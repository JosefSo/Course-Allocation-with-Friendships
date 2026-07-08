from __future__ import annotations

import csv
import hashlib
import html
import json
import sqlite3
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .hbs_api import normalize_improvement_config, normalize_pick_rule, normalize_sequence, run_hbs_social
from .hbs_io import _read_table_1
from .hbs_statistics import bootstrap_mean_ci, paired_nonparametric_tests


SCHEMA_VERSION = 1


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _dataset_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _metric_dimensions(metric_name: str) -> tuple[str, str | None, str | None]:
    representation = next(
        (
            candidate
            for candidate in ("course", "friend", "combined")
            if metric_name.endswith(f"_{candidate}")
        ),
        None,
    )
    base_name = (
        metric_name[: -(len(representation) + 1)]
        if representation is not None
        else metric_name
    )
    envy_definition = None
    for candidate in ("substitution", "swap", "base_only"):
        suffix = f"_{candidate}"
        if base_name.endswith(suffix):
            envy_definition = candidate.replace("_", "-")
            base_name = base_name[: -len(suffix)]
            break
    return base_name, representation, envy_definition


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS experiments (
            experiment_id TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            config_json TEXT NOT NULL,
            config_hash TEXT NOT NULL,
            dataset_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id TEXT NOT NULL,
            initial_method TEXT NOT NULL,
            sequence TEXT NOT NULL,
            pick_rule TEXT NOT NULL,
            post_mode TEXT NOT NULL,
            lambda_value REAL,
            network_model TEXT NOT NULL,
            seed INTEGER NOT NULL,
            config_hash TEXT NOT NULL,
            dataset_hash TEXT NOT NULL,
            total_utility REAL NOT NULL,
            gini_total_norm REAL NOT NULL,
            allocation_hash TEXT NOT NULL,
            UNIQUE (
                experiment_id, initial_method, sequence, pick_rule,
                post_mode, lambda_value, seed
            )
        );
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            metric TEXT NOT NULL,
            value REAL NOT NULL,
            representation TEXT,
            envy_definition TEXT,
            FOREIGN KEY (run_id) REFERENCES runs(id)
        );
        CREATE TABLE IF NOT EXISTS pick_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            event_index INTEGER NOT NULL,
            round_picked INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            course_id TEXT NOT NULL,
            initial_position INTEGER NOT NULL,
            turn_position INTEGER NOT NULL,
            normalized_turn_position REAL NOT NULL,
            friend_opportunity_at_pick REAL NOT NULL,
            reactive_friend_bonus_at_pick REAL NOT NULL,
            utility_at_pick REAL NOT NULL,
            ex_post_course_utility REAL NOT NULL,
            ex_post_friend_utility REAL NOT NULL,
            ex_post_combined_utility REAL NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(id)
        );
        CREATE INDEX IF NOT EXISTS idx_research_metrics_run ON metrics(run_id);
        CREATE INDEX IF NOT EXISTS idx_research_picks_run ON pick_events(run_id);
        """
    )


def _resolve_path(base: Path, raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else (base / path).resolve()


def load_research_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("research config must be a JSON object")
    if int(config.get("schema_version", 0)) != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    for section in ("experiment_id", "dataset", "allocation", "factors", "output_dir"):
        if section not in config:
            raise ValueError(f"missing research config field: {section}")
    base = path.resolve().parent
    dataset = dict(config["dataset"])
    for key in ("table1", "table2"):
        dataset[key] = str(_resolve_path(base, str(dataset[key])))
    if dataset.get("table3"):
        dataset["table3"] = str(_resolve_path(base, str(dataset["table3"])))
    config["dataset"] = dataset
    config["output_dir"] = str(_resolve_path(base, str(config["output_dir"])))
    return config


def _constant_lambda_csv(path: Path, table1: Path, value: float) -> Path:
    students = sorted({row.student_id for row in _read_table_1(table1)})
    path.write_text(
        "StudentID,LambdaFriend\n"
        + "".join(f"{student},{value:.6f}\n" for student in students),
        encoding="utf-8",
    )
    return path


def _mechanism_label(run: sqlite3.Row | dict[str, Any]) -> str:
    return "/".join(
        str(run[key])
        for key in ("initial_method", "sequence", "pick_rule", "post_mode")
    )


def _write_flat_csv(conn: sqlite3.Connection, path: Path) -> None:
    conn.row_factory = sqlite3.Row
    runs = conn.execute("SELECT * FROM runs ORDER BY id").fetchall()
    metric_rows = conn.execute(
        "SELECT run_id, metric, value, representation, envy_definition FROM metrics"
    ).fetchall()
    metrics_by_run: dict[int, dict[str, float]] = defaultdict(dict)
    for row in metric_rows:
        key = str(row["metric"])
        if row["envy_definition"]:
            key += f"_{str(row['envy_definition']).replace('-', '_')}"
        if row["representation"]:
            key += f"_{row['representation']}"
        metrics_by_run[int(row["run_id"])][key] = float(row["value"])
    metric_names = sorted({name for values in metrics_by_run.values() for name in values})
    fields = [
        "run_id", "experiment_id", "initial_method", "sequence", "pick_rule",
        "post_mode", "lambda_value", "network_model", "seed", "config_hash",
        "dataset_hash", "allocation_hash", *metric_names,
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for run in runs:
            row = {field: run[field] for field in fields if field in run.keys()}
            row["run_id"] = run["id"]
            row.update(metrics_by_run[int(run["id"])])
            writer.writerow(row)


def _aggregate_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT r.*, m.metric, m.value, m.representation, m.envy_definition
        FROM runs r JOIN metrics m ON m.run_id = r.id
        ORDER BY r.id
        """
    ).fetchall()
    grouped: dict[tuple[str, float | None, str], list[float]] = defaultdict(list)
    for row in rows:
        metric = str(row["metric"])
        if row["envy_definition"]:
            metric += f"_{str(row['envy_definition']).replace('-', '_')}"
        if row["representation"]:
            metric += f"_{row['representation']}"
        grouped[(_mechanism_label(row), row["lambda_value"], metric)].append(float(row["value"]))
    output = []
    for (mechanism, lambda_value, metric), values in sorted(grouped.items(), key=str):
        low, high = bootstrap_mean_ci(values, resamples=1000, seed=0)
        output.append(
            {
                "mechanism": mechanism,
                "lambda": lambda_value,
                "metric": metric,
                "n": len(values),
                "mean": sum(values) / len(values),
                "ci95_low": low,
                "ci95_high": high,
            }
        )
    return output


