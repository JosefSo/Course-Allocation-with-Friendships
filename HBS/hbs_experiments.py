from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .hbs_api import (
    CANONICAL_IMPROVE_MODES,
    normalize_improvement_config,
    normalize_improve_mode,
    run_hbs_social,
)
from .hbs_domain import PostAllocLogRow
from .hbs_io import (
    _write_metrics_extended_csv,
    _write_post_alloc_csv,
    _write_summary_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
TABLES_DIR = REPO_ROOT / "tables"

DEFAULT_OUT_DIR = Path("results/experiments")
DEFAULT_DB_PATH = DEFAULT_OUT_DIR / "experiments.sqlite"
DEFAULT_POST_GRID = (0, 1, 5, 10, 20)
DEFAULT_MODES = CANONICAL_IMPROVE_MODES
ALLOWED_MODES = set(DEFAULT_MODES)


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    table1_ref: str
    table2_ref: str
    lambda_ref: str | None
    cap_default: int
    b: int
    draft_rounds: int


@dataclass
class SweepRun:
    scenario_id: str
    table1_ref: str
    table2_ref: str
    lambda_ref: str | None
    cap_default: int
    b: int
    draft_rounds: int
    seed: int
    post_iters: int
    move_type: str
    objective_scope: str
    improve_mode: str
    total_utility: float
    gini_total_norm: float
    gini_base_norm: float
    metrics_extended: dict[str, float]
    metrics_maxima: dict[str, float]
    allocation_hash: str
    summary_signature: str
    post_log_len: int
    has_noop: bool
    has_early_stop: bool
    artifact_dir: str
    allocation_path: str
    post_allocation_path: str
    summary_path: str
    metrics_extended_path: str
    run_id: int | None = None


@dataclass
class StabilityCheck:
    scenario_id: str
    improve_mode: str
    seed: int
    max_post_iters: int
    stable_from_post: int | None
    all_equal: bool
    classification: str
    signatures_by_post: dict[int, str]
    no_op_posts: list[int]
    early_stop_posts: list[int]


@dataclass(frozen=True)
class SweepResult:
    experiment_id: int
    total_planned_runs: int
    total_runs_used: int
    runs_executed: int
    runs_reused: int
    db_path: Path
    runs_flat_csv: Path
    mode_post_agg_csv: Path
    stability_csv: Path
    report_md: Path


DEFAULT_SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        scenario_id="A_200x8",
        table1_ref="table1_200x8.csv",
        table2_ref="table2_200x8.csv",
        lambda_ref="table3_lambda_200x8.csv",
        cap_default=80,
        b=3,
        draft_rounds=3,
    ),
    Scenario(
        scenario_id="B_200x10",
        table1_ref="table1_200x10.csv",
        table2_ref="table2_200x10.csv",
        lambda_ref="table3_lambda_200x10.csv",
        cap_default=70,
        b=3,
        draft_rounds=3,
    ),
    Scenario(
        scenario_id="C_200x12",
        table1_ref="table1_200x12.csv",
        table2_ref="table2_200x12.csv",
        lambda_ref="table3_lambda_200x12.csv",
        cap_default=60,
        b=3,
        draft_rounds=3,
    ),
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canonical_allocation_json(alloc: dict[str, list[str]]) -> str:
    ordered = {student_id: alloc[student_id] for student_id in sorted(alloc)}
    return json.dumps(ordered, ensure_ascii=True, separators=(",", ":"), sort_keys=False)


def _allocation_hash(alloc: dict[str, list[str]]) -> str:
    canonical = _canonical_allocation_json(alloc)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _summary_signature(total_utility: float, gini_total_norm: float, gini_base_norm: float) -> str:
    return f"{total_utility:.6f}|{gini_total_norm:.6f}|{gini_base_norm:.6f}"


def _parse_post_grid(raw: str) -> list[int]:
    values: list[int] = []
    for token in raw.split(","):
        cleaned = token.strip()
        if not cleaned:
            continue
        value = int(cleaned)
        if value < 0:
            raise ValueError("post_grid values must be >= 0")
        values.append(value)
    if not values:
        raise ValueError("post_grid cannot be empty")
    return sorted(set(values))


def _parse_modes(raw: str) -> list[str]:
    modes: list[str] = []
    for token in raw.split(","):
        mode = normalize_improve_mode(token.strip())
        if not mode:
            continue
        if mode not in ALLOWED_MODES:
            allowed = ", ".join(sorted(ALLOWED_MODES))
            raise ValueError(f"Unsupported mode '{mode}'. Allowed: {allowed}")
        modes.append(mode)
    if not modes:
        raise ValueError("modes cannot be empty")
    return modes


