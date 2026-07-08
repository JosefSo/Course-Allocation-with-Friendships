#!/usr/bin/env python3
"""
Local web UI for the HBS Social allocator.

Run:
    python hbs_web.py [--port 8765]

Then open http://127.0.0.1:8765 in a browser. No external dependencies:
the server is stdlib http.server, the UI is a single static HTML file
(webui/index.html), and runs call the same public API as the CLI.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import threading
import time
import traceback
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parent
WEBUI_HTML = PROJECT_ROOT / "webui" / "index.html"
TABLES_DIR = PROJECT_ROOT / "tables"

sys.path.insert(0, str(PROJECT_ROOT))

from HBS.hbs_api import normalize_improvement_config, run_hbs_social  # noqa: E402
from HBS.hbs_web import (  # noqa: E402
    _append_run_history,
    _build_run_history_stats,
    _list_run_history,
    _reset_run_history,
    _run_mode_comparison_payload,
)


def _api_generate(params: dict) -> dict:
    """Generate synthetic tables into tables/ via the generator script."""

    students = int(params.get("students", 200))
    courses = int(params.get("courses", 8))
    seed = int(params.get("seed", 11))
    popularity = float(params.get("popularity_strength", 0.0))
    lambda_default = float(params.get("lambda_default", 0.3))

    TABLES_DIR.mkdir(exist_ok=True)
    tag = f"{students}x{courses}_s{seed}_p{int(round(popularity * 100)):02d}"
    out1 = TABLES_DIR / f"t1_{tag}.csv"
    out2 = TABLES_DIR / f"t2_{tag}.csv"
    out3 = TABLES_DIR / f"t3_{tag}.csv"

    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "generate" / "generate_tables.py"),
        "--students", str(students),
        "--courses", str(courses),
        "--seed", str(seed),
        "--popularity-strength", str(popularity),
        "--lambda-default", str(lambda_default),
        "--out1", str(out1),
        "--out2", str(out2),
        "--out3", str(out3),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or "generator failed")
    return {
        "csv_a": out1.name,
        "csv_b": out2.name,
        "csv_lambda": out3.name,
        "tables": _list_tables(),
    }


def _list_tables() -> list[str]:
    if not TABLES_DIR.is_dir():
        return []
    return sorted(p.name for p in TABLES_DIR.glob("*.csv"))


def _resolve_table(name: str) -> Path:
    """Resolve a table file name inside tables/ (no path escapes)."""

    candidate = (TABLES_DIR / name).resolve()
    if candidate.parent != TABLES_DIR.resolve() or not candidate.is_file():
        raise ValueError(f"table not found: {name}")
    return candidate


_TABLE_REQUIRED_COLUMNS = {
    "table1": {"StudentID", "CourseID", "Score", "Position"},
    "table2": {"StudentID_A", "StudentID_B", "CourseID", "Position"},
    "lambda": {"StudentID", "LambdaFriend"},
}


def _validate_table_kind(path: Path, kind: str) -> None:
    """Reject a CSV selected in the wrong UI slot before starting a job."""

    required = _TABLE_REQUIRED_COLUMNS[kind]
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        columns = set(next(csv.reader(handle), []))
    missing = required - columns
    if missing:
        expected = ", ".join(sorted(required))
        raise ValueError(
            f"{kind} selected the wrong CSV file '{path.name}'. "
            f"Expected columns: {expected}"
        )


# ---- background jobs with live progress -----------------------------------

_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def _run_job(job_id: str, params: dict) -> None:
    def progress_cb(event: dict) -> None:
        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
            if job is None:
                return
            if event.get("stage"):
                job["stage"] = event["stage"]
            iteration = int(event.get("iter") or 0)
            if iteration > job["iter"]:
                job["iter"] = iteration
            text = event.get("event")
            viz = event.get("viz")
            if text or viz:
                entry: dict = {"iter": iteration}
                if text:
                    delta = event.get("delta")
                    if delta is not None:
                        text = f"{text}   Δ +{delta:.4f}"
                    entry["text"] = text
                if viz:
                    entry["viz"] = viz
                job["events"].append(entry)

    try:
        csv_a = _resolve_table(str(params["csv_a"]))
        csv_b = _resolve_table(str(params["csv_b"]))
        csv_lambda = None
        if params.get("csv_lambda"):
            csv_lambda = _resolve_table(str(params["csv_lambda"]))

        t0 = time.time()
        result = run_hbs_social(
            csv_a,
            csv_b,
            csv_lambda=csv_lambda,
            cap_default=int(params.get("cap_default", 10)),
            b=int(params.get("b", 3)),
            draft_rounds=(int(params["draft_rounds"]) if params.get("draft_rounds") else None),
            post_iters=int(params.get("post_iters", 0)),
            improve_mode=str(params.get("improve_mode", "swap")),
            initial_method=str(params.get("initial_method", "sequential")),
            sequence=str(params.get("sequence", "snake")),
            pick_rule=str(params.get("pick_rule", "personal")),
            seed=int(params.get("seed", 42)),
            progress_cb=progress_cb,
        )
        elapsed = time.time() - t0

        move_type, objective_scope, effective_mode = normalize_improvement_config(
            improve_mode=str(params.get("improve_mode", "swap"))
        )
        resolved_rounds = (
            int(params["draft_rounds"])
            if params.get("draft_rounds")
            else int(params.get("b", 3))
        )
        history_id = _append_run_history(
            table1_ref=str(params["csv_a"]),
            table2_ref=str(params["csv_b"]),
            lambda_ref=(str(params["csv_lambda"]) if params.get("csv_lambda") else None),
            cap_default=int(params.get("cap_default", 10)),
            b=int(params.get("b", 3)),
            seed=int(params.get("seed", 42)),
            draft_rounds=resolved_rounds,
            post_iters=int(params.get("post_iters", 0)),
            move_type=move_type,
            objective_scope=objective_scope,
            improve_mode=effective_mode,
            total_utility=result.summary.total_utility,
            gini_total_norm=result.summary.gini_total_norm,
            gini_base_norm=result.summary.gini_base_norm,
            metrics_extended=result.metrics_extended.values,
            initial_method=str(params.get("initial_method", "sequential")),
            sequence=str(params.get("sequence", "snake")),
            pick_rule=str(params.get("pick_rule", "personal")),
        )

        swaps = sum(1 for r in result.post_log if r.event_type == "SWAP")
        add_drops = sum(1 for r in result.post_log if r.event_type == "ADD_DROP")
        # Ex-post per-student utilities feed the distribution/Lorenz charts in the UI.
        per_student: dict[str, dict[str, float]] = {}
        for row in result.pick_log:
            per_student[row.student_id] = {
                "base": row.ex_post_course_utility,
                "friend": row.ex_post_friend_utility,
                "total": row.ex_post_combined_utility,
            }
        for student_id in result.alloc:
            per_student.setdefault(student_id, {"base": 0.0, "friend": 0.0, "total": 0.0})
        payload = {
            "elapsed_s": round(elapsed, 2),
            "summary": {
                "total_utility": result.summary.total_utility,
                "total_utility_max": result.summary.total_utility_max,
                "gini_total_norm": result.summary.gini_total_norm,
                "gini_base_norm": result.summary.gini_base_norm,
            },
            "metrics": result.metrics_extended.values,
            "maxima": result.metrics_extended.maxima,
            "alloc": result.alloc,
            "per_student": per_student,
            "picks": len(result.pick_log),
            "post_events": {"swaps": swaps, "add_drops": add_drops},
            "history_id": history_id,
        }
        with _JOBS_LOCK:
            _JOBS[job_id]["result"] = payload
            _JOBS[job_id]["done"] = True
    except Exception as exc:
        traceback.print_exc()
        with _JOBS_LOCK:
            _JOBS[job_id]["error"] = f"{type(exc).__name__}: {exc}"
            _JOBS[job_id]["done"] = True


def _api_run_start(params: dict) -> dict:
    # Validate table names up front so obvious mistakes fail fast (HTTP 400).
    csv_a = _resolve_table(str(params["csv_a"]))
    csv_b = _resolve_table(str(params["csv_b"]))
    _validate_table_kind(csv_a, "table1")
    _validate_table_kind(csv_b, "table2")
    if params.get("csv_lambda"):
        csv_lambda = _resolve_table(str(params["csv_lambda"]))
        _validate_table_kind(csv_lambda, "lambda")

    b = int(params.get("b", 3))
    draft_rounds = int(params["draft_rounds"]) if params.get("draft_rounds") else b
    total_iters = draft_rounds + int(params.get("post_iters", 0))

    job_id = uuid.uuid4().hex[:12]
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "done": False, "error": None, "result": None,
            "stage": "старт", "iter": 0, "total": total_iters, "events": [],
        }
    threading.Thread(target=_run_job, args=(job_id, params), daemon=True).start()
    return {"job": job_id, "total": total_iters}


def _api_progress(job_id: str, cursor: int) -> dict:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise ValueError(f"job not found: {job_id}")
        payload = {
            "done": job["done"],
            "error": job["error"],
            "stage": job["stage"],
            "iter": job["iter"],
            "total": job["total"],
            "events": job["events"][cursor:],
            "cursor": len(job["events"]),
        }
        if job["done"] and job["result"] is not None:
            payload["result"] = job["result"]
        if job["done"]:
            # One-shot delivery: the UI keeps its own history.
            del _JOBS[job_id]
    return payload


def _api_compare(params: dict) -> dict:
    csv_a = _resolve_table(str(params["csv_a"]))
    csv_b = _resolve_table(str(params["csv_b"]))
    _validate_table_kind(csv_a, "table1")
    _validate_table_kind(csv_b, "table2")
    if params.get("csv_lambda"):
        _validate_table_kind(
            _resolve_table(str(params["csv_lambda"])),
            "lambda",
        )
    payload = {
        "table1_file": str(params["csv_a"]),
        "table2_file": str(params["csv_b"]),
        "lambda_file": (str(params["csv_lambda"]) if params.get("csv_lambda") else None),
        "cap_default": int(params.get("cap_default", 10)),
        "b": int(params.get("b", 3)),
        "seed": int(params.get("seed", 42)),
        "draft_rounds": params.get("draft_rounds"),
        "post_iters": int(params.get("post_iters", 0)),
        "initial_method": str(params.get("initial_method", "sequential")),
        "batch_size": int(params.get("batch_size", 10)),
        "sequence": str(params.get("sequence", "snake")),
        "pick_rule": str(params.get("pick_rule", "personal")),
    }
    return _run_mode_comparison_payload(payload)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # quieter console
        pass

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            body = WEBUI_HTML.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/api/tables":
            self._send_json({"tables": _list_tables()})
        elif parsed.path == "/api/progress":
            query = parse_qs(parsed.query)
            try:
                job_id = query.get("job", [""])[0]
                cursor = int(query.get("cursor", ["0"])[0])
                self._send_json(_api_progress(job_id, cursor))
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
        elif parsed.path == "/api/history":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["200"])[0])
                self._send_json(_list_run_history(limit=limit))
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
        elif parsed.path == "/api/history/stats":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["200"])[0])
                self._send_json(_build_run_history_stats(limit=limit))
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
        else:
            self._send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        try:
            params = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json({"error": "invalid JSON"}, status=400)
            return

        try:
            if self.path == "/api/run":
                self._send_json(_api_run_start(params))
            elif self.path == "/api/generate":
                self._send_json(_api_generate(params))
            elif self.path == "/api/compare":
                self._send_json(_api_compare(params))
            elif self.path == "/api/history/reset":
                self._send_json(_reset_run_history())
            else:
                self._send_json({"error": "not found"}, status=404)
        except (ValueError, KeyError) as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:  # surface unexpected errors to the UI
            traceback.print_exc()
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, status=500)


def main() -> int:
    parser = argparse.ArgumentParser(description="Web UI for the HBS Social allocator")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser tab")
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), _Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"HBS Social web UI: {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