def _write_aggregate_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fields = ["mechanism", "lambda", "metric", "n", "mean", "ci95_low", "ci95_high"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_html_reports(rows: list[dict[str, Any]], output_dir: Path) -> None:
    def render(title: str, selected: list[dict[str, Any]], note: str) -> str:
        body_rows = "".join(
            "<tr>"
            + "".join(
                f"<td>{html.escape(str(row[key]))}</td>"
                for key in ("mechanism", "lambda", "metric", "n", "mean", "ci95_low", "ci95_high")
            )
            + "</tr>"
            for row in selected
        )
        return (
            "<!doctype html><meta charset='utf-8'>"
            f"<title>{html.escape(title)}</title><h1>{html.escape(title)}</h1>"
            f"<p>{html.escape(note)}</p><table border='1' cellspacing='0' cellpadding='5'>"
            "<tr><th>mechanism</th><th>lambda</th><th>metric</th><th>n</th>"
            "<th>mean</th><th>CI low</th><th>CI high</th></tr>"
            f"{body_rows}</table>"
        )

    warning = (
        "Combined utility may be compared only within a fixed lambda; cross-lambda "
        "ranking is intentionally not produced."
    )
    (output_dir / "results.html").write_text(
        render("Research Results", rows, warning), encoding="utf-8"
    )
    position_rows = [row for row in rows if "position" in str(row["metric"])]
    (output_dir / "position_effects.html").write_text(
        render("Position Effects", position_rows, warning), encoding="utf-8"
    )
    fairness_rows = [
        row
        for row in rows
        if any(token in str(row["metric"]) for token in ("ef1", "envy", "gini", "egalitarian", "nash"))
    ]
    (output_dir / "fairness.html").write_text(
        render("Fairness", fairness_rows, warning), encoding="utf-8"
    )


def _position_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    raw = conn.execute(
        """
        SELECT r.initial_method, r.sequence, r.pick_rule, r.post_mode, r.lambda_value,
               p.normalized_turn_position, p.friend_opportunity_at_pick,
               p.ex_post_course_utility, p.ex_post_friend_utility,
               p.ex_post_combined_utility
        FROM runs r JOIN pick_events p ON p.run_id = r.id
        ORDER BY r.id, p.event_index
        """
    ).fetchall()
    grouped: dict[tuple[str, float | None, int], list[sqlite3.Row]] = defaultdict(list)
    for row in raw:
        decile = min(9, int(float(row["normalized_turn_position"]) * 10.0))
        grouped[(_mechanism_label(row), row["lambda_value"], decile)].append(row)
    output = []
    for (mechanism, lambda_value, decile), values in sorted(grouped.items(), key=str):
        output.append(
            {
                "mechanism": mechanism,
                "lambda": lambda_value,
                "position_decile": decile,
                "n": len(values),
                "friend_opportunity": sum(float(row["friend_opportunity_at_pick"]) for row in values) / len(values),
                "course_utility": sum(float(row["ex_post_course_utility"]) for row in values) / len(values),
                "friend_utility": sum(float(row["ex_post_friend_utility"]) for row in values) / len(values),
                "combined_utility": sum(float(row["ex_post_combined_utility"]) for row in values) / len(values),
            }
        )
    return output


def _write_position_artifacts(rows: list[dict[str, Any]], output_dir: Path) -> None:
    fields = [
        "mechanism", "lambda", "position_decile", "n", "friend_opportunity",
        "course_utility", "friend_utility", "combined_utility",
    ]
    with (output_dir / "position_effects.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    table_rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row[field]))}</td>" for field in fields) + "</tr>"
        for row in rows
    )
    (output_dir / "position_effects.html").write_text(
        "<!doctype html><meta charset='utf-8'><h1>Position Effects</h1>"
        "<p>Combined utility is comparable only within a fixed lambda.</p>"
        "<table border='1' cellspacing='0' cellpadding='5'><tr>"
        + "".join(f"<th>{field}</th>" for field in fields)
        + f"</tr>{table_rows}</table>",
        encoding="utf-8",
    )
    width, height, margin = 900, 420, 45
    points = []
    max_value = max((float(row["combined_utility"]) for row in rows), default=1.0) or 1.0
    for row in rows:
        x = margin + (float(row["position_decile"]) / 9.0 if 9 else 0.0) * (width - 2 * margin)
        y = height - margin - float(row["combined_utility"]) / max_value * (height - 2 * margin)
        points.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#285f9e"/>')
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
        '<rect width="100%" height="100%" fill="white"/>'
        f'<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="black"/>'
        f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}" stroke="black"/>'
        + "".join(points)
        + "</svg>"
    )
    (output_dir / "position_effects.svg").write_text(svg, encoding="utf-8")