def _metric_stats(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return (0.0, 0.0, 0.0)
    mean_v = statistics.fmean(values)
    std_v = statistics.pstdev(values) if len(values) > 1 else 0.0
    median_v = statistics.median(values)
    return (mean_v, std_v, median_v)


def _relative_to(base_dir: Path, path: Path) -> str:
    return str(path.relative_to(base_dir))


def _scenario_path(file_ref: str | None) -> Path | None:
    if file_ref is None:
        return None
    return TABLES_DIR / file_ref


def _ensure_scenario_files_exist(scenario: Scenario) -> None:
    required = [
        _scenario_path(scenario.table1_ref),
        _scenario_path(scenario.table2_ref),
    ]
    if scenario.lambda_ref is not None:
        required.append(_scenario_path(scenario.lambda_ref))
    for path in required:
        if path is None:
            continue
        if not path.exists():
            raise FileNotFoundError(f"Scenario file not found: {path}")
        if not path.is_file():
            raise FileNotFoundError(f"Scenario path is not a file: {path}")


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            out_dir TEXT NOT NULL,
            db_path TEXT NOT NULL,
            seed_start INTEGER NOT NULL,
            seed_count INTEGER NOT NULL,
            post_grid TEXT NOT NULL,
            modes TEXT NOT NULL,
            scenarios_json TEXT NOT NULL,
            resume INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            scenario_id TEXT NOT NULL,
            table1_ref TEXT NOT NULL,
            table2_ref TEXT NOT NULL,
            lambda_ref TEXT,
            cap_default INTEGER NOT NULL,
            b INTEGER NOT NULL,
            draft_rounds INTEGER NOT NULL,
            seed INTEGER NOT NULL,
            post_iters INTEGER NOT NULL,
            move_type TEXT,
            objective_scope TEXT,
            improve_mode TEXT NOT NULL,
            total_utility REAL NOT NULL,
            gini_total_norm REAL NOT NULL,
            gini_base_norm REAL NOT NULL,
            metrics_extended_json TEXT NOT NULL,
            metrics_maxima_json TEXT NOT NULL,
            allocation_hash TEXT NOT NULL,
            summary_signature TEXT NOT NULL,
            post_log_len INTEGER NOT NULL,
            has_noop INTEGER NOT NULL,
            has_early_stop INTEGER NOT NULL,
            artifact_dir TEXT NOT NULL,
            allocation_path TEXT NOT NULL,
            post_allocation_path TEXT NOT NULL,
            summary_path TEXT NOT NULL,
            metrics_extended_path TEXT NOT NULL,
            UNIQUE (scenario_id, seed, post_iters, improve_mode)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS post_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            event_index INTEGER NOT NULL,
            iteration INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            student_id TEXT,
            dropped_courses TEXT,
            added_courses TEXT,
            swap_student_1 TEXT,
            swap_course_1 TEXT,
            swap_student_2 TEXT,
            swap_course_2 TEXT,
            delta_utility REAL,
            FOREIGN KEY (run_id) REFERENCES runs(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS stability_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            scenario_id TEXT NOT NULL,
            improve_mode TEXT NOT NULL,
            seed INTEGER NOT NULL,
            max_post_iters INTEGER NOT NULL,
            stable_from_post INTEGER,
            all_equal INTEGER NOT NULL,
            classification TEXT NOT NULL,
            signatures_json TEXT NOT NULL,
            no_op_posts_json TEXT NOT NULL,
            early_stop_posts_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_runs_lookup "
        "ON runs(scenario_id, seed, post_iters, improve_mode)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_post_events_run_id ON post_events(run_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_stability_checks_experiment_id "
        "ON stability_checks(experiment_id)"
    )
    run_columns = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(runs)").fetchall()
    }
    if "move_type" not in run_columns:
        conn.execute("ALTER TABLE runs ADD COLUMN move_type TEXT")
    if "objective_scope" not in run_columns:
        conn.execute("ALTER TABLE runs ADD COLUMN objective_scope TEXT")
    rows_to_backfill = conn.execute(
        """
        SELECT id, improve_mode
        FROM runs
        WHERE move_type IS NULL OR objective_scope IS NULL
        """
    ).fetchall()
    for row_id, improve_mode in rows_to_backfill:
        move_type, objective_scope, effective_mode = normalize_improvement_config(
            improve_mode=str(improve_mode)
        )
        conn.execute(
            """
            UPDATE runs
            SET move_type = ?, objective_scope = ?, improve_mode = ?
            WHERE id = ?
            """,
            (move_type, objective_scope, effective_mode, int(row_id)),
        )
    conn.commit()


