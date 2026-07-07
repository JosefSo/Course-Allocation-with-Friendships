from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import random
import sqlite3
import tempfile
import threading
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from generate.generate_tables import (
    _default_table_paths,
    _ensure_parent_dirs,
    _validate_table_1,
    _validate_table_2,
    _write_csv_table_1,
    _write_csv_table_2,
    _write_csv_table_3,
    generate_table_1,
    generate_table_2,
    generate_table_3,
)
from .hbs_api import CANONICAL_IMPROVE_MODES, normalize_improvement_config, run_hbs_social
from .hbs_domain import PickLogRow, PostAllocLogRow
from .hbs_io import (
    _read_table_1,
    _read_table_2,
    _write_allocation_csv,
    _write_metrics_extended_csv,
    _write_post_alloc_csv,
    _write_summary_csv,
)

LOG = logging.getLogger(__name__)
UI_PATH = Path(__file__).resolve().parents[1] / "hbs_web_ui.html"
TABLES_DIR = Path(__file__).resolve().parents[1] / "tables"
HISTORY_DB_PATH = Path(__file__).resolve().parents[1] / "results" / "hbs_social_web_history.sqlite3"
PRESENTATION_ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "results" / "presentation_artifacts"
EXPERIMENTS_DIR = Path(__file__).resolve().parents[1] / "results" / "experiments"
_COMPARE_PROGRESS: dict[str, dict[str, Any]] = {}
_COMPARE_PROGRESS_LOCK = threading.Lock()

HISTORY_METRIC_KEYS = (
    "total_utility",
    "total_utility_norm",
    "total_base_utility",
    "total_friend_utility_norm",
    "total_friend_utility_raw",
    "mean_base_assigned",
    "mean_friend_norm_assigned",
    "friend_norm_base_ratio_mean",
    "avg_friend_overlaps_per_student",
    "friend_overlap_total",
    "friend_possible_overlap_total",
    "overlap_rate",
    "share_students_with_any_friend_overlap",
    "gini_total_raw",
    "gini_total_norm",
    "gini_base_raw",
    "gini_base_norm",
    "gini_friend_norm",
    "gini_friend_opportunity_norm",
    "jain_index",
    "egalitarian_welfare",
    "nash_welfare_geomean",
    "zero_utility_share",
    "nash_zero_safe",
    "ef1_violation_pair_share_substitution_combined",
    "ef1_violation_student_share_substitution_combined",
    "avg_position",
    "share_top1",
    "share_top3",
)

HISTORY_MIN_METRIC_KEYS = (
    "gini_total_norm",
    "gini_base_norm",
    "gini_friend_norm",
    "gini_friend_opportunity_norm",
    "avg_position",
)

HISTORY_MAX_METRIC_KEYS = (
    "total_utility",
    "total_utility_norm",
    "total_base_utility",
    "total_friend_utility_norm",
    "avg_friend_overlaps_per_student",
    "share_students_with_any_friend_overlap",
    "jain_index",
    "share_top1",
    "share_top3",
)


def _to_int(payload: dict[str, Any], key: str, default: int | None = None) -> int:
    raw = payload.get(key, default)
    if raw is None:
        raise ValueError(f"{key} is required")
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer") from exc


def _optional_int(payload: dict[str, Any], key: str) -> int | None:
    if key not in payload:
        return None
    raw = payload[key]
    if raw is None:
        return None
    if isinstance(raw, str) and raw.strip() == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer or null") from exc


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    if key not in payload:
        return None
    raw = payload[key]
    if raw is None:
        return None
    text = str(raw).strip()
    if text == "":
        return None
    return text


def _to_float(payload: dict[str, Any], key: str, default: float | None = None) -> float:
    raw = payload.get(key, default)
    if raw is None:
        raise ValueError(f"{key} is required")
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a number") from exc


def _to_bool(payload: dict[str, Any], key: str, default: bool = False) -> bool:
    raw = payload.get(key, default)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        lowered = raw.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off", ""}:
            return False
    if isinstance(raw, int):
        return bool(raw)
    raise ValueError(f"{key} must be a boolean")


def _to_csv_text(payload: dict[str, Any], key: str, required: bool) -> str | None:
    raw = payload.get(key)
    if raw is None:
        if required:
            raise ValueError(f"{key} is required")
        return None
    if not isinstance(raw, str):
        raise ValueError(f"{key} must be a string")
    text = raw.strip()
    if text == "":
        if required:
            raise ValueError(f"{key} cannot be empty")
        return None
    return text + "\n"


def _resolve_table_file(rel_path: str) -> Path:
    if not isinstance(rel_path, str):
        raise ValueError("table file path must be a string")
    cleaned = rel_path.strip()
    if cleaned == "":
        raise ValueError("table file path cannot be empty")

    candidate = (TABLES_DIR / cleaned).resolve()
    base = TABLES_DIR.resolve()
    if base != candidate and base not in candidate.parents:
        raise ValueError(f"table file path is outside tables directory: {cleaned}")
    if not candidate.exists() or not candidate.is_file():
        raise ValueError(f"table file not found: {cleaned}")
    if candidate.suffix.lower() != ".csv":
        raise ValueError(f"table file must be CSV: {cleaned}")
    return candidate


def _read_csv_from_payload(
    payload: dict[str, Any],
    *,
    text_key: str,
    file_key: str,
    required: bool,
) -> str | None:
    file_raw = payload.get(file_key)
    if file_raw is not None and str(file_raw).strip() != "":
        file_path = _resolve_table_file(str(file_raw))
        text = file_path.read_text(encoding="utf-8").strip()
        if text == "":
            if required:
                raise ValueError(f"{file_key} points to an empty file")
            return None
        return text + "\n"
    return _to_csv_text(payload, text_key, required=required)


def _list_table_files() -> dict[str, Any]:
    if not TABLES_DIR.exists():
        return {
            "ok": True,
            "tables_dir": str(TABLES_DIR),
            "all": [],
            "table1": [],
            "table2": [],
            "lambda": [],
        }

    files = sorted(
        str(path.relative_to(TABLES_DIR))
        for path in TABLES_DIR.rglob("*.csv")
        if path.is_file()
    )
    table1_files: list[str] = []
    table2_files: list[str] = []
    lambda_files: list[str] = []
    for rel in files:
        lowered = rel.lower()
        if lowered.startswith("table1"):
            table1_files.append(rel)
        elif lowered.startswith("table2"):
            table2_files.append(rel)
        elif lowered.startswith("table3") or "lambda" in lowered:
            lambda_files.append(rel)

    return {
        "ok": True,
        "tables_dir": str(TABLES_DIR),
        "all": files,
        "table1": table1_files,
        "table2": table2_files,
        "lambda": lambda_files,
    }


def _coerce_artifact_value(raw: str | None) -> Any:
    if raw is None:
        return None
    text = str(raw).strip()
    if text == "":
        return ""
    try:
        value = float(text)
    except ValueError:
        return text
    if math.isfinite(value):
        return value
    return text


def _read_artifact_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows: list[dict[str, Any]] = []
        for row in reader:
            rows.append({str(key): _coerce_artifact_value(value) for key, value in row.items()})
    return rows


def _load_presentation_artifacts() -> dict[str, Any]:
    artifacts = {
        "lambda_tradeoff": _read_artifact_csv(PRESENTATION_ARTIFACTS_DIR / "lambda_tradeoff.csv"),
        "mode_family_comparison": _read_artifact_csv(
            PRESENTATION_ARTIFACTS_DIR / "mode_family_comparison.csv"
        ),
        "global_vs_personal": _read_artifact_csv(
            PRESENTATION_ARTIFACTS_DIR / "global_vs_personal.csv"
        ),
        "raw_runs": _read_artifact_csv(PRESENTATION_ARTIFACTS_DIR / "raw_runs.csv"),
        "post_iters": _read_artifact_csv(EXPERIMENTS_DIR / "A_200x8_mode_post_agg_partial.csv"),
        "stability": _read_artifact_csv(EXPERIMENTS_DIR / "A_200x8_stability_partial.csv"),
    }
    return {
        "ok": True,
        "artifacts_dir": str(PRESENTATION_ARTIFACTS_DIR),
        "experiments_dir": str(EXPERIMENTS_DIR),
        **artifacts,
    }


def _table_path_in_tables_dir(default_path: Path) -> Path:
    return TABLES_DIR / default_path.name


def _summarize_lambda_rows(rows: list[Any]) -> dict[str, Any]:
    values = [float(row.lambda_friend) for row in rows]
    unique_values = sorted({round(value, 3) for value in values})
    sample = [f"{value:.3f}" for value in unique_values[:10]]
    return {
        "count": len(values),
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "unique_count": len(unique_values),
        "sample_values": sample,
    }