def _write_inferential_statistics(conn: sqlite3.Connection, output_dir: Path) -> None:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT r.seed, r.lambda_value, r.initial_method, r.sequence, r.pick_rule,
               r.post_mode, m.value
        FROM runs r JOIN metrics m ON m.run_id = r.id
        WHERE m.metric = 'total_utility' AND m.representation IS NULL
        ORDER BY r.lambda_value, r.seed
        """
    ).fetchall()
    by_lambda: dict[str, dict[str, dict[int, float]]] = defaultdict(lambda: defaultdict(dict))
    for row in rows:
        lambda_key = "table3" if row["lambda_value"] is None else str(row["lambda_value"])
        by_lambda[lambda_key][_mechanism_label(row)][int(row["seed"])] = float(row["value"])
    output: dict[str, Any] = {
        "alpha": 0.05,
        "warning": "Combined utility comparisons are separated by lambda.",
        "by_lambda": {},
    }
    for lambda_key, mechanisms in by_lambda.items():
        common_seeds = set.intersection(*(set(values) for values in mechanisms.values())) if mechanisms else set()
        paired = {
            mechanism: [values[seed] for seed in sorted(common_seeds)]
            for mechanism, values in mechanisms.items()
        }
        if len(paired) < 2 or not common_seeds:
            output["by_lambda"][lambda_key] = {"status": "insufficient paired data"}
            continue
        try:
            result = paired_nonparametric_tests(paired)
            result["paired_seeds"] = len(common_seeds)
            output["by_lambda"][lambda_key] = result
        except RuntimeError as exc:
            output["by_lambda"][lambda_key] = {"status": str(exc)}
    (output_dir / "statistics.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_research_config(config_path: Path) -> dict[str, Any]:
    config = load_research_config(config_path)
    dataset = dict(config["dataset"])
    allocation = dict(config["allocation"])
    factors = dict(config["factors"])
    output_dir = Path(str(config["output_dir"]))
    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = output_dir / "research.sqlite3"

    table1 = Path(str(dataset["table1"]))
    table2 = Path(str(dataset["table2"]))
    table3 = Path(str(dataset["table3"])) if dataset.get("table3") else None
    for path in (table1, table2, *([table3] if table3 is not None else [])):
        if not path.is_file():
            raise ValueError(f"dataset file not found: {path}")
    data_hash = _dataset_hash([table1, table2, *([table3] if table3 else [])])
    config_hash = _sha256_bytes(_canonical_json(config).encode("utf-8"))
    experiment_id = str(config["experiment_id"])

    initial_methods = list(factors.get("initial_methods", ["sequential"]))
    sequences = list(factors.get("sequences", ["snake"]))
    pick_rules = list(factors.get("pick_rules", ["personal"]))
    post_modes = list(factors.get("post_modes", ["none"]))
    seeds = [int(seed) for seed in factors.get("seeds", [11])]
    lambda_values = factors.get("lambda_values")
    lambdas = [None] if lambda_values is None else [float(value) for value in lambda_values]
    if any(value is not None and not (0.0 <= value <= 1.0) for value in lambdas):
        raise ValueError("lambda_values must be in [0,1]")

    with sqlite3.connect(db_path) as conn, tempfile.TemporaryDirectory() as tmp:
        _init_db(conn)
        conn.execute(
            "INSERT OR REPLACE INTO experiments VALUES (?, ?, ?, ?, ?, ?)",
            (
                experiment_id,
                SCHEMA_VERSION,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                _canonical_json(config),
                config_hash,
                data_hash,
            ),
        )
        run_count = 0
        for initial_method in initial_methods:
            mechanism_sequences = sequences if initial_method == "sequential" else ["round-robin"]
            for sequence_raw in mechanism_sequences:
                sequence = normalize_sequence(str(sequence_raw))
                for pick_rule_raw in pick_rules:
                    pick_rule = normalize_pick_rule(str(pick_rule_raw))
                    for post_mode in post_modes:
                        if post_mode == "none":
                            improve_mode = "swap-global"
                            post_iters = 0
                        else:
                            _move, _scope, improve_mode = normalize_improvement_config(
                                improve_mode=str(post_mode)
                            )
                            post_iters = int(allocation.get("post_iters", 0))
                        for lambda_value in lambdas:
                            lambda_path = table3
                            if lambda_value is not None:
                                lambda_path = _constant_lambda_csv(
                                    Path(tmp) / f"lambda_{lambda_value:.6f}.csv",
                                    table1,
                                    lambda_value,
                                )
                            for seed in seeds:
                                result = run_hbs_social(
                                    table1,
                                    table2,
                                    csv_lambda=lambda_path,
                                    cap_default=int(allocation["cap_default"]),
                                    b=int(allocation["b"]),
                                    draft_rounds=allocation.get("draft_rounds"),
                                    post_iters=post_iters,
                                    improve_mode=improve_mode,
                                    initial_method=str(initial_method),
                                    sequence=sequence,
                                    pick_rule=pick_rule,
                                    seed=seed,
                                )
                                allocation_hash = _sha256_bytes(
                                    _canonical_json(result.alloc).encode("utf-8")
                                )
                                existing_ids = [
                                    int(row[0])
                                    for row in conn.execute(
                                        """
                                        SELECT id FROM runs
                                        WHERE experiment_id=? AND initial_method=? AND sequence=?
                                          AND pick_rule=? AND post_mode=? AND seed=?
                                          AND ((lambda_value IS NULL AND ? IS NULL) OR lambda_value=?)
                                        """,
                                        (
                                            experiment_id, initial_method, sequence, pick_rule,
                                            post_mode, seed, lambda_value, lambda_value,
                                        ),
                                    ).fetchall()
                                ]
                                for existing_id in existing_ids:
                                    conn.execute("DELETE FROM metrics WHERE run_id=?", (existing_id,))
                                    conn.execute("DELETE FROM pick_events WHERE run_id=?", (existing_id,))
                                    conn.execute("DELETE FROM runs WHERE id=?", (existing_id,))
                                cursor = conn.execute(
                                    """
                                    INSERT OR REPLACE INTO runs (
                                        experiment_id, initial_method, sequence, pick_rule,
                                        post_mode, lambda_value, network_model, seed,
                                        config_hash, dataset_hash, total_utility,
                                        gini_total_norm, allocation_hash
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        experiment_id,
                                        initial_method,
                                        sequence,
                                        pick_rule,
                                        post_mode,
                                        lambda_value,
                                        str(dataset.get("network_model", "unknown")),
                                        seed,
                                        config_hash,
                                        data_hash,
                                        result.summary.total_utility,
                                        result.summary.gini_total_norm,
                                        allocation_hash,
                                    ),
                                )
                                run_id = int(cursor.lastrowid)
                                conn.execute("DELETE FROM metrics WHERE run_id = ?", (run_id,))
                                conn.execute("DELETE FROM pick_events WHERE run_id = ?", (run_id,))
                                for name, value in result.metrics_extended.values.items():
                                    metric, representation, envy_definition = _metric_dimensions(name)
                                    conn.execute(
                                        "INSERT INTO metrics (run_id, metric, value, representation, envy_definition) VALUES (?, ?, ?, ?, ?)",
                                        (run_id, metric, float(value), representation, envy_definition),
                                    )
                                for index, row in enumerate(result.pick_log):
                                    conn.execute(
                                        """
                                        INSERT INTO pick_events VALUES (
                                            NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                                        )
                                        """,
                                        (
                                            run_id, index, row.round_picked, row.student_id,
                                            row.course_id, row.initial_position, row.turn_position,
                                            row.normalized_turn_position,
                                            row.friend_opportunity_at_pick,
                                            row.friend_bonus_at_pick, row.utility_at_pick,
                                            row.ex_post_course_utility,
                                            row.ex_post_friend_utility,
                                            row.ex_post_combined_utility,
                                        ),
                                    )
                                run_count += 1
        conn.commit()
        _write_flat_csv(conn, output_dir / "runs_flat.csv")
        aggregates = _aggregate_rows(conn)
        _write_aggregate_csv(aggregates, output_dir / "aggregates.csv")
        _write_html_reports(aggregates, output_dir)
        _write_position_artifacts(_position_rows(conn), output_dir)
        _write_inferential_statistics(conn, output_dir)

    (output_dir / "resolved_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "experiment_id": experiment_id,
        "runs": run_count,
        "db_path": str(db_path),
        "config_hash": config_hash,
        "dataset_hash": data_hash,
    }