def _insert_experiment(
    conn: sqlite3.Connection,
    *,
    out_dir: Path,
    db_path: Path,
    seed_start: int,
    seed_count: int,
    post_grid: list[int],
    modes: list[str],
    scenarios: list[Scenario],
    resume: bool,
) -> int:
    created_at = _utc_now_iso()
    scenarios_json = [
        {
            "scenario_id": s.scenario_id,
            "table1_ref": s.table1_ref,
            "table2_ref": s.table2_ref,
            "lambda_ref": s.lambda_ref,
            "cap_default": s.cap_default,
            "b": s.b,
            "draft_rounds": s.draft_rounds,
        }
        for s in scenarios
    ]
    cursor = conn.execute(
        """
        INSERT INTO experiments (
            created_at, out_dir, db_path, seed_start, seed_count, post_grid, modes, scenarios_json, resume
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            created_at,
            str(out_dir),
            str(db_path),
            seed_start,
            seed_count,
            ",".join(str(v) for v in post_grid),
            ",".join(modes),
            json.dumps(scenarios_json, ensure_ascii=True, sort_keys=True),
            int(resume),
        ),
    )
    conn.commit()
    experiment_id = cursor.lastrowid
    if experiment_id is None:
        raise RuntimeError("Failed to create experiment row")
    return int(experiment_id)


def _row_to_run(row: sqlite3.Row) -> SweepRun:
    return SweepRun(
        scenario_id=str(row["scenario_id"]),
        table1_ref=str(row["table1_ref"]),
        table2_ref=str(row["table2_ref"]),
        lambda_ref=(str(row["lambda_ref"]) if row["lambda_ref"] is not None else None),
        cap_default=int(row["cap_default"]),
        b=int(row["b"]),
        draft_rounds=int(row["draft_rounds"]),
        seed=int(row["seed"]),
        post_iters=int(row["post_iters"]),
        move_type=(str(row["move_type"]) if row["move_type"] is not None else ""),
        objective_scope=(str(row["objective_scope"]) if row["objective_scope"] is not None else ""),
        improve_mode=str(row["improve_mode"]),
        total_utility=float(row["total_utility"]),
        gini_total_norm=float(row["gini_total_norm"]),
        gini_base_norm=float(row["gini_base_norm"]),
        metrics_extended=json.loads(str(row["metrics_extended_json"])),
        metrics_maxima=json.loads(str(row["metrics_maxima_json"])),
        allocation_hash=str(row["allocation_hash"]),
        summary_signature=str(row["summary_signature"]),
        post_log_len=int(row["post_log_len"]),
        has_noop=bool(row["has_noop"]),
        has_early_stop=bool(row["has_early_stop"]),
        artifact_dir=str(row["artifact_dir"]),
        allocation_path=str(row["allocation_path"]),
        post_allocation_path=str(row["post_allocation_path"]),
        summary_path=str(row["summary_path"]),
        metrics_extended_path=str(row["metrics_extended_path"]),
        run_id=int(row["id"]),
    )


def _load_existing_run(
    conn: sqlite3.Connection,
    *,
    scenario_id: str,
    seed: int,
    post_iters: int,
    improve_mode: str,
) -> SweepRun | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT
            id, scenario_id, table1_ref, table2_ref, lambda_ref,
            cap_default, b, draft_rounds, seed, post_iters, move_type, objective_scope,
            improve_mode,
            total_utility, gini_total_norm, gini_base_norm,
            metrics_extended_json, metrics_maxima_json,
            allocation_hash, summary_signature, post_log_len,
            has_noop, has_early_stop, artifact_dir,
            allocation_path, post_allocation_path, summary_path, metrics_extended_path
        FROM runs
        WHERE scenario_id = ? AND seed = ? AND post_iters = ? AND improve_mode = ?
        """,
        (scenario_id, seed, post_iters, improve_mode),
    ).fetchone()
    if row is None:
        return None
    return _row_to_run(row)