def _generate_tables_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object")

    n_students = _to_int(payload, "students")
    n_courses = _to_int(payload, "courses")
    if n_students <= 0:
        raise ValueError("students must be > 0")
    if n_courses <= 0:
        raise ValueError("courses must be > 0")

    generate_table1 = _to_bool(payload, "generate_table1", True)
    generate_table2 = _to_bool(payload, "generate_table2", True)
    generate_lambda = _to_bool(payload, "generate_lambda", True)
    if not (generate_table1 or generate_table2 or generate_lambda):
        raise ValueError("Select at least one table to generate")

    seed = payload.get("seed")
    if seed is not None and str(seed).strip() != "":
        seed = _to_int(payload, "seed")
    else:
        seed = None
    score_min = _to_int(payload, "score_min", default=1)
    score_max = _to_int(payload, "score_max", default=5)
    if score_min >= score_max:
        raise ValueError("score_min must be less than score_max")
    swap_prob = _to_float(payload, "swap_prob", default=0.0)
    if not (0.0 <= swap_prob <= 1.0):
        raise ValueError("swap_prob must be in range 0..1")

    friend_top_k = _to_int(payload, "friend_top_k", default=3)
    if friend_top_k <= 0:
        raise ValueError("friend_top_k must be > 0")
    friend_score_min = payload.get("friend_score_min")
    friend_score_min = (
        score_min
        if friend_score_min is None or str(friend_score_min).strip() == ""
        else _to_int(payload, "friend_score_min")
    )
    friend_score_max = payload.get("friend_score_max")
    friend_score_max = (
        score_max
        if friend_score_max is None or str(friend_score_max).strip() == ""
        else _to_int(payload, "friend_score_max")
    )
    if friend_score_min >= friend_score_max:
        raise ValueError("friend_score_min must be less than friend_score_max")
    friend_score_mode = str(payload.get("friend_score_mode", "score_first")).strip()
    if friend_score_mode not in {"score_first", "position_first"}:
        raise ValueError("friend_score_mode must be score_first or position_first")
    friend_swap_prob = _to_float(payload, "friend_swap_prob", default=0.0)
    if not (0.0 <= friend_swap_prob <= 1.0):
        raise ValueError("friend_swap_prob must be in range 0..1")

    lambda_default_raw = payload.get("lambda_default")
    if lambda_default_raw is None or str(lambda_default_raw).strip() == "":
        lambda_default = None
    else:
        lambda_default = _to_float(payload, "lambda_default")
        if not (0.0 <= lambda_default <= 1.0):
            raise ValueError("lambda_default must be in range 0..1")

    student_ids = [f"S{i}" for i in range(1, n_students + 1)]
    course_ids = [f"C{i}" for i in range(1, n_courses + 1)]
    rng = random.Random(seed)
    default_out1, default_out2, default_out3 = _default_table_paths(
        n_students,
        n_courses,
        lambda_default=lambda_default,
    )
    out1 = _table_path_in_tables_dir(default_out1)
    out2 = _table_path_in_tables_dir(default_out2)
    out3 = _table_path_in_tables_dir(default_out3)
    created: dict[str, str] = {}
    lambda_info: dict[str, Any] | None = None

    if generate_table1:
        table1 = generate_table_1(
            student_ids,
            course_ids,
            rng,
            score_min=score_min,
            score_max=score_max,
            swap_prob=swap_prob,
        )
        _validate_table_1(
            table1,
            n_courses=len(course_ids),
            score_min=score_min,
            score_max=score_max,
        )
        _ensure_parent_dirs(out1)
        _write_csv_table_1(out1, table1)
        created["table1"] = out1.name

    if generate_table2:
        table2 = generate_table_2(
            student_ids,
            course_ids,
            rng,
            top_k=friend_top_k,
            score_min=friend_score_min,
            score_max=friend_score_max,
            score_mode=friend_score_mode,
            swap_prob=friend_swap_prob,
        )
        _validate_table_2(
            table2,
            top_k=friend_top_k,
            score_min=friend_score_min,
            score_max=friend_score_max,
        )
        _ensure_parent_dirs(out2)
        _write_csv_table_2(out2, table2)
        created["table2"] = out2.name

    if generate_lambda:
        table3 = generate_table_3(
            student_ids,
            lambda_default=lambda_default,
            rng=rng,
        )
        _ensure_parent_dirs(out3)
        _write_csv_table_3(out3, table3)
        created["lambda"] = out3.name
        lambda_info = {
            "mode": ("random" if lambda_default is None else "constant"),
            "requested_default": lambda_default,
            "file": out3.name,
            "summary": _summarize_lambda_rows(table3),
        }

    return {
        "ok": True,
        "tables_dir": str(TABLES_DIR),
        "created": created,
        "lambda_info": lambda_info,
        "files": _list_table_files(),
    }


def _resolve_history_db_path(db_path: Path | None) -> Path:
    return HISTORY_DB_PATH if db_path is None else db_path


def _init_history_db(db_path: Path | None = None) -> None:
    db_path = _resolve_history_db_path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path, timeout=5) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS run_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                table1_ref TEXT NOT NULL,
                table2_ref TEXT NOT NULL,
                lambda_ref TEXT,
                cap_default INTEGER NOT NULL,
                b INTEGER NOT NULL,
                seed INTEGER NOT NULL,
                draft_rounds INTEGER NOT NULL,
                post_iters INTEGER NOT NULL,
                move_type TEXT,
                objective_scope TEXT,
                improve_mode TEXT NOT NULL,
                total_utility REAL NOT NULL,
                gini_total_norm REAL NOT NULL,
                gini_base_norm REAL NOT NULL,
                metrics_extended_json TEXT
            )
            """
        )
        columns = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(run_history)").fetchall()
        }
        if "move_type" not in columns:
            conn.execute("ALTER TABLE run_history ADD COLUMN move_type TEXT")
        if "objective_scope" not in columns:
            conn.execute("ALTER TABLE run_history ADD COLUMN objective_scope TEXT")
        if "metrics_extended_json" not in columns:
            conn.execute("ALTER TABLE run_history ADD COLUMN metrics_extended_json TEXT")
        rows_to_backfill = conn.execute(
            """
            SELECT id, improve_mode
            FROM run_history
            WHERE move_type IS NULL OR objective_scope IS NULL
            """
        ).fetchall()
        for row_id, improve_mode in rows_to_backfill:
            move_type, objective_scope, effective_mode = normalize_improvement_config(
                improve_mode=str(improve_mode)
            )
            conn.execute(
                """
                UPDATE run_history
                SET move_type = ?, objective_scope = ?, improve_mode = ?
                WHERE id = ?
                """,
                (move_type, objective_scope, effective_mode, int(row_id)),
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_run_history_created_at ON run_history(created_at DESC)"
        )
        conn.commit()


def _history_ref(payload: dict[str, Any], file_key: str) -> str | None:
    raw = payload.get(file_key)
    if raw is None:
        return None
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip()
    if cleaned == "":
        return None
    return cleaned


def _append_run_history(
    *,
    table1_ref: str,
    table2_ref: str,
    lambda_ref: str | None,
    cap_default: int,
    b: int,
    seed: int,
    draft_rounds: int,
    post_iters: int,
    move_type: str,
    objective_scope: str,
    improve_mode: str,
    total_utility: float,
    gini_total_norm: float,
    gini_base_norm: float,
    metrics_extended: dict[str, float] | None = None,
    db_path: Path | None = None,
) -> int:
    db_path = _resolve_history_db_path(db_path)
    _init_history_db(db_path)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with sqlite3.connect(db_path, timeout=5) as conn:
        cursor = conn.execute(
            """
            INSERT INTO run_history (
                created_at, table1_ref, table2_ref, lambda_ref, cap_default, b, seed,
                draft_rounds, post_iters, move_type, objective_scope, improve_mode,
                total_utility, gini_total_norm, gini_base_norm, metrics_extended_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                table1_ref,
                table2_ref,
                lambda_ref,
                cap_default,
                b,
                seed,
                draft_rounds,
                post_iters,
                move_type,
                objective_scope,
                improve_mode,
                total_utility,
                gini_total_norm,
                gini_base_norm,
                json.dumps(metrics_extended or {}, ensure_ascii=True, sort_keys=True),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def _list_run_history(limit: int = 200, db_path: Path | None = None) -> dict[str, Any]:
    db_path = _resolve_history_db_path(db_path)
    if limit <= 0:
        raise ValueError("limit must be > 0")
    safe_limit = min(limit, 1000)
    _init_history_db(db_path)
    with sqlite3.connect(db_path, timeout=5) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                id, created_at, table1_ref, table2_ref, lambda_ref,
                cap_default, b, seed, draft_rounds, post_iters, move_type, objective_scope,
                improve_mode,
                total_utility, gini_total_norm, gini_base_norm, metrics_extended_json
            FROM run_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        lambda_part = f", lambda={row['lambda_ref']}" if row["lambda_ref"] else ""
        summary_line = (
            f"tables: {row['table1_ref']}, {row['table2_ref']}{lambda_part} | "
            f"params: cap={row['cap_default']}, b={row['b']}, seed={row['seed']}, "
            f"draft={row['draft_rounds']}, post={row['post_iters']}, mode={row['improve_mode']} | "
            f"metrics: U={row['total_utility']:.6f}, "
            f"G_total={row['gini_total_norm']:.6f}, G_base={row['gini_base_norm']:.6f}"
        )
        metrics = _history_metrics_from_row(row)
        items.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "table1_ref": row["table1_ref"],
                "table2_ref": row["table2_ref"],
                "lambda_ref": row["lambda_ref"],
                "cap_default": row["cap_default"],
                "b": row["b"],
                "seed": row["seed"],
                "draft_rounds": row["draft_rounds"],
                "post_iters": row["post_iters"],
                "move_type": row["move_type"],
                "objective_scope": row["objective_scope"],
                "improve_mode": row["improve_mode"],
                "total_utility": row["total_utility"],
                "gini_total_norm": row["gini_total_norm"],
                "gini_base_norm": row["gini_base_norm"],
                "metrics_extended": metrics,
                "summary_line": summary_line,
            }
        )

    return {
        "ok": True,
        "items": items,
    }


