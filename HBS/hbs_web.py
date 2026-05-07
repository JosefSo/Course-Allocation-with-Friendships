from __future__ import annotations

import argparse
import json
import logging
import math
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

from .hbs_api import CANONICAL_IMPROVE_MODES, normalize_improvement_config, run_hbs_social
from .hbs_domain import PickLogRow, PostAllocLogRow
from .hbs_io import (
    _write_allocation_csv,
    _write_metrics_extended_csv,
    _write_post_alloc_csv,
    _write_summary_csv,
)

LOG = logging.getLogger(__name__)
UI_PATH = Path(__file__).resolve().parents[1] / "hbs_web_ui.html"
TABLES_DIR = Path(__file__).resolve().parents[1] / "tables"
HISTORY_DB_PATH = Path(__file__).resolve().parents[1] / "results" / "hbs_social_web_history.sqlite3"
_COMPARE_PROGRESS: dict[str, dict[str, Any]] = {}
_COMPARE_PROGRESS_LOCK = threading.Lock()


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
                gini_base_norm REAL NOT NULL
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
                total_utility, gini_total_norm, gini_base_norm
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                total_utility, gini_total_norm, gini_base_norm
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
                total_utility, gini_total_norm, gini_base_norm
            FROM run_history
            ORDER BY id ASC
            LIMIT ?
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

        trend_point = {
            "run_index": idx,
            "id": run_id,
            "move_type": move_type,
            "objective_scope": objective_scope,
            "improve_mode": mode,
            "total_utility": total_utility,
            "gini_total_norm": gini_total_norm,
            "gini_base_norm": gini_base_norm,
        }
        trend.append(trend_point)

        if mode not in mode_acc:
            mode_acc[mode] = {
                "improve_mode": mode,
                "move_type": move_type,
                "objective_scope": objective_scope,
                "runs": 0,
                "sum_total_utility": 0.0,
                "best_total_utility": total_utility,
                "sum_gini_total_norm": 0.0,
                "min_gini_total_norm": gini_total_norm,
                "sum_gini_base_norm": 0.0,
                "min_gini_base_norm": gini_base_norm,
            }
        bucket = mode_acc[mode]
        bucket["runs"] += 1
        bucket["sum_total_utility"] += total_utility
        bucket["best_total_utility"] = max(bucket["best_total_utility"], total_utility)
        bucket["sum_gini_total_norm"] += gini_total_norm
        bucket["min_gini_total_norm"] = min(bucket["min_gini_total_norm"], gini_total_norm)
        bucket["sum_gini_base_norm"] += gini_base_norm
        bucket["min_gini_base_norm"] = min(bucket["min_gini_base_norm"], gini_base_norm)

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
                "avg_total_utility": (bucket["sum_total_utility"] / runs if runs > 0 else 0.0),
                "best_total_utility": float(bucket["best_total_utility"]),
                "avg_gini_total_norm": (bucket["sum_gini_total_norm"] / runs if runs > 0 else 0.0),
                "min_gini_total_norm": float(bucket["min_gini_total_norm"]),
                "avg_gini_base_norm": (bucket["sum_gini_base_norm"] / runs if runs > 0 else 0.0),
                "min_gini_base_norm": float(bucket["min_gini_base_norm"]),
            }
        )

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
        seed=int(task["seed"]),
        progress=False,
        sanity_checks=False,
        delta_check_every=0,
    )
    return {
        "improve_mode": str(task["improve_mode"]),
        "seed": int(task["seed"]),
        "total_utility": float(result.summary.total_utility),
        "gini_total_norm": float(result.summary.gini_total_norm),
        "gini_base_norm": float(result.summary.gini_base_norm),
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
                )
            )

        by_mode: list[dict[str, Any]] = []
        for mode in CANONICAL_IMPROVE_MODES:
            move_type, objective_scope = mode_meta[mode]
            rows = grouped_results[mode]
            total_values: list[float] = []
            g_total_values: list[float] = []
            g_base_values: list[float] = []
            seeds: list[int] = []
            for row in rows:
                seeds.append(int(row["seed"]))
                total_values.append(float(row["total_utility"]))
                g_total_values.append(float(row["gini_total_norm"]))
                g_base_values.append(float(row["gini_base_norm"]))

            by_mode.append(
                {
                    "improve_mode": mode,
                    "move_type": move_type,
                    "objective_scope": objective_scope,
                    "runs": batch_size,
                    "seed_start": min(seeds),
                    "seed_end": max(seeds),
                    "avg_total_utility": _mean(total_values),
                    "best_total_utility": max(total_values),
                    "std_total_utility": _stddev(total_values),
                    "avg_gini_total_norm": _mean(g_total_values),
                    "min_gini_total_norm": min(g_total_values),
                    "std_gini_total_norm": _stddev(g_total_values),
                    "avg_gini_base_norm": _mean(g_base_values),
                    "min_gini_base_norm": min(g_base_values),
                    "std_gini_base_norm": _stddev(g_base_values),
                }
            )

    best_utility = max(by_mode, key=lambda row: row["avg_total_utility"]) if by_mode else None
    best_fairness = min(by_mode, key=lambda row: row["avg_gini_total_norm"]) if by_mode else None
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

        if path not in {"/api/run", "/api/compare-modes"}:
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
