from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .hbs_api import run_hbs_social
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
HISTORY_DB_PATH = Path(tempfile.gettempdir()) / "hbs_social_web_history.sqlite3"


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


def _init_history_db(db_path: Path = HISTORY_DB_PATH) -> None:
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
                improve_mode TEXT NOT NULL,
                total_utility REAL NOT NULL,
                gini_total_norm REAL NOT NULL,
                gini_base_norm REAL NOT NULL
            )
            """
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
    improve_mode: str,
    total_utility: float,
    gini_total_norm: float,
    gini_base_norm: float,
    db_path: Path = HISTORY_DB_PATH,
) -> int:
    _init_history_db(db_path)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with sqlite3.connect(db_path, timeout=5) as conn:
        cursor = conn.execute(
            """
            INSERT INTO run_history (
                created_at, table1_ref, table2_ref, lambda_ref, cap_default, b, seed,
                draft_rounds, post_iters, improve_mode, total_utility, gini_total_norm, gini_base_norm
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                improve_mode,
                total_utility,
                gini_total_norm,
                gini_base_norm,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def _list_run_history(limit: int = 200, db_path: Path = HISTORY_DB_PATH) -> dict[str, Any]:
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
                cap_default, b, seed, draft_rounds, post_iters, improve_mode,
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
    improve_mode = str(payload.get("improve_mode", "swap"))
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
            improve_mode=improve_mode,
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
        self._send_json(
            HTTPStatus.NOT_FOUND,
            {"ok": False, "error": f"Unknown route: {path}"},
        )

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/run":
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