def _build_run_history_stats(limit: int = 200, db_path: Path | None = None) -> dict[str, Any]:
    db_path = _resolve_history_db_path(db_path)
    if limit <= 0:
        raise ValueError("limit must be > 0")
    safe_limit = min(limit, 1000)
    _init_history_db(db_path)
    with sqlite3.connect(db_path, timeout=5) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                id, move_type, objective_scope, improve_mode,
                total_utility, gini_total_norm, gini_base_norm, metrics_extended_json
            FROM (
                SELECT
                    id, move_type, objective_scope, improve_mode,
                    total_utility, gini_total_norm, gini_base_norm, metrics_extended_json
                FROM run_history
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id ASC
            """,
            (safe_limit,),
        ).fetchall()

    trend: list[dict[str, Any]] = []
    mode_acc: dict[str, dict[str, Any]] = {}

    best_utility: dict[str, Any] | None = None
    best_fairness_g_total: dict[str, Any] | None = None
    best_fairness_g_base: dict[str, Any] | None = None

    for idx, row in enumerate(rows, start=1):
        run_id = int(row["id"])
        move_type = str(row["move_type"]) if row["move_type"] is not None else ""
        objective_scope = (
            str(row["objective_scope"]) if row["objective_scope"] is not None else ""
        )
        mode = str(row["improve_mode"])
        total_utility = float(row["total_utility"])
        gini_total_norm = float(row["gini_total_norm"])
        gini_base_norm = float(row["gini_base_norm"])
        metrics = _history_metrics_from_row(row)

        trend_point = {
            "run_index": idx,
            "id": run_id,
            "move_type": move_type,
            "objective_scope": objective_scope,
            "improve_mode": mode,
        }
        for key in HISTORY_METRIC_KEYS:
            if key in metrics:
                trend_point[key] = metrics[key]
        trend.append(trend_point)

        if mode not in mode_acc:
            mode_acc[mode] = {
                "improve_mode": mode,
                "move_type": move_type,
                "objective_scope": objective_scope,
                "runs": 0,
            }
            for key in HISTORY_METRIC_KEYS:
                mode_acc[mode][f"sum_{key}"] = 0.0
                mode_acc[mode][f"count_{key}"] = 0
            for key in HISTORY_MAX_METRIC_KEYS:
                mode_acc[mode][f"best_{key}"] = None
            for key in HISTORY_MIN_METRIC_KEYS:
                mode_acc[mode][f"min_{key}"] = None
        bucket = mode_acc[mode]
        bucket["runs"] += 1
        for key in HISTORY_METRIC_KEYS:
            value = metrics.get(key)
            if value is None or not math.isfinite(value):
                continue
            bucket[f"sum_{key}"] += value
            bucket[f"count_{key}"] += 1
        for key in HISTORY_MAX_METRIC_KEYS:
            value = metrics.get(key)
            if value is None or not math.isfinite(value):
                continue
            current = bucket[f"best_{key}"]
            bucket[f"best_{key}"] = value if current is None else max(float(current), value)
        for key in HISTORY_MIN_METRIC_KEYS:
            value = metrics.get(key)
            if value is None or not math.isfinite(value):
                continue
            current = bucket[f"min_{key}"]
            bucket[f"min_{key}"] = value if current is None else min(float(current), value)

        utility_candidate = {
            "run_index": idx,
            "id": run_id,
            "move_type": move_type,
            "objective_scope": objective_scope,
            "improve_mode": mode,
            "value": total_utility,
        }
        if best_utility is None or utility_candidate["value"] > best_utility["value"]:
            best_utility = utility_candidate

        fairness_total_candidate = {
            "run_index": idx,
            "id": run_id,
            "move_type": move_type,
            "objective_scope": objective_scope,
            "improve_mode": mode,
            "value": gini_total_norm,
        }
        if (
            best_fairness_g_total is None
            or fairness_total_candidate["value"] < best_fairness_g_total["value"]
        ):
            best_fairness_g_total = fairness_total_candidate

        fairness_base_candidate = {
            "run_index": idx,
            "id": run_id,
            "move_type": move_type,
            "objective_scope": objective_scope,
            "improve_mode": mode,
            "value": gini_base_norm,
        }
        if (
            best_fairness_g_base is None
            or fairness_base_candidate["value"] < best_fairness_g_base["value"]
        ):
            best_fairness_g_base = fairness_base_candidate

    by_mode: list[dict[str, Any]] = []
    for mode in sorted(mode_acc.keys()):
        bucket = mode_acc[mode]
        runs = int(bucket["runs"])
        by_mode.append(
            {
                "improve_mode": mode,
                "move_type": str(bucket["move_type"]),
                "objective_scope": str(bucket["objective_scope"]),
                "runs": runs,
            }
        )
        out = by_mode[-1]
        for key in HISTORY_METRIC_KEYS:
            count = int(bucket.get(f"count_{key}", 0))
            out[f"avg_{key}"] = (
                float(bucket[f"sum_{key}"]) / count if count > 0 else None
            )
        for key in HISTORY_MAX_METRIC_KEYS:
            out[f"best_{key}"] = bucket.get(f"best_{key}")
        for key in HISTORY_MIN_METRIC_KEYS:
            out[f"min_{key}"] = bucket.get(f"min_{key}")

    return {
        "ok": True,
        "trend": trend,
        "by_mode": by_mode,
        "overall": {
            "runs_total": len(trend),
            "best_utility": best_utility,
            "best_fairness_g_total": best_fairness_g_total,
            "best_fairness_g_base": best_fairness_g_base,
        },
    }


def _reset_run_history(db_path: Path | None = None) -> dict[str, Any]:
    db_path = _resolve_history_db_path(db_path)
    if db_path.exists():
        db_path.unlink()
    _init_history_db(db_path)
    return {
        "ok": True,
        "items": [],
    }


def _serialize_pick_log(rows: list[PickLogRow]) -> list[dict[str, Any]]:
    return [asdict(row) for row in rows]


def _serialize_post_log(rows: list[PostAllocLogRow]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        item = asdict(row)
        if item["dropped_courses"] is not None:
            item["dropped_courses"] = list(item["dropped_courses"])
        if item["added_courses"] is not None:
            item["added_courses"] = list(item["added_courses"])
        out.append(item)
    return out


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stddev(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    mean = _mean(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def _history_metrics_from_row(row: sqlite3.Row) -> dict[str, float]:
    metrics: dict[str, float] = {}
    raw_metrics = row["metrics_extended_json"] if "metrics_extended_json" in row.keys() else None
    if raw_metrics:
        try:
            loaded = json.loads(str(raw_metrics))
        except json.JSONDecodeError:
            loaded = {}
        if isinstance(loaded, dict):
            for key, value in loaded.items():
                try:
                    metrics[str(key)] = float(value)
                except (TypeError, ValueError):
                    continue

    # Backward-compatible fallbacks for history rows saved before extended metrics existed.
    metrics.setdefault("total_utility", float(row["total_utility"]))
    metrics.setdefault("gini_total_norm", float(row["gini_total_norm"]))
    metrics.setdefault("gini_base_norm", float(row["gini_base_norm"]))
    return metrics


def _run_mode_comparison_task(task: dict[str, Any]) -> dict[str, Any]:
    result = run_hbs_social(
        Path(str(task["csv_a"])),
        Path(str(task["csv_b"])),
        csv_lambda=(Path(str(task["csv_lambda"])) if task["csv_lambda"] is not None else None),
        cap_default=int(task["cap_default"]),
        b=int(task["b"]),
        draft_rounds=task["draft_rounds"],
        post_iters=int(task["post_iters"]),
        improve_mode=str(task["improve_mode"]),
        initial_method=str(task.get("initial_method", "sequential")),
        sequence=str(task.get("sequence", "snake")),
        pick_rule=str(task.get("pick_rule", "personal")),
        seed=int(task["seed"]),
        progress=False,
        sanity_checks=False,
        delta_check_every=0,
    )
    return {
        "improve_mode": str(task["improve_mode"]),
        "seed": int(task["seed"]),
        "post_iters": int(task["post_iters"]),
        "total_utility": float(result.summary.total_utility),
        "gini_total_norm": float(result.summary.gini_total_norm),
        "gini_base_norm": float(result.summary.gini_base_norm),
        "metrics_extended": result.metrics_extended.values,
    }


def _write_worker_progress(
    progress_dir: Path,
    *,
    worker_id: int,
    total: int,
    completed: int,
    status: str,
) -> None:
    payload = {
        "worker_id": worker_id,
        "total": total,
        "completed": completed,
        "status": status,
    }
    target = progress_dir / f"worker_{worker_id}.json"
    tmp = progress_dir / f"worker_{worker_id}.json.tmp"
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(target)


def _run_mode_comparison_chunk(chunk: dict[str, Any]) -> list[dict[str, Any]]:
    worker_id = int(chunk["worker_id"])
    tasks = list(chunk["tasks"])
    progress_dir_raw = chunk.get("progress_dir")
    progress_dir = Path(str(progress_dir_raw)) if progress_dir_raw is not None else None
    total = len(tasks)
    results: list[dict[str, Any]] = []
    if progress_dir is not None:
        _write_worker_progress(
            progress_dir,
            worker_id=worker_id,
            total=total,
            completed=0,
            status=("done" if total == 0 else "running"),
        )
    for idx, task in enumerate(tasks, start=1):
        results.append(_run_mode_comparison_task(task))
        if progress_dir is not None:
            _write_worker_progress(
                progress_dir,
                worker_id=worker_id,
                total=total,
                completed=idx,
                status=("done" if idx == total else "running"),
            )
    return results


def _run_mode_comparison_tasks(
    chunks: list[dict[str, Any]],
    *,
    parallel_workers: int,
) -> tuple[list[dict[str, Any]], int, str | None]:
    try:
        with ProcessPoolExecutor(max_workers=parallel_workers) as executor:
            results: list[dict[str, Any]] = []
            for chunk_results in executor.map(_run_mode_comparison_chunk, chunks):
                results.extend(chunk_results)
            return results, parallel_workers, None
    except PermissionError as exc:
        LOG.debug("Parallel mode comparison blocked by the environment: %s", exc)
        results = []
        for chunk in chunks:
            results.extend(_run_mode_comparison_chunk(chunk))
        return results, 1, str(exc)


def _normalize_progress_job_id(raw_job_id: Any) -> str:
    job_id = str(raw_job_id or "").strip()
    if job_id == "":
        raise ValueError("progress_job_id is required")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    if any(ch not in allowed for ch in job_id):
        raise ValueError("progress_job_id may contain only letters, digits, _ and -")
    return job_id[:80]


def _read_compare_progress(job_id: str) -> dict[str, Any]:
    with _COMPARE_PROGRESS_LOCK:
        state = dict(_COMPARE_PROGRESS.get(job_id) or {})
    if not state:
        return {"ok": False, "error": "Progress job not found"}

    workers = state.get("workers")
    progress_dir_raw = state.get("progress_dir")
    if workers is None and progress_dir_raw is not None:
        progress_dir = Path(str(progress_dir_raw))
        workers = []
        for worker_id in range(1, int(state.get("worker_count", 0)) + 1):
            path = progress_dir / f"worker_{worker_id}.json"
            if path.exists():
                try:
                    workers.append(json.loads(path.read_text(encoding="utf-8")))
                    continue
                except json.JSONDecodeError:
                    pass
            workers.append(
                {
                    "worker_id": worker_id,
                    "total": int(state.get("worker_totals", {}).get(worker_id, 0)),
                    "completed": 0,
                    "status": "queued",
                }
            )

    workers = list(workers or [])
    total = sum(int(worker.get("total", 0)) for worker in workers)
    completed = sum(int(worker.get("completed", 0)) for worker in workers)
    return {
        "ok": True,
        "job_id": job_id,
        "status": state.get("status", "running"),
        "workers": workers,
        "total": total,
        "completed": completed,
    }


def _run_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object")

    table1_csv = _read_csv_from_payload(
        payload,
        text_key="table1_csv",
        file_key="table1_file",
        required=True,
    )
    table2_csv = _read_csv_from_payload(
        payload,
        text_key="table2_csv",
        file_key="table2_file",
        required=True,
    )
    table_lambda_csv = _read_csv_from_payload(
        payload,
        text_key="lambda_csv",
        file_key="lambda_file",
        required=False,
    )

    cap_default = _to_int(payload, "cap_default", default=10)
    b = _to_int(payload, "b", default=3)
    seed = _to_int(payload, "seed", default=42)
    draft_rounds = _optional_int(payload, "draft_rounds")
    post_iters = _to_int(payload, "post_iters", default=0)
    initial_method = str(payload.get("initial_method", "sequential"))
    sequence = str(payload.get("sequence", "snake"))
    pick_rule = str(payload.get("pick_rule", "personal"))
    raw_improve_mode = _optional_str(payload, "improve_mode")
    raw_move_type = _optional_str(payload, "move_type")
    raw_objective_scope = _optional_str(payload, "objective_scope")
    move_type, objective_scope, improve_mode = normalize_improvement_config(
        improve_mode=raw_improve_mode,
        move_type=raw_move_type,
        objective_scope=raw_objective_scope,
    )
    table1_ref = _history_ref(payload, "table1_file") or "[inline-table1]"
    table2_ref = _history_ref(payload, "table2_file") or "[inline-table2]"
    lambda_ref = _history_ref(payload, "lambda_file")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        csv_a = tmp_dir / "table1.csv"
        csv_b = tmp_dir / "table2.csv"
        csv_lambda: Path | None = None
        csv_a.write_text(table1_csv, encoding="utf-8")
        csv_b.write_text(table2_csv, encoding="utf-8")

        if table_lambda_csv is not None:
            csv_lambda = tmp_dir / "lambda.csv"
            csv_lambda.write_text(table_lambda_csv, encoding="utf-8")

        result = run_hbs_social(
            csv_a,
            csv_b,
            csv_lambda=csv_lambda,
            cap_default=cap_default,
            b=b,
            draft_rounds=draft_rounds,
            post_iters=post_iters,
            improve_mode=raw_improve_mode,
            move_type=move_type,
            objective_scope=objective_scope,
            initial_method=initial_method,
            sequence=sequence,
            pick_rule=pick_rule,
            seed=seed,
            progress=False,
            sanity_checks=False,
            delta_check_every=0,
        )

        allocation_path = tmp_dir / "allocation.csv"
        post_path = tmp_dir / "post_allocation.csv"
        summary_path = tmp_dir / "summary.csv"
        metrics_path = tmp_dir / "metrics_extended.csv"
        resolved_draft_rounds = b if draft_rounds is None else draft_rounds

        _write_allocation_csv(allocation_path, pick_log=result.pick_log)
        _write_post_alloc_csv(post_path, post_log=result.post_log)
        _write_summary_csv(
            summary_path,
            seed=seed,
            cap_default=cap_default,
            b=b,
            draft_rounds=resolved_draft_rounds,
            post_iters=post_iters,
            summary=result.summary,
        )
        _write_metrics_extended_csv(metrics_path, metrics=result.metrics_extended)
        history_id = _append_run_history(
            table1_ref=table1_ref,
            table2_ref=table2_ref,
            lambda_ref=lambda_ref,
            cap_default=cap_default,
            b=b,
            seed=seed,
            draft_rounds=resolved_draft_rounds,
            post_iters=post_iters,
            move_type=move_type,
            objective_scope=objective_scope,
            improve_mode=improve_mode,
            total_utility=result.summary.total_utility,
            gini_total_norm=result.summary.gini_total_norm,
            gini_base_norm=result.summary.gini_base_norm,
            metrics_extended=result.metrics_extended.values,
        )

        return {
            "ok": True,
            "run_history_id": history_id,
            "config": {
                "cap_default": cap_default,
                "b": b,
                "seed": seed,
                "draft_rounds": resolved_draft_rounds,
                "post_iters": post_iters,
                "move_type": move_type,
                "objective_scope": objective_scope,
                "improve_mode": improve_mode,
            },
            "summary": asdict(result.summary),
            "allocation": result.alloc,
            "pick_log": _serialize_pick_log(result.pick_log),
            "post_log": _serialize_post_log(result.post_log),
            "metrics_extended": asdict(result.metrics_extended),
            "csv_outputs": {
                "allocation": allocation_path.read_text(encoding="utf-8"),
                "post_allocation": post_path.read_text(encoding="utf-8"),
                "summary": summary_path.read_text(encoding="utf-8"),
                "metrics_extended": metrics_path.read_text(encoding="utf-8"),
            },
        }


def _run_mode_comparison_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object")

    table1_csv = _read_csv_from_payload(
        payload,
        text_key="table1_csv",
        file_key="table1_file",
        required=True,
    )
    table2_csv = _read_csv_from_payload(
        payload,
        text_key="table2_csv",
        file_key="table2_file",
        required=True,
    )
    table_lambda_csv = _read_csv_from_payload(
        payload,
        text_key="lambda_csv",
        file_key="lambda_file",
        required=False,
    )

    cap_default = _to_int(payload, "cap_default", default=10)
    b = _to_int(payload, "b", default=3)
    base_seed = _to_int(payload, "seed", default=42)
    draft_rounds = _optional_int(payload, "draft_rounds")
    post_iters = _to_int(payload, "post_iters", default=0)
    initial_method = str(payload.get("initial_method", "sequential"))
    sequence = str(payload.get("sequence", "snake"))
    pick_rule = str(payload.get("pick_rule", "personal"))
    batch_size = _to_int(payload, "batch_size", default=30)
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")
    if batch_size > 200:
        raise ValueError("batch_size must be <= 200")
    table1_ref = _history_ref(payload, "table1_file") or "[inline-table1]"
    table2_ref = _history_ref(payload, "table2_file") or "[inline-table2]"
    lambda_ref = _history_ref(payload, "lambda_file")
    resolved_draft_rounds = b if draft_rounds is None else draft_rounds
    raw_progress_job_id = payload.get("progress_job_id")
    progress_job_id = (
        _normalize_progress_job_id(raw_progress_job_id)
        if raw_progress_job_id is not None
        else None
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        csv_a = tmp_dir / "table1.csv"
        csv_b = tmp_dir / "table2.csv"
        csv_lambda: Path | None = None
        progress_dir = tmp_dir / "compare_progress"
        progress_dir.mkdir()
        csv_a.write_text(table1_csv, encoding="utf-8")
        csv_b.write_text(table2_csv, encoding="utf-8")

        if table_lambda_csv is not None:
            csv_lambda = tmp_dir / "lambda.csv"
            csv_lambda.write_text(table_lambda_csv, encoding="utf-8")

        tasks: list[dict[str, Any]] = []
        mode_meta: dict[str, tuple[str, str]] = {}
        history_ids: list[int] = []
        for mode in CANONICAL_IMPROVE_MODES:
            move_type, objective_scope, improve_mode = normalize_improvement_config(
                improve_mode=mode
            )
            mode_meta[improve_mode] = (move_type, objective_scope)
            for offset in range(batch_size):
                tasks.append(
                    {
                        "csv_a": str(csv_a),
                        "csv_b": str(csv_b),
                        "csv_lambda": (str(csv_lambda) if csv_lambda is not None else None),
                        "cap_default": cap_default,
                        "b": b,
                        "draft_rounds": draft_rounds,
                        "post_iters": post_iters,
                        "improve_mode": improve_mode,
                        "initial_method": initial_method,
                        "sequence": sequence,
                        "pick_rule": pick_rule,
                        "seed": base_seed + offset,
                    }
                )

        parallel_workers = 6
        chunks: list[dict[str, Any]] = [
            {
                "worker_id": worker_id,
                "progress_dir": str(progress_dir),
                "tasks": [],
            }
            for worker_id in range(1, parallel_workers + 1)
        ]
        for idx, task in enumerate(tasks):
            chunks[idx % parallel_workers]["tasks"].append(task)
        worker_totals = {
            int(chunk["worker_id"]): len(chunk["tasks"])
            for chunk in chunks
        }
        if progress_job_id is not None:
            with _COMPARE_PROGRESS_LOCK:
                _COMPARE_PROGRESS[progress_job_id] = {
                    "status": "running",
                    "progress_dir": str(progress_dir),
                    "worker_count": parallel_workers,
                    "worker_totals": worker_totals,
                }
        try:
            task_results, effective_parallel_workers, parallel_fallback_reason = (
                _run_mode_comparison_tasks(chunks, parallel_workers=parallel_workers)
            )
        except Exception:
            if progress_job_id is not None:
                failed_workers = _read_compare_progress(progress_job_id).get("workers", [])
                with _COMPARE_PROGRESS_LOCK:
                    _COMPARE_PROGRESS[progress_job_id] = {
                        "status": "failed",
                        "workers": failed_workers,
                        "worker_count": parallel_workers,
                        "worker_totals": worker_totals,
                    }
            raise
        if progress_job_id is not None:
            final_workers = _read_compare_progress(progress_job_id).get("workers", [])
            for worker in final_workers:
                worker["status"] = "done"
            with _COMPARE_PROGRESS_LOCK:
                _COMPARE_PROGRESS[progress_job_id] = {
                    "status": "done",
                    "workers": final_workers,
                    "worker_count": parallel_workers,
                    "worker_totals": worker_totals,
                }

        grouped_results: dict[str, list[dict[str, Any]]] = {
            mode: [] for mode in CANONICAL_IMPROVE_MODES
        }
        for row in task_results:
            improve_mode = str(row["improve_mode"])
            move_type, objective_scope = mode_meta[improve_mode]
            grouped_results[improve_mode].append(row)
            history_ids.append(
                _append_run_history(
                    table1_ref=table1_ref,
                    table2_ref=table2_ref,
                    lambda_ref=lambda_ref,
                    cap_default=cap_default,
                    b=b,
                    seed=int(row["seed"]),
                    draft_rounds=resolved_draft_rounds,
                    post_iters=post_iters,
                    move_type=move_type,
                    objective_scope=objective_scope,
                    improve_mode=improve_mode,
                    total_utility=float(row["total_utility"]),
                    gini_total_norm=float(row["gini_total_norm"]),
                    gini_base_norm=float(row["gini_base_norm"]),
                    metrics_extended=dict(row.get("metrics_extended") or {}),
                )
            )

        by_mode: list[dict[str, Any]] = []
        for mode in CANONICAL_IMPROVE_MODES:
            move_type, objective_scope = mode_meta[mode]
            rows = grouped_results[mode]
            total_values: list[float] = []
            g_total_values: list[float] = []
            g_base_values: list[float] = []
            metric_values: dict[str, list[float]] = {key: [] for key in HISTORY_METRIC_KEYS}
            seeds: list[int] = []
            for row in rows:
                seeds.append(int(row["seed"]))
                total_values.append(float(row["total_utility"]))
                g_total_values.append(float(row["gini_total_norm"]))
                g_base_values.append(float(row["gini_base_norm"]))
                metrics = dict(row.get("metrics_extended") or {})
                metrics.setdefault("total_utility", float(row["total_utility"]))
                metrics.setdefault("gini_total_norm", float(row["gini_total_norm"]))
                metrics.setdefault("gini_base_norm", float(row["gini_base_norm"]))
                for key in HISTORY_METRIC_KEYS:
                    try:
                        value = float(metrics[key])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if math.isfinite(value):
                        metric_values[key].append(value)

            out_row: dict[str, Any] = {
                "improve_mode": mode,
                "move_type": move_type,
                "objective_scope": objective_scope,
                "runs": batch_size,
                "seed_start": min(seeds),
                "seed_end": max(seeds),
            }
            for key, values in metric_values.items():
                out_row[f"avg_{key}"] = _mean(values)
                out_row[f"std_{key}"] = _stddev(values)
                if key in HISTORY_MAX_METRIC_KEYS:
                    out_row[f"best_{key}"] = max(values) if values else 0.0
                if key in HISTORY_MIN_METRIC_KEYS:
                    out_row[f"min_{key}"] = min(values) if values else 0.0

            # Preserve legacy response keys used by older UI/tests.
            out_row.setdefault("avg_total_utility", _mean(total_values))
            out_row.setdefault("best_total_utility", max(total_values))
            out_row.setdefault("std_total_utility", _stddev(total_values))
            out_row.setdefault("avg_gini_total_norm", _mean(g_total_values))
            out_row.setdefault("min_gini_total_norm", min(g_total_values))
            out_row.setdefault("std_gini_total_norm", _stddev(g_total_values))
            out_row.setdefault("avg_gini_base_norm", _mean(g_base_values))
            out_row.setdefault("min_gini_base_norm", min(g_base_values))
            out_row.setdefault("std_gini_base_norm", _stddev(g_base_values))
            by_mode.append(out_row)

    best_utility = max(by_mode, key=lambda row: row["avg_total_utility"]) if by_mode else None
    best_fairness = min(by_mode, key=lambda row: row["avg_gini_total_norm"]) if by_mode else None
    best_friend = (
        max(by_mode, key=lambda row: row.get("avg_mean_friend_norm_assigned", 0.0))
        if by_mode
        else None
    )
    best_social_opportunity_fairness = (
        min(by_mode, key=lambda row: row.get("avg_gini_friend_opportunity_norm", 1.0))
        if by_mode
        else None
    )
    return {
        "ok": True,
        "run_history_ids": history_ids,
        "config": {
            "cap_default": cap_default,
            "b": b,
            "base_seed": base_seed,
            "seed_start": base_seed,
            "seed_end": base_seed + batch_size - 1,
            "batch_size": batch_size,
            "parallel_workers": parallel_workers,
            "effective_parallel_workers": effective_parallel_workers,
            "parallel_fallback_reason": parallel_fallback_reason,
            "draft_rounds": resolved_draft_rounds,
            "post_iters": post_iters,
            "modes": list(CANONICAL_IMPROVE_MODES),
        },
        "by_mode": by_mode,
        "overall": {
            "mode_count": len(by_mode),
            "runs_total": len(by_mode) * batch_size,
            "best_avg_utility_mode": best_utility,
            "best_avg_fairness_mode": best_fairness,
            "best_avg_friend_mode": best_friend,
            "best_avg_social_opportunity_fairness_mode": best_social_opportunity_fairness,
        },
    }


def _parse_post_grid_payload(raw: Any) -> list[int]:
    if raw is None or raw == "":
        values = [0, 1, 2, 3, 5, 8, 12, 16, 20]
    elif isinstance(raw, list):
        values = [int(item) for item in raw]
    else:
        values = [int(token.strip()) for token in str(raw).split(",") if token.strip()]
    if not values:
        raise ValueError("post_grid cannot be empty")
    cleaned = sorted(set(values))
    if len(cleaned) > 21:
        raise ValueError("post_grid must contain at most 21 values")
    for value in cleaned:
        if value < 0:
            raise ValueError("post_grid values must be >= 0")
    return cleaned


def _run_post_mode_sweep_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object")

    table1_csv = _read_csv_from_payload(
        payload,
        text_key="table1_csv",
        file_key="table1_file",
        required=True,
    )
    table2_csv = _read_csv_from_payload(
        payload,
        text_key="table2_csv",
        file_key="table2_file",
        required=True,
    )
    table_lambda_csv = _read_csv_from_payload(
        payload,
        text_key="lambda_csv",
        file_key="lambda_file",
        required=False,
    )

    cap_default = _to_int(payload, "cap_default", default=10)
    b = _to_int(payload, "b", default=3)
    base_seed = _to_int(payload, "seed", default=42)
    draft_rounds = _optional_int(payload, "draft_rounds")
    seed_count = _to_int(payload, "post_sweep_seed_count", default=1)
    if seed_count <= 0:
        raise ValueError("post_sweep_seed_count must be > 0")
    if seed_count > 20:
        raise ValueError("post_sweep_seed_count must be <= 20")
    constant_lambda: float | None = None
    if table_lambda_csv is None and payload.get("constant_lambda") is not None:
        constant_lambda = _to_float(payload, "constant_lambda")
        if not (0.0 <= constant_lambda <= 1.0):
            raise ValueError("constant_lambda must be in range 0..1")
    post_grid = _parse_post_grid_payload(payload.get("post_grid"))
    table1_ref = _history_ref(payload, "table1_file") or "[inline-table1]"
    table2_ref = _history_ref(payload, "table2_file") or "[inline-table2]"
    lambda_ref = (
        f"constant:{constant_lambda:.3f}"
        if constant_lambda is not None
        else _history_ref(payload, "lambda_file")
    )
    resolved_draft_rounds = b if draft_rounds is None else draft_rounds
    raw_progress_job_id = payload.get("progress_job_id")
    progress_job_id = (
        _normalize_progress_job_id(raw_progress_job_id)
        if raw_progress_job_id is not None
        else None
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        csv_a = tmp_dir / "table1.csv"
        csv_b = tmp_dir / "table2.csv"
        csv_lambda: Path | None = None
        progress_dir = tmp_dir / "post_mode_sweep_progress"
        progress_dir.mkdir()
        csv_a.write_text(table1_csv, encoding="utf-8")
        csv_b.write_text(table2_csv, encoding="utf-8")
        if table_lambda_csv is not None:
            csv_lambda = tmp_dir / "lambda.csv"
            csv_lambda.write_text(table_lambda_csv, encoding="utf-8")
        elif constant_lambda is not None:
            table1_student_ids = {row.student_id for row in _read_table_1(csv_a)}
            table2_student_ids = {
                student_id
                for row in _read_table_2(csv_b)
                for student_id in (row.student_id_a, row.student_id_b)
            }
            student_ids = sorted(table1_student_ids | table2_student_ids)
            if not student_ids:
                raise ValueError("Table 1 must contain at least one student")
            csv_lambda = tmp_dir / "lambda_constant.csv"
            _write_constant_lambda_csv(csv_lambda, student_ids, constant_lambda)

        tasks: list[dict[str, Any]] = []
        mode_meta: dict[str, tuple[str, str]] = {}
        history_ids: list[int] = []
        for post_iters in post_grid:
            for mode in CANONICAL_IMPROVE_MODES:
                move_type, objective_scope, improve_mode = normalize_improvement_config(
                    improve_mode=mode
                )
                mode_meta[improve_mode] = (move_type, objective_scope)
                for offset in range(seed_count):
                    tasks.append(
                        {
                            "csv_a": str(csv_a),
                            "csv_b": str(csv_b),
                            "csv_lambda": (str(csv_lambda) if csv_lambda is not None else None),
                            "cap_default": cap_default,
                            "b": b,
                            "draft_rounds": draft_rounds,
                            "post_iters": post_iters,
                            "improve_mode": improve_mode,
                            "seed": base_seed + offset,
                        }
                    )

        parallel_workers = min(6, max(1, len(tasks)))
        chunks: list[dict[str, Any]] = [
            {
                "worker_id": worker_id,
                "progress_dir": str(progress_dir),
                "tasks": [],
            }
            for worker_id in range(1, parallel_workers + 1)
        ]
        for idx, task in enumerate(tasks):
            chunks[idx % parallel_workers]["tasks"].append(task)
        worker_totals = {int(chunk["worker_id"]): len(chunk["tasks"]) for chunk in chunks}
        if progress_job_id is not None:
            with _COMPARE_PROGRESS_LOCK:
                _COMPARE_PROGRESS[progress_job_id] = {
                    "status": "running",
                    "progress_dir": str(progress_dir),
                    "worker_count": parallel_workers,
                    "worker_totals": worker_totals,
                }
        try:
            task_results, effective_parallel_workers, parallel_fallback_reason = (
                _run_mode_comparison_tasks(chunks, parallel_workers=parallel_workers)
            )
        except Exception:
            if progress_job_id is not None:
                failed_workers = _read_compare_progress(progress_job_id).get("workers", [])
                with _COMPARE_PROGRESS_LOCK:
                    _COMPARE_PROGRESS[progress_job_id] = {
                        "status": "failed",
                        "workers": failed_workers,
                        "worker_count": parallel_workers,
                        "worker_totals": worker_totals,
                    }
            raise
        if progress_job_id is not None:
            final_workers = _read_compare_progress(progress_job_id).get("workers", [])
            for worker in final_workers:
                worker["status"] = "done"
            with _COMPARE_PROGRESS_LOCK:
                _COMPARE_PROGRESS[progress_job_id] = {
                    "status": "done",
                    "workers": final_workers,
                    "worker_count": parallel_workers,
                    "worker_totals": worker_totals,
                }

        grouped: dict[tuple[int, str], list[dict[str, Any]]] = {}
        for row in task_results:
            post_iters = int(row["post_iters"])
            improve_mode = str(row["improve_mode"])
            grouped.setdefault((post_iters, improve_mode), []).append(row)
            move_type, objective_scope = mode_meta[improve_mode]
            history_ids.append(
                _append_run_history(
                    table1_ref=table1_ref,
                    table2_ref=table2_ref,
                    lambda_ref=lambda_ref,
                    cap_default=cap_default,
                    b=b,
                    seed=int(row["seed"]),
                    draft_rounds=resolved_draft_rounds,
                    post_iters=post_iters,
                    move_type=move_type,
                    objective_scope=objective_scope,
                    improve_mode=improve_mode,
                    total_utility=float(row["total_utility"]),
                    gini_total_norm=float(row["gini_total_norm"]),
                    gini_base_norm=float(row["gini_base_norm"]),
                    metrics_extended=dict(row.get("metrics_extended") or {}),
                )
            )

        by_mode_post: list[dict[str, Any]] = []
        for post_iters in post_grid:
            for mode in CANONICAL_IMPROVE_MODES:
                move_type, objective_scope = mode_meta[mode]
                rows = grouped.get((post_iters, mode), [])
                metric_values: dict[str, list[float]] = {key: [] for key in HISTORY_METRIC_KEYS}
                seeds: list[int] = []
                total_values: list[float] = []
                g_total_values: list[float] = []
                g_base_values: list[float] = []
                for row in rows:
                    seeds.append(int(row["seed"]))
                    total_values.append(float(row["total_utility"]))
                    g_total_values.append(float(row["gini_total_norm"]))
                    g_base_values.append(float(row["gini_base_norm"]))
                    metrics = dict(row.get("metrics_extended") or {})
                    metrics.setdefault("total_utility", float(row["total_utility"]))
                    metrics.setdefault("gini_total_norm", float(row["gini_total_norm"]))
                    metrics.setdefault("gini_base_norm", float(row["gini_base_norm"]))
                    for key in HISTORY_METRIC_KEYS:
                        try:
                            value = float(metrics[key])
                        except (KeyError, TypeError, ValueError):
                            continue
                        if math.isfinite(value):
                            metric_values[key].append(value)

                out_row: dict[str, Any] = {
                    "post_iters": post_iters,
                    "improve_mode": mode,
                    "move_type": move_type,
                    "objective_scope": objective_scope,
                    "runs": len(rows),
                    "seed_start": min(seeds) if seeds else base_seed,
                    "seed_end": max(seeds) if seeds else base_seed,
                }
                for key, values in metric_values.items():
                    out_row[f"avg_{key}"] = _mean(values)
                    out_row[f"std_{key}"] = _stddev(values)
                out_row.setdefault("avg_total_utility", _mean(total_values))
                out_row.setdefault("avg_gini_total_norm", _mean(g_total_values))
                out_row.setdefault("avg_gini_base_norm", _mean(g_base_values))
                by_mode_post.append(out_row)

    return {
        "ok": True,
        "run_history_ids": history_ids,
        "config": {
            "cap_default": cap_default,
            "b": b,
            "base_seed": base_seed,
            "seed_start": base_seed,
            "seed_end": base_seed + seed_count - 1,
            "seed_count": seed_count,
            "post_grid": post_grid,
            "constant_lambda": constant_lambda,
            "lambda_ref": lambda_ref,
            "draft_rounds": resolved_draft_rounds,
            "modes": list(CANONICAL_IMPROVE_MODES),
            "parallel_workers": parallel_workers,
            "effective_parallel_workers": effective_parallel_workers,
            "parallel_fallback_reason": parallel_fallback_reason,
        },
        "by_mode_post": by_mode_post,
        "overall": {
            "post_count": len(post_grid),
            "mode_count": len(CANONICAL_IMPROVE_MODES),
            "runs_total": len(history_ids),
        },
    }


def _parse_lambda_grid(raw: Any) -> list[float]:
    if raw is None or raw == "":
        values = [0.0, 0.25, 0.5, 0.75, 1.0]
    elif isinstance(raw, list):
        values = [float(item) for item in raw]
    else:
        values = [float(token.strip()) for token in str(raw).split(",") if token.strip()]
    if not values:
        raise ValueError("lambda_values cannot be empty")
    cleaned = sorted(set(round(value, 6) for value in values))
    if len(cleaned) > 21:
        raise ValueError("lambda_values must contain at most 21 values")
    for value in cleaned:
        if not (0.0 <= value <= 1.0):
            raise ValueError("lambda_values must be in range 0..1")
    return cleaned


def _write_constant_lambda_csv(path: Path, student_ids: list[str], lambda_value: float) -> None:
    lines = ["StudentID,LambdaFriend"]
    lines.extend(f"{student_id},{lambda_value:.6f}" for student_id in student_ids)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_lambda_sweep_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object")

    table1_csv = _read_csv_from_payload(
        payload,
        text_key="table1_csv",
        file_key="table1_file",
        required=True,
    )
    table2_csv = _read_csv_from_payload(
        payload,
        text_key="table2_csv",
        file_key="table2_file",
        required=True,
    )

    cap_default = _to_int(payload, "cap_default", default=10)
    b = _to_int(payload, "b", default=3)
    base_seed = _to_int(payload, "seed", default=42)
    draft_rounds = _optional_int(payload, "draft_rounds")
    post_iters = _to_int(payload, "post_iters", default=0)
    batch_size = _to_int(payload, "lambda_batch_size", default=1)
    if batch_size <= 0:
        raise ValueError("lambda_batch_size must be > 0")
    if batch_size > 20:
        raise ValueError("lambda_batch_size must be <= 20")
    lambda_values = _parse_lambda_grid(payload.get("lambda_values"))

    move_type, objective_scope, improve_mode = normalize_improvement_config(
        improve_mode=_optional_str(payload, "improve_mode"),
        move_type=_optional_str(payload, "move_type"),
        objective_scope=_optional_str(payload, "objective_scope"),
    )
    table1_ref = _history_ref(payload, "table1_file") or "[inline-table1]"
    table2_ref = _history_ref(payload, "table2_file") or "[inline-table2]"
    resolved_draft_rounds = b if draft_rounds is None else draft_rounds

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        csv_a = tmp_dir / "table1.csv"
        csv_b = tmp_dir / "table2.csv"
        csv_a.write_text(table1_csv, encoding="utf-8")
        csv_b.write_text(table2_csv, encoding="utf-8")

        table1_student_ids = {row.student_id for row in _read_table_1(csv_a)}
        table2_student_ids = {
            student_id
            for row in _read_table_2(csv_b)
            for student_id in (row.student_id_a, row.student_id_b)
        }
        student_ids = sorted(table1_student_ids | table2_student_ids)
        if not student_ids:
            raise ValueError("Table 1 must contain at least one student")

        rows_by_lambda: list[dict[str, Any]] = []
        history_ids: list[int] = []
        for lambda_value in lambda_values:
            csv_lambda = tmp_dir / f"lambda_{lambda_value:.6f}.csv"
            _write_constant_lambda_csv(csv_lambda, student_ids, lambda_value)
            metric_values: dict[str, list[float]] = {key: [] for key in HISTORY_METRIC_KEYS}
            seeds: list[int] = []
            total_values: list[float] = []
            g_total_values: list[float] = []
            g_base_values: list[float] = []

            for offset in range(batch_size):
                seed = base_seed + offset
                result = run_hbs_social(
                    csv_a,
                    csv_b,
                    csv_lambda=csv_lambda,
                    cap_default=cap_default,
                    b=b,
                    seed=seed,
                    draft_rounds=draft_rounds,
                    post_iters=post_iters,
                    improve_mode=improve_mode,
                    move_type=move_type,
                    objective_scope=objective_scope,
                    progress=False,
                    sanity_checks=False,
                    delta_check_every=0,
                )
                metrics = dict(result.metrics_extended.values)
                metrics.setdefault("total_utility", float(result.summary.total_utility))
                metrics.setdefault("gini_total_norm", float(result.summary.gini_total_norm))
                metrics.setdefault("gini_base_norm", float(result.summary.gini_base_norm))
                seeds.append(seed)
                total_values.append(float(result.summary.total_utility))
                g_total_values.append(float(result.summary.gini_total_norm))
                g_base_values.append(float(result.summary.gini_base_norm))
                for key in HISTORY_METRIC_KEYS:
                    try:
                        value = float(metrics[key])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if math.isfinite(value):
                        metric_values[key].append(value)

                history_ids.append(
                    _append_run_history(
                        table1_ref=table1_ref,
                        table2_ref=table2_ref,
                        lambda_ref=f"constant:{lambda_value:.3f}",
                        cap_default=cap_default,
                        b=b,
                        seed=seed,
                        draft_rounds=resolved_draft_rounds,
                        post_iters=post_iters,
                        move_type=move_type,
                        objective_scope=objective_scope,
                        improve_mode=improve_mode,
                        total_utility=float(result.summary.total_utility),
                        gini_total_norm=float(result.summary.gini_total_norm),
                        gini_base_norm=float(result.summary.gini_base_norm),
                        metrics_extended=metrics,
                    )
                )

            row: dict[str, Any] = {
                "lambda": lambda_value,
                "runs": batch_size,
                "seed_start": min(seeds),
                "seed_end": max(seeds),
            }
            for key, values in metric_values.items():
                row[f"avg_{key}"] = _mean(values)
                row[f"std_{key}"] = _stddev(values)
                if key in HISTORY_MAX_METRIC_KEYS:
                    row[f"best_{key}"] = max(values) if values else 0.0
                if key in HISTORY_MIN_METRIC_KEYS:
                    row[f"min_{key}"] = min(values) if values else 0.0

            row.setdefault("avg_total_utility", _mean(total_values))
            row.setdefault("avg_gini_total_norm", _mean(g_total_values))
            row.setdefault("avg_gini_base_norm", _mean(g_base_values))
            rows_by_lambda.append(row)

    return {
        "ok": True,
        "run_history_ids": history_ids,
        "config": {
            "cap_default": cap_default,
            "b": b,
            "base_seed": base_seed,
            "seed_start": base_seed,
            "seed_end": base_seed + batch_size - 1,
            "lambda_batch_size": batch_size,
            "lambda_values": lambda_values,
            "draft_rounds": resolved_draft_rounds,
            "post_iters": post_iters,
            "move_type": move_type,
            "objective_scope": objective_scope,
            "improve_mode": improve_mode,
        },
        "by_lambda": rows_by_lambda,
        "overall": {
            "lambda_count": len(rows_by_lambda),
            "runs_total": len(history_ids),
        },
    }


def _run_mode_lambda_sweep_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object")

    table1_csv = _read_csv_from_payload(
        payload,
        text_key="table1_csv",
        file_key="table1_file",
        required=True,
    )
    table2_csv = _read_csv_from_payload(
        payload,
        text_key="table2_csv",
        file_key="table2_file",
        required=True,
    )

    cap_default = _to_int(payload, "cap_default", default=10)
    b = _to_int(payload, "b", default=3)
    base_seed = _to_int(payload, "seed", default=42)
    draft_rounds = _optional_int(payload, "draft_rounds")
    post_iters = _to_int(payload, "post_iters", default=0)
    batch_size = _to_int(payload, "lambda_batch_size", default=1)
    if batch_size <= 0:
        raise ValueError("lambda_batch_size must be > 0")
    if batch_size > 20:
        raise ValueError("lambda_batch_size must be <= 20")
    lambda_values = _parse_lambda_grid(payload.get("lambda_values"))

    table1_ref = _history_ref(payload, "table1_file") or "[inline-table1]"
    table2_ref = _history_ref(payload, "table2_file") or "[inline-table2]"
    resolved_draft_rounds = b if draft_rounds is None else draft_rounds

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        csv_a = tmp_dir / "table1.csv"
        csv_b = tmp_dir / "table2.csv"
        csv_a.write_text(table1_csv, encoding="utf-8")
        csv_b.write_text(table2_csv, encoding="utf-8")

        table1_student_ids = {row.student_id for row in _read_table_1(csv_a)}
        table2_student_ids = {
            student_id
            for row in _read_table_2(csv_b)
            for student_id in (row.student_id_a, row.student_id_b)
        }
        student_ids = sorted(table1_student_ids | table2_student_ids)
        if not student_ids:
            raise ValueError("Table 1 must contain at least one student")

        rows_by_mode_lambda: list[dict[str, Any]] = []
        history_ids: list[int] = []
        for lambda_value in lambda_values:
            csv_lambda = tmp_dir / f"lambda_{lambda_value:.6f}.csv"
            _write_constant_lambda_csv(csv_lambda, student_ids, lambda_value)
            for mode in CANONICAL_IMPROVE_MODES:
                move_type, objective_scope, improve_mode = normalize_improvement_config(
                    improve_mode=mode
                )
                metric_values: dict[str, list[float]] = {
                    key: [] for key in HISTORY_METRIC_KEYS
                }
                seeds: list[int] = []
                total_values: list[float] = []
                g_total_values: list[float] = []
                g_base_values: list[float] = []

                for offset in range(batch_size):
                    seed = base_seed + offset
                    result = run_hbs_social(
                        csv_a,
                        csv_b,
                        csv_lambda=csv_lambda,
                        cap_default=cap_default,
                        b=b,
                        seed=seed,
                        draft_rounds=draft_rounds,
                        post_iters=post_iters,
                        improve_mode=improve_mode,
                        move_type=move_type,
                        objective_scope=objective_scope,
                        progress=False,
                        sanity_checks=False,
                        delta_check_every=0,
                    )
                    metrics = dict(result.metrics_extended.values)
                    metrics.setdefault("total_utility", float(result.summary.total_utility))
                    metrics.setdefault("gini_total_norm", float(result.summary.gini_total_norm))
                    metrics.setdefault("gini_base_norm", float(result.summary.gini_base_norm))
                    seeds.append(seed)
                    total_values.append(float(result.summary.total_utility))
                    g_total_values.append(float(result.summary.gini_total_norm))
                    g_base_values.append(float(result.summary.gini_base_norm))
                    for key in HISTORY_METRIC_KEYS:
                        try:
                            value = float(metrics[key])
                        except (KeyError, TypeError, ValueError):
                            continue
                        if math.isfinite(value):
                            metric_values[key].append(value)

                    history_ids.append(
                        _append_run_history(
                            table1_ref=table1_ref,
                            table2_ref=table2_ref,
                            lambda_ref=f"constant:{lambda_value:.3f}",
                            cap_default=cap_default,
                            b=b,
                            seed=seed,
                            draft_rounds=resolved_draft_rounds,
                            post_iters=post_iters,
                            move_type=move_type,
                            objective_scope=objective_scope,
                            improve_mode=improve_mode,
                            total_utility=float(result.summary.total_utility),
                            gini_total_norm=float(result.summary.gini_total_norm),
                            gini_base_norm=float(result.summary.gini_base_norm),
                            metrics_extended=metrics,
                        )
                    )

                row: dict[str, Any] = {
                    "lambda": lambda_value,
                    "improve_mode": improve_mode,
                    "move_type": move_type,
                    "objective_scope": objective_scope,
                    "runs": batch_size,
                    "seed_start": min(seeds),
                    "seed_end": max(seeds),
                }
                for key, values in metric_values.items():
                    row[f"avg_{key}"] = _mean(values)
                    row[f"std_{key}"] = _stddev(values)
                    if key in HISTORY_MAX_METRIC_KEYS:
                        row[f"best_{key}"] = max(values) if values else 0.0
                    if key in HISTORY_MIN_METRIC_KEYS:
                        row[f"min_{key}"] = min(values) if values else 0.0

                row.setdefault("avg_total_utility", _mean(total_values))
                row.setdefault("avg_gini_total_norm", _mean(g_total_values))
                row.setdefault("avg_gini_base_norm", _mean(g_base_values))
                rows_by_mode_lambda.append(row)

    return {
        "ok": True,
        "run_history_ids": history_ids,
        "config": {
            "cap_default": cap_default,
            "b": b,
            "base_seed": base_seed,
            "seed_start": base_seed,
            "seed_end": base_seed + batch_size - 1,
            "lambda_batch_size": batch_size,
            "lambda_values": lambda_values,
            "draft_rounds": resolved_draft_rounds,
            "post_iters": post_iters,
            "modes": list(CANONICAL_IMPROVE_MODES),
        },
        "by_mode_lambda": rows_by_mode_lambda,
        "overall": {
            "lambda_count": len(lambda_values),
            "mode_count": len(CANONICAL_IMPROVE_MODES),
            "runs_total": len(history_ids),
        },
    }


class _HbsWebHandler(BaseHTTPRequestHandler):
    server_version = "HbsSocialWeb/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path in {"/", "/index.html"}:
            self._serve_ui()
            return
        if path == "/api/tables":
            self._send_json(HTTPStatus.OK, _list_table_files())
            return
        if path == "/api/presentation-artifacts":
            self._send_json(HTTPStatus.OK, _load_presentation_artifacts())
            return
        if path == "/api/compare-progress":
            query = parse_qs(parsed.query)
            job_id_raw = query.get("job_id", [""])[0]
            try:
                job_id = _normalize_progress_job_id(job_id_raw)
                progress = _read_compare_progress(job_id)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            status = HTTPStatus.OK if progress.get("ok") else HTTPStatus.NOT_FOUND
            self._send_json(status, progress)
            return
        if path == "/api/history":
            query = parse_qs(parsed.query)
            limit_raw = query.get("limit", ["200"])[0]
            try:
                limit = int(limit_raw)
            except ValueError:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "limit must be an integer"},
                )
                return
            if limit <= 0:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "limit must be > 0"},
                )
                return
            self._send_json(HTTPStatus.OK, _list_run_history(limit=limit))
            return
        if path == "/api/history/stats":
            query = parse_qs(parsed.query)
            limit_raw = query.get("limit", ["200"])[0]
            try:
                limit = int(limit_raw)
            except ValueError:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "limit must be an integer"},
                )
                return
            if limit <= 0:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "limit must be > 0"},
                )
                return
            try:
                self._send_json(HTTPStatus.OK, _build_run_history_stats(limit=limit))
            except Exception as exc:  # pragma: no cover - defensive fallback
                LOG.exception("Unexpected error during /api/history/stats")
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": f"Unexpected server error: {exc}"},
                )
            return
        self._send_json(
            HTTPStatus.NOT_FOUND,
            {"ok": False, "error": f"Unknown route: {path}"},
        )

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/history/reset":
            try:
                self._send_json(HTTPStatus.OK, _reset_run_history())
            except Exception as exc:  # pragma: no cover - defensive fallback
                LOG.exception("Unexpected error during /api/history/reset")
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": f"Unexpected server error: {exc}"},
                )
            return

        if path not in {
            "/api/run",
            "/api/compare-modes",
            "/api/lambda-sweep",
            "/api/mode-lambda-sweep",
            "/api/post-mode-sweep",
            "/api/generate-tables",
        }:
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"ok": False, "error": f"Unknown route: {path}"},
            )
            return

        content_type = self.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            self._send_json(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                {"ok": False, "error": "Content-Type must be application/json"},
            )
            return

        length_header = self.headers.get("Content-Length")
        if length_header is None:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Missing Content-Length"},
            )
            return

        try:
            body_size = int(length_header)
        except ValueError:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Invalid Content-Length"},
            )
            return

        raw = self.rfile.read(max(0, body_size))
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Invalid JSON payload"},
            )
            return

        try:
            if path == "/api/compare-modes":
                response = _run_mode_comparison_payload(payload)
            elif path == "/api/lambda-sweep":
                response = _run_lambda_sweep_payload(payload)
            elif path == "/api/mode-lambda-sweep":
                response = _run_mode_lambda_sweep_payload(payload)
            elif path == "/api/post-mode-sweep":
                response = _run_post_mode_sweep_payload(payload)
            elif path == "/api/generate-tables":
                response = _generate_tables_payload(payload)
            else:
                response = _run_payload(payload)
        except ValueError as exc:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": str(exc)},
            )
            return
        except Exception as exc:  # pragma: no cover - defensive fallback
            LOG.exception("Unexpected error during /api/run")
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": f"Unexpected server error: {exc}"},
            )
            return

        self._send_json(HTTPStatus.OK, response)

    def _serve_ui(self) -> None:
        if not UI_PATH.exists():
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": f"UI file missing: {UI_PATH}"},
            )
            return
        body = UI_PATH.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve_web_app(host: str, port: int) -> int:
    _init_history_db()
    with ThreadingHTTPServer((host, port), _HbsWebHandler) as server:
        print(f"HBS web app: http://{host}:{port}")
        print("Press Ctrl+C to stop.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping...")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local HTML UI for HBS social course allocation.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Logging verbosity",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))
    return serve_web_app(args.host, args.port)