def _delete_existing_run(
    conn: sqlite3.Connection,
    *,
    scenario_id: str,
    seed: int,
    post_iters: int,
    improve_mode: str,
) -> None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id FROM runs WHERE scenario_id = ? AND seed = ? AND post_iters = ? AND improve_mode = ?",
        (scenario_id, seed, post_iters, improve_mode),
    ).fetchone()
    if row is None:
        return
    run_id = int(row["id"])
    conn.execute("DELETE FROM post_events WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
    conn.commit()


def _persist_run(
    conn: sqlite3.Connection,
    *,
    experiment_id: int,
    run: SweepRun,
    post_log: list[PostAllocLogRow],
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO runs (
            experiment_id, created_at, scenario_id, table1_ref, table2_ref, lambda_ref,
            cap_default, b, draft_rounds, seed, post_iters, move_type, objective_scope,
            improve_mode,
            total_utility, gini_total_norm, gini_base_norm,
            metrics_extended_json, metrics_maxima_json,
            allocation_hash, summary_signature, post_log_len, has_noop, has_early_stop,
            artifact_dir, allocation_path, post_allocation_path, summary_path, metrics_extended_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            experiment_id,
            _utc_now_iso(),
            run.scenario_id,
            run.table1_ref,
            run.table2_ref,
            run.lambda_ref,
            run.cap_default,
            run.b,
            run.draft_rounds,
            run.seed,
            run.post_iters,
            run.move_type,
            run.objective_scope,
            run.improve_mode,
            run.total_utility,
            run.gini_total_norm,
            run.gini_base_norm,
            json.dumps(run.metrics_extended, ensure_ascii=True, sort_keys=True),
            json.dumps(run.metrics_maxima, ensure_ascii=True, sort_keys=True),
            run.allocation_hash,
            run.summary_signature,
            run.post_log_len,
            int(run.has_noop),
            int(run.has_early_stop),
            run.artifact_dir,
            run.allocation_path,
            run.post_allocation_path,
            run.summary_path,
            run.metrics_extended_path,
        ),
    )
    run_id = cursor.lastrowid
    if run_id is None:
        raise RuntimeError("Failed to insert run row")
    for event_index, event in enumerate(post_log):
        dropped = "" if not event.dropped_courses else ";".join(event.dropped_courses)
        added = "" if not event.added_courses else ";".join(event.added_courses)
        conn.execute(
            """
            INSERT INTO post_events (
                run_id, event_index, iteration, event_type, student_id,
                dropped_courses, added_courses, swap_student_1, swap_course_1,
                swap_student_2, swap_course_2, delta_utility
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(run_id),
                event_index,
                event.iteration,
                event.event_type,
                event.student_id,
                dropped,
                added,
                event.swap_student_1,
                event.swap_course_1,
                event.swap_student_2,
                event.swap_course_2,
                event.delta_utility,
            ),
        )
    conn.commit()
    return int(run_id)


def _write_allocation_json(path: Path, alloc: dict[str, list[str]]) -> None:
    ordered = {student_id: alloc[student_id] for student_id in sorted(alloc)}
    with path.open("w", encoding="utf-8") as f:
        json.dump(ordered, f, ensure_ascii=True, indent=2, sort_keys=False)
        f.write("\n")


def _run_single(
    *,
    out_dir: Path,
    scenario: Scenario,
    seed: int,
    post_iters: int,
    mode: str,
) -> tuple[SweepRun, list[PostAllocLogRow]]:
    table1_path = _scenario_path(scenario.table1_ref)
    table2_path = _scenario_path(scenario.table2_ref)
    lambda_path = _scenario_path(scenario.lambda_ref)
    if table1_path is None or table2_path is None:
        raise AssertionError("Scenario table paths cannot be None")

    run_dir = (
        out_dir
        / "runs"
        / scenario.scenario_id
        / f"mode_{mode}"
        / f"seed_{seed}"
        / f"post_{post_iters}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    move_type, objective_scope, effective_mode = normalize_improvement_config(improve_mode=mode)

    result = run_hbs_social(
        table1_path,
        table2_path,
        csv_lambda=lambda_path,
        cap_default=scenario.cap_default,
        b=scenario.b,
        seed=seed,
        draft_rounds=scenario.draft_rounds,
        post_iters=post_iters,
        improve_mode=mode,
        move_type=move_type,
        objective_scope=objective_scope,
        progress=False,
        sanity_checks=False,
        delta_check_every=0,
    )

    allocation_path = run_dir / "allocation.json"
    post_allocation_path = run_dir / "post_allocation.csv"
    summary_path = run_dir / "summary.csv"
    metrics_extended_path = run_dir / "metrics_extended.csv"

    _write_allocation_json(allocation_path, result.alloc)
    _write_post_alloc_csv(post_allocation_path, post_log=result.post_log)
    _write_summary_csv(
        summary_path,
        seed=seed,
        cap_default=scenario.cap_default,
        b=scenario.b,
        draft_rounds=scenario.draft_rounds,
        post_iters=post_iters,
        summary=result.summary,
    )
    _write_metrics_extended_csv(metrics_extended_path, metrics=result.metrics_extended)

    post_log_len = len(result.post_log)
    has_noop = any(row.event_type == "" for row in result.post_log)
    has_early_stop = bool(post_iters > 0 and has_noop and post_log_len < post_iters)

    run = SweepRun(
        scenario_id=scenario.scenario_id,
        table1_ref=scenario.table1_ref,
        table2_ref=scenario.table2_ref,
        lambda_ref=scenario.lambda_ref,
        cap_default=scenario.cap_default,
        b=scenario.b,
        draft_rounds=scenario.draft_rounds,
        seed=seed,
        post_iters=post_iters,
        move_type=move_type,
        objective_scope=objective_scope,
        improve_mode=effective_mode,
        total_utility=result.summary.total_utility,
        gini_total_norm=result.summary.gini_total_norm,
        gini_base_norm=result.summary.gini_base_norm,
        metrics_extended=result.metrics_extended.values,
        metrics_maxima=result.metrics_extended.maxima,
        allocation_hash=_allocation_hash(result.alloc),
        summary_signature=_summary_signature(
            result.summary.total_utility,
            result.summary.gini_total_norm,
            result.summary.gini_base_norm,
        ),
        post_log_len=post_log_len,
        has_noop=has_noop,
        has_early_stop=has_early_stop,
        artifact_dir=_relative_to(out_dir, run_dir),
        allocation_path=_relative_to(out_dir, allocation_path),
        post_allocation_path=_relative_to(out_dir, post_allocation_path),
        summary_path=_relative_to(out_dir, summary_path),
        metrics_extended_path=_relative_to(out_dir, metrics_extended_path),
    )
    return run, result.post_log


def _compute_stability_for_group(group: list[SweepRun]) -> StabilityCheck:
    if not group:
        raise ValueError("stability group cannot be empty")
    ordered = sorted(group, key=lambda r: r.post_iters)
    signatures_by_post = {
        run.post_iters: f"{run.allocation_hash}|{run.summary_signature}" for run in ordered
    }
    signatures = [signatures_by_post[run.post_iters] for run in ordered]
    all_equal = len(set(signatures)) == 1

    stable_from_post: int | None = None
    for i, run in enumerate(ordered):
        suffix = signatures[i:]
        if len(set(suffix)) == 1:
            stable_from_post = run.post_iters
            break

    if stable_from_post is None:
        classification = "still_improving_at_max_post"
    elif any(run.has_early_stop for run in ordered):
        classification = "hybrid_early_stop"
    elif any(run.has_noop for run in ordered if run.post_iters > 0):
        classification = "no_op_tail_without_break"
    else:
        classification = "no_op_tail_without_break"

    no_op_posts = [run.post_iters for run in ordered if run.has_noop]
    early_stop_posts = [run.post_iters for run in ordered if run.has_early_stop]

    first = ordered[0]
    return StabilityCheck(
        scenario_id=first.scenario_id,
        improve_mode=first.improve_mode,
        seed=first.seed,
        max_post_iters=max(run.post_iters for run in ordered),
        stable_from_post=stable_from_post,
        all_equal=all_equal,
        classification=classification,
        signatures_by_post=signatures_by_post,
        no_op_posts=no_op_posts,
        early_stop_posts=early_stop_posts,
    )


def _compute_stability_checks(runs: list[SweepRun]) -> list[StabilityCheck]:
    grouped: dict[tuple[str, str, int], list[SweepRun]] = {}
    for run in runs:
        key = (run.scenario_id, run.improve_mode, run.seed)
        grouped.setdefault(key, []).append(run)
    checks = [_compute_stability_for_group(group) for group in grouped.values()]
    checks.sort(key=lambda c: (c.scenario_id, c.improve_mode, c.seed))
    return checks


def _write_runs_flat_csv(path: Path, runs: list[SweepRun]) -> None:
    metric_keys: set[str] = set()
    maxima_keys: set[str] = set()
    for run in runs:
        metric_keys.update(run.metrics_extended.keys())
        maxima_keys.update(run.metrics_maxima.keys())
    metric_cols = [f"metric_{k}" for k in sorted(metric_keys)]
    maxima_cols = [f"max_{k}" for k in sorted(maxima_keys)]

    fields = [
        "scenario_id",
        "table1_ref",
        "table2_ref",
        "lambda_ref",
        "cap_default",
        "b",
        "draft_rounds",
        "seed",
        "post_iters",
        "move_type",
        "objective_scope",
        "improve_mode",
        "total_utility",
        "gini_total_norm",
        "gini_base_norm",
        "allocation_hash",
        "summary_signature",
        "post_log_len",
        "has_noop",
        "has_early_stop",
        "artifact_dir",
        "allocation_path",
        "post_allocation_path",
        "summary_path",
        "metrics_extended_path",
    ] + metric_cols + maxima_cols

    ordered = sorted(runs, key=lambda r: (r.scenario_id, r.improve_mode, r.seed, r.post_iters))
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for run in ordered:
            row = {
                "scenario_id": run.scenario_id,
                "table1_ref": run.table1_ref,
                "table2_ref": run.table2_ref,
                "lambda_ref": run.lambda_ref or "",
                "cap_default": run.cap_default,
                "b": run.b,
                "draft_rounds": run.draft_rounds,
                "seed": run.seed,
                "post_iters": run.post_iters,
                "move_type": run.move_type,
                "objective_scope": run.objective_scope,
                "improve_mode": run.improve_mode,
                "total_utility": f"{run.total_utility:.12f}",
                "gini_total_norm": f"{run.gini_total_norm:.12f}",
                "gini_base_norm": f"{run.gini_base_norm:.12f}",
                "allocation_hash": run.allocation_hash,
                "summary_signature": run.summary_signature,
                "post_log_len": run.post_log_len,
                "has_noop": int(run.has_noop),
                "has_early_stop": int(run.has_early_stop),
                "artifact_dir": run.artifact_dir,
                "allocation_path": run.allocation_path,
                "post_allocation_path": run.post_allocation_path,
                "summary_path": run.summary_path,
                "metrics_extended_path": run.metrics_extended_path,
            }
            for k in sorted(metric_keys):
                row[f"metric_{k}"] = f"{run.metrics_extended.get(k, 0.0):.12f}"
            for k in sorted(maxima_keys):
                row[f"max_{k}"] = f"{run.metrics_maxima.get(k, 0.0):.12f}"
            writer.writerow(row)


def _build_mode_post_agg_rows(runs: list[SweepRun]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int], list[SweepRun]] = {}
    for run in runs:
        key = (run.scenario_id, run.improve_mode, run.post_iters)
        grouped.setdefault(key, []).append(run)

    rows: list[dict[str, Any]] = []
    for (scenario_id, improve_mode, post_iters), group in grouped.items():
        u_vals = [run.total_utility for run in group]
        gt_vals = [run.gini_total_norm for run in group]
        gb_vals = [run.gini_base_norm for run in group]
        noop_rate = sum(1 for run in group if run.has_noop) / len(group)
        early_rate = sum(1 for run in group if run.has_early_stop) / len(group)

        u_mean, u_std, u_median = _metric_stats(u_vals)
        gt_mean, gt_std, gt_median = _metric_stats(gt_vals)
        gb_mean, gb_std, gb_median = _metric_stats(gb_vals)

        rows.append(
            {
                "scenario_id": scenario_id,
                "improve_mode": improve_mode,
                "post_iters": post_iters,
                "runs_count": len(group),
                "total_utility_mean": u_mean,
                "total_utility_std": u_std,
                "total_utility_median": u_median,
                "gini_total_norm_mean": gt_mean,
                "gini_total_norm_std": gt_std,
                "gini_total_norm_median": gt_median,
                "gini_base_norm_mean": gb_mean,
                "gini_base_norm_std": gb_std,
                "gini_base_norm_median": gb_median,
                "has_noop_rate": noop_rate,
                "has_early_stop_rate": early_rate,
            }
        )
    rows.sort(key=lambda r: (r["scenario_id"], r["improve_mode"], r["post_iters"]))
    return rows


def _write_mode_post_agg_csv(path: Path, runs: list[SweepRun]) -> None:
    rows = _build_mode_post_agg_rows(runs)
    fields = [
        "scenario_id",
        "improve_mode",
        "post_iters",
        "runs_count",
        "total_utility_mean",
        "total_utility_std",
        "total_utility_median",
        "gini_total_norm_mean",
        "gini_total_norm_std",
        "gini_total_norm_median",
        "gini_base_norm_mean",
        "gini_base_norm_std",
        "gini_base_norm_median",
        "has_noop_rate",
        "has_early_stop_rate",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            out = row.copy()
            for key in fields:
                value = out[key]
                if isinstance(value, float):
                    out[key] = f"{value:.12f}"
            writer.writerow(out)


def _write_stability_csv(path: Path, checks: list[StabilityCheck]) -> None:
    fields = [
        "scenario_id",
        "improve_mode",
        "seed",
        "max_post_iters",
        "stable_from_post",
        "all_equal",
        "classification",
        "no_op_posts",
        "early_stop_posts",
        "signatures_json",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for check in checks:
            writer.writerow(
                {
                    "scenario_id": check.scenario_id,
                    "improve_mode": check.improve_mode,
                    "seed": check.seed,
                    "max_post_iters": check.max_post_iters,
                    "stable_from_post": ("" if check.stable_from_post is None else check.stable_from_post),
                    "all_equal": int(check.all_equal),
                    "classification": check.classification,
                    "no_op_posts": ",".join(str(v) for v in check.no_op_posts),
                    "early_stop_posts": ",".join(str(v) for v in check.early_stop_posts),
                    "signatures_json": json.dumps(
                        {str(k): v for k, v in check.signatures_by_post.items()},
                        ensure_ascii=True,
                        sort_keys=True,
                    ),
                }
            )


def _persist_stability_checks(
    conn: sqlite3.Connection,
    *,
    experiment_id: int,
    checks: list[StabilityCheck],
) -> None:
    conn.execute("DELETE FROM stability_checks WHERE experiment_id = ?", (experiment_id,))
    for check in checks:
        conn.execute(
            """
            INSERT INTO stability_checks (
                experiment_id, created_at, scenario_id, improve_mode, seed,
                max_post_iters, stable_from_post, all_equal, classification,
                signatures_json, no_op_posts_json, early_stop_posts_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                _utc_now_iso(),
                check.scenario_id,
                check.improve_mode,
                check.seed,
                check.max_post_iters,
                check.stable_from_post,
                int(check.all_equal),
                check.classification,
                json.dumps({str(k): v for k, v in check.signatures_by_post.items()}, sort_keys=True),
                json.dumps(check.no_op_posts),
                json.dumps(check.early_stop_posts),
            ),
        )
    conn.commit()


def _build_report(
    *,
    out_path: Path,
    runs: list[SweepRun],
    checks: list[StabilityCheck],
    scenarios: list[Scenario],
    post_grid: list[int],
    modes: list[str],
    seed_start: int,
    seed_count: int,
) -> None:
    max_post = max(post_grid)
    lines: list[str] = []
    lines.append("# Experiment Report")
    lines.append("")
    lines.append(f"- generated_at_utc: `{_utc_now_iso()}`")
    lines.append(f"- total_runs: `{len(runs)}`")
    lines.append(f"- stability_groups: `{len(checks)}`")
    lines.append(
        f"- seeds: `{seed_start}..{seed_start + seed_count - 1}` | post_grid: `{','.join(str(v) for v in post_grid)}`"
    )
    lines.append(f"- modes: `{','.join(modes)}`")
    lines.append("")

    lines.append("## Top Modes Per Scenario (post=max)")
    lines.append("")
    for scenario in scenarios:
        scenario_runs = [
            run
            for run in runs
            if run.scenario_id == scenario.scenario_id and run.post_iters == max_post
        ]
        mode_groups: dict[str, list[SweepRun]] = {}
        for run in scenario_runs:
            mode_groups.setdefault(run.improve_mode, []).append(run)
        if not mode_groups:
            lines.append(f"- `{scenario.scenario_id}`: no runs.")
            continue

        utility_rank: list[tuple[str, float]] = []
        gtotal_rank: list[tuple[str, float]] = []
        gbase_rank: list[tuple[str, float]] = []
        for mode in sorted(mode_groups):
            group = mode_groups[mode]
            utility_rank.append((mode, statistics.fmean([r.total_utility for r in group])))
            gtotal_rank.append((mode, statistics.fmean([r.gini_total_norm for r in group])))
            gbase_rank.append((mode, statistics.fmean([r.gini_base_norm for r in group])))

        best_u_mode, best_u_value = max(utility_rank, key=lambda t: t[1])
        best_gt_mode, best_gt_value = min(gtotal_rank, key=lambda t: t[1])
        best_gb_mode, best_gb_value = min(gbase_rank, key=lambda t: t[1])

        lines.append(
            f"- `{scenario.scenario_id}`: "
            f"best_U=`{best_u_mode}` ({best_u_value:.6f}), "
            f"best_G_total=`{best_gt_mode}` ({best_gt_value:.6f}), "
            f"best_G_base=`{best_gb_mode}` ({best_gb_value:.6f})"
        )
    lines.append("")

    lines.append("## Stability Classification Share")
    lines.append("")
    for mode in modes:
        mode_checks = [check for check in checks if check.improve_mode == mode]
        total = len(mode_checks)
        if total == 0:
            lines.append(f"- `{mode}`: no checks.")
            continue
        counts: dict[str, int] = {}
        for check in mode_checks:
            counts[check.classification] = counts.get(check.classification, 0) + 1
        parts = [
            f"{classification}={count}/{total} ({(count / total) * 100:.1f}%)"
            for classification, count in sorted(counts.items())
        ]
        lines.append(f"- `{mode}`: " + ", ".join(parts))
    lines.append("")

    lines.append("## Hypothesis Check")
    lines.append("")
    adaptive_checks = [c for c in checks if c.improve_mode.startswith("hybrid-")]
    adaptive_early = [c for c in adaptive_checks if c.classification == "hybrid_early_stop"]
    nonglobal_checks = [
        c
        for c in checks
        if c.improve_mode.startswith("swap-") or c.improve_mode.startswith("drop-add-")
    ]
    nonglobal_tail = [
        c for c in nonglobal_checks if c.classification == "no_op_tail_without_break"
    ]
    if adaptive_checks:
        lines.append(
            "- hybrid modes with early-stop signature: "
            f"`{len(adaptive_early)}/{len(adaptive_checks)}` "
            f"({(len(adaptive_early) / len(adaptive_checks)) * 100:.1f}%)."
        )
    if nonglobal_checks:
        lines.append(
            "- swap/drop-add groups with no-op-tail signature: "
            f"`{len(nonglobal_tail)}/{len(nonglobal_checks)}` "
            f"({(len(nonglobal_tail) / len(nonglobal_checks)) * 100:.1f}%)."
        )
    lines.append(
        "- Interpretation: identical outcomes across larger `post_iters` appear when the system "
        "reaches a fixed point; hybrid modes stop early explicitly, while swap/drop-add can keep "
        "logging no-op iterations without changing allocation."
    )
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def run_experiment_suite(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    db_path: Path = DEFAULT_DB_PATH,
    seed_start: int = 11,
    seed_count: int = 10,
    post_grid: Iterable[int] = DEFAULT_POST_GRID,
    modes: Iterable[str] = DEFAULT_MODES,
    resume: bool = True,
    progress: bool = False,
    scenarios: Iterable[Scenario] = DEFAULT_SCENARIOS,
) -> SweepResult:
    if seed_count <= 0:
        raise ValueError("seed_count must be > 0")

    post_values = sorted(set(int(v) for v in post_grid))
    if not post_values:
        raise ValueError("post_grid cannot be empty")
    if any(v < 0 for v in post_values):
        raise ValueError("post_grid values must be >= 0")

    mode_values = [normalize_improve_mode(str(mode)) for mode in modes]
    if not mode_values:
        raise ValueError("modes cannot be empty")
    for mode in mode_values:
        if mode not in ALLOWED_MODES:
            allowed = ", ".join(sorted(ALLOWED_MODES))
            raise ValueError(f"Unsupported mode '{mode}'. Allowed: {allowed}")

    scenario_values = list(scenarios)
    if not scenario_values:
        raise ValueError("scenarios cannot be empty")
    for scenario in scenario_values:
        _ensure_scenario_files_exist(scenario)

    out_dir.mkdir(parents=True, exist_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path, timeout=30)
    try:
        _init_db(conn)
        experiment_id = _insert_experiment(
            conn,
            out_dir=out_dir,
            db_path=db_path,
            seed_start=seed_start,
            seed_count=seed_count,
            post_grid=post_values,
            modes=mode_values,
            scenarios=scenario_values,
            resume=resume,
        )

        total_planned = len(scenario_values) * len(mode_values) * seed_count * len(post_values)
        runs: list[SweepRun] = []
        executed = 0
        reused = 0
        done = 0

        for scenario in scenario_values:
            for mode in mode_values:
                for seed in range(seed_start, seed_start + seed_count):
                    for post_iters in post_values:
                        done += 1
                        if resume:
                            existing = _load_existing_run(
                                conn,
                                scenario_id=scenario.scenario_id,
                                seed=seed,
                                post_iters=post_iters,
                                improve_mode=mode,
                            )
                            if existing is not None:
                                runs.append(existing)
                                reused += 1
                                if progress:
                                    print(
                                        f"[{done}/{total_planned}] reuse "
                                        f"{scenario.scenario_id} {mode} seed={seed} post={post_iters}"
                                    )
                                continue
                        else:
                            _delete_existing_run(
                                conn,
                                scenario_id=scenario.scenario_id,
                                seed=seed,
                                post_iters=post_iters,
                                improve_mode=mode,
                            )

                        run, post_log = _run_single(
                            out_dir=out_dir,
                            scenario=scenario,
                            seed=seed,
                            post_iters=post_iters,
                            mode=mode,
                        )
                        run_id = _persist_run(
                            conn,
                            experiment_id=experiment_id,
                            run=run,
                            post_log=post_log,
                        )
                        run.run_id = run_id
                        runs.append(run)
                        executed += 1
                        if progress:
                            print(
                                f"[{done}/{total_planned}] run "
                                f"{scenario.scenario_id} {mode} seed={seed} post={post_iters}"
                            )

        checks = _compute_stability_checks(runs)
        _persist_stability_checks(conn, experiment_id=experiment_id, checks=checks)

        runs_flat_csv = out_dir / "runs_flat.csv"
        mode_post_agg_csv = out_dir / "mode_post_agg.csv"
        stability_csv = out_dir / "stability_by_seed.csv"
        report_md = out_dir / "report.md"

        _write_runs_flat_csv(runs_flat_csv, runs)
        _write_mode_post_agg_csv(mode_post_agg_csv, runs)
        _write_stability_csv(stability_csv, checks)
        _build_report(
            out_path=report_md,
            runs=runs,
            checks=checks,
            scenarios=scenario_values,
            post_grid=post_values,
            modes=mode_values,
            seed_start=seed_start,
            seed_count=seed_count,
        )

        return SweepResult(
            experiment_id=experiment_id,
            total_planned_runs=total_planned,
            total_runs_used=len(runs),
            runs_executed=executed,
            runs_reused=reused,
            db_path=db_path,
            runs_flat_csv=runs_flat_csv,
            mode_post_agg_csv=mode_post_agg_csv,
            stability_csv=stability_csv,
            report_md=report_md,
        )
    finally:
        conn.close()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Mass benchmark sweep for HBS social course allocation.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    p.add_argument("--seed-start", type=int, default=11)
    p.add_argument("--seed-count", type=int, default=10)
    p.add_argument("--post-grid", type=str, default="0,1,5,10,20")
    p.add_argument(
        "--modes",
        type=str,
        default=(
            "swap-global,swap-personal,drop-add-global,"
            "drop-add-personal,hybrid-global,hybrid-personal"
        ),
        help="Comma-separated list of modes.",
    )
    p.add_argument(
        "--resume",
        dest="resume",
        action="store_true",
        default=True,
        help="Reuse existing runs from DB if present.",
    )
    p.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
        help="Recompute runs and overwrite DB rows for matching keys.",
    )
    p.add_argument("--progress", action="store_true", help="Print sweep progress.")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    post_grid = _parse_post_grid(args.post_grid)
    modes = _parse_modes(args.modes)

    result = run_experiment_suite(
        out_dir=args.out_dir,
        db_path=args.db_path,
        seed_start=args.seed_start,
        seed_count=args.seed_count,
        post_grid=post_grid,
        modes=modes,
        resume=args.resume,
        progress=args.progress,
    )

    print(
        "Completed experiment "
        f"id={result.experiment_id}, runs={result.total_runs_used} "
        f"(executed={result.runs_executed}, reused={result.runs_reused})"
    )
    print(f"DB: {result.db_path}")
    print(f"runs_flat: {result.runs_flat_csv}")
    print(f"mode_post_agg: {result.mode_post_agg_csv}")
    print(f"stability: {result.stability_csv}")
    print(f"report: {result.report_md}")
    return 0


__all__ = [
    "DEFAULT_SCENARIOS",
    "Scenario",
    "SweepResult",
    "run_experiment_suite",
    "main",
    "_allocation_hash",
    "_canonical_allocation_json",
    "_compute_stability_for_group",
]
