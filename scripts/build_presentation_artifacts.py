#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import sys
from pathlib import Path
from statistics import fmean

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from HBS.hbs_api import normalize_improvement_config
from HBS.hbs_config import _RunConfig
from HBS.hbs_engine import _HbsSocialDraftEngine
from HBS.hbs_io import _read_table_1, _read_table_2


OUT_DIR = ROOT / "results" / "presentation_artifacts"

TABLE1 = ROOT / "tables" / "table1_200x8.csv"
TABLE2 = ROOT / "tables" / "table2_200x8.csv"

SEEDS = (11, 12)
POST_ITERS = 5
CAP_DEFAULT = 80
MAX_COURSES = 3
DRAFT_ROUNDS = 3

MODE_FAMILY = ("swap-global", "drop-add-global", "hybrid-global")
SCOPE_MODES = (
    "swap-global",
    "swap-personal",
    "drop-add-global",
    "drop-add-personal",
    "hybrid-global",
    "hybrid-personal",
)
LAMBDA_VALUES = (0.0, 0.25, 0.5, 0.75, 1.0)


def _mean(values: list[float]) -> float:
    return fmean(values) if values else 0.0


def _fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _load_students(rows_a, rows_b) -> list[str]:
    return sorted(
        {r.student_id for r in rows_a}
        | {r.student_id_a for r in rows_b}
        | {r.student_id_b for r in rows_b}
    )


def _run(rows_a, rows_b, students: list[str], *, mode: str, lambda_value: float, seed: int) -> dict[str, float]:
    move_type, objective_scope, effective_mode = normalize_improvement_config(improve_mode=mode)
    config = _RunConfig(
        default_capacity=CAP_DEFAULT,
        max_courses=MAX_COURSES,
        draft_rounds=DRAFT_ROUNDS,
        post_iters=POST_ITERS,
        total_iters=DRAFT_ROUNDS + POST_ITERS,
        move_type=move_type,
        objective_scope=objective_scope,
        effective_improve_mode=effective_mode,
        progress=False,
        seed=seed,
        sanity_checks=False,
        delta_check_every=0,
    )
    engine = _HbsSocialDraftEngine(
        individual_prefs=rows_a,
        pair_prefs=rows_b,
        student_lambdas={student_id: lambda_value for student_id in students},
        config=config,
    )
    result = engine.run()
    metrics = dict(result.metrics_extended.values)
    metrics["total_utility"] = result.summary.total_utility
    metrics["gini_total_norm"] = result.summary.gini_total_norm
    metrics["gini_base_norm"] = result.summary.gini_base_norm
    return metrics


def _aggregate(raw_rows: list[dict[str, object]], group_key: str) -> list[dict[str, object]]:
    metric_keys = [
        "total_utility",
        "total_utility_norm",
        "mean_base_assigned",
        "mean_friend_norm_assigned",
        "friend_norm_base_ratio_mean",
        "total_base_utility",
        "total_friend_utility_norm",
        "avg_friend_overlaps_per_student",
        "share_students_with_any_friend_overlap",
        "gini_total_norm",
        "gini_base_norm",
        "gini_friend_norm",
        "gini_friend_opportunity_norm",
        "avg_position",
        "share_top1",
        "share_top3",
    ]
    grouped: dict[object, list[dict[str, object]]] = {}
    for row in raw_rows:
        grouped.setdefault(row[group_key], []).append(row)

    out: list[dict[str, object]] = []
    for key, rows in grouped.items():
        item: dict[str, object] = {group_key: key, "runs": len(rows)}
        for metric in metric_keys:
            item[metric] = _mean([float(row[metric]) for row in rows])
        out.append(item)
    return out


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _write_markdown(path: Path, sections: list[tuple[str, list[str], list[list[str]]]]) -> None:
    parts = ["# Presentation Tables", ""]
    for title, headers, rows in sections:
        parts.append(f"## {title}")
        parts.append("")
        parts.append(_markdown_table(headers, rows))
        parts.append("")
    path.write_text("\n".join(parts), encoding="utf-8")


def _svg_header(width: int, height: int) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        "text { font-family: Georgia, serif; fill: #1f2933; }",
        ".title { font-size: 24px; font-weight: 700; }",
        ".label { font-size: 13px; }",
        ".small { font-size: 11px; fill: #52606d; }",
        ".axis { stroke: #9aa5b1; stroke-width: 1; }",
        "</style>",
        '<rect x="0" y="0" width="100%" height="100%" fill="#fbfaf7"/>',
    ]


def _save_grouped_bar_svg(path: Path, title: str, rows: list[dict[str, object]], key: str) -> None:
    width, height = 980, 520
    margin_left, margin_bottom, top = 78, 82, 78
    chart_w, chart_h = width - margin_left - 42, height - top - margin_bottom
    metrics = [
        ("mean_base_assigned", "Base", "#2f6f73"),
        ("mean_friend_norm_assigned", "Friend", "#c56b37"),
    ]
    max_y = 1.0
    group_w = chart_w / len(rows)
    bar_w = min(46, group_w / 4)

    svg = _svg_header(width, height)
    svg.append(f'<text class="title" x="42" y="42">{html.escape(title)}</text>')
    svg.append(f'<line class="axis" x1="{margin_left}" y1="{top + chart_h}" x2="{margin_left + chart_w}" y2="{top + chart_h}"/>')
    svg.append(f'<line class="axis" x1="{margin_left}" y1="{top}" x2="{margin_left}" y2="{top + chart_h}"/>')
    for tick in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = top + chart_h - tick * chart_h
        svg.append(f'<line x1="{margin_left - 5}" y1="{y:.1f}" x2="{margin_left + chart_w}" y2="{y:.1f}" stroke="#e4e7eb"/>')
        svg.append(f'<text class="small" x="34" y="{y + 4:.1f}">{tick:.2f}</text>')
    for i, row in enumerate(rows):
        center = margin_left + i * group_w + group_w / 2
        for j, (metric, label, color) in enumerate(metrics):
            value = float(row[metric])
            h = (value / max_y) * chart_h
            x = center + (j - 0.5) * (bar_w + 8) - bar_w / 2
            y = top + chart_h - h
            svg.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="3" fill="{color}"/>')
            svg.append(f'<text class="small" x="{x + bar_w / 2:.1f}" y="{y - 7:.1f}" text-anchor="middle">{value:.2f}</text>')
        svg.append(f'<text class="label" x="{center:.1f}" y="{height - 42}" text-anchor="middle">{html.escape(str(row[key]))}</text>')
    svg.append('<rect x="730" y="30" width="16" height="16" fill="#2f6f73"/><text class="small" x="754" y="43">Base component</text>')
    svg.append('<rect x="730" y="54" width="16" height="16" fill="#c56b37"/><text class="small" x="754" y="67">Friend component</text>')
    svg.append("</svg>")
    path.write_text("\n".join(svg), encoding="utf-8")


def _save_two_series_bar_svg(
    path: Path,
    title: str,
    rows: list[dict[str, object]],
    key: str,
    series: list[tuple[str, str, str]],
) -> None:
    width, height = 980, 520
    margin_left, margin_bottom, top = 78, 82, 78
    chart_w, chart_h = width - margin_left - 42, height - top - margin_bottom
    max_y = max(1.0, max(float(row[metric]) for row in rows for metric, _label, _color in series))
    group_w = chart_w / len(rows)
    bar_w = min(46, group_w / (len(series) + 2))

    svg = _svg_header(width, height)
    svg.append(f'<text class="title" x="42" y="42">{html.escape(title)}</text>')
    svg.append(f'<line class="axis" x1="{margin_left}" y1="{top + chart_h}" x2="{margin_left + chart_w}" y2="{top + chart_h}"/>')
    svg.append(f'<line class="axis" x1="{margin_left}" y1="{top}" x2="{margin_left}" y2="{top + chart_h}"/>')
    for tick in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = top + chart_h - (tick / max_y) * chart_h
        svg.append(f'<line x1="{margin_left - 5}" y1="{y:.1f}" x2="{margin_left + chart_w}" y2="{y:.1f}" stroke="#e4e7eb"/>')
        svg.append(f'<text class="small" x="34" y="{y + 4:.1f}">{tick:.2f}</text>')
    for i, row in enumerate(rows):
        center = margin_left + i * group_w + group_w / 2
        for j, (metric, _label, color) in enumerate(series):
            value = float(row[metric])
            h = (value / max_y) * chart_h
            x = center + (j - (len(series) - 1) / 2) * (bar_w + 8) - bar_w / 2
            y = top + chart_h - h
            svg.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="3" fill="{color}"/>')
            svg.append(f'<text class="small" x="{x + bar_w / 2:.1f}" y="{y - 7:.1f}" text-anchor="middle">{value:.2f}</text>')
        svg.append(f'<text class="label" x="{center:.1f}" y="{height - 42}" text-anchor="middle">{html.escape(str(row[key]))}</text>')
    for idx, (_metric, label, color) in enumerate(series):
        y = 30 + idx * 24
        svg.append(f'<rect x="730" y="{y}" width="16" height="16" fill="{color}"/><text class="small" x="754" y="{y + 13}">{html.escape(label)}</text>')
    svg.append("</svg>")
    path.write_text("\n".join(svg), encoding="utf-8")


def _save_line_svg(path: Path, title: str, rows: list[dict[str, object]]) -> None:
    width, height = 980, 520
    margin_left, margin_bottom, top = 78, 82, 78
    chart_w, chart_h = width - margin_left - 42, height - top - margin_bottom
    series = [
        ("mean_base_assigned", "Base", "#2f6f73"),
        ("mean_friend_norm_assigned", "Friend", "#c56b37"),
        ("total_utility_norm", "Total norm", "#4b5563"),
    ]
    max_y = 1.0
    svg = _svg_header(width, height)
    svg.append(f'<text class="title" x="42" y="42">{html.escape(title)}</text>')
    svg.append(f'<line class="axis" x1="{margin_left}" y1="{top + chart_h}" x2="{margin_left + chart_w}" y2="{top + chart_h}"/>')
    svg.append(f'<line class="axis" x1="{margin_left}" y1="{top}" x2="{margin_left}" y2="{top + chart_h}"/>')
    for tick in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = top + chart_h - tick * chart_h
        svg.append(f'<line x1="{margin_left - 5}" y1="{y:.1f}" x2="{margin_left + chart_w}" y2="{y:.1f}" stroke="#e4e7eb"/>')
        svg.append(f'<text class="small" x="34" y="{y + 4:.1f}">{tick:.2f}</text>')
    for metric, label, color in series:
        points = []
        for row in rows:
            lam = float(row["lambda"])
            value = float(row[metric])
            x = margin_left + lam * chart_w
            y = top + chart_h - (value / max_y) * chart_h
            points.append((x, y, value))
        path_data = " ".join(f"{x:.1f},{y:.1f}" for x, y, _v in points)
        svg.append(f'<polyline points="{path_data}" fill="none" stroke="{color}" stroke-width="3"/>')
        for x, y, value in points:
            svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}"/>')
            svg.append(f'<text class="small" x="{x:.1f}" y="{y - 10:.1f}" text-anchor="middle">{value:.2f}</text>')
    for lam in LAMBDA_VALUES:
        x = margin_left + lam * chart_w
        svg.append(f'<text class="label" x="{x:.1f}" y="{height - 42}" text-anchor="middle">{lam:.2f}</text>')
    for idx, (_metric, label, color) in enumerate(series):
        y = 30 + idx * 24
        svg.append(f'<rect x="730" y="{y}" width="16" height="16" fill="{color}"/><text class="small" x="754" y="{y + 13}">{label}</text>')
    svg.append("</svg>")
    path.write_text("\n".join(svg), encoding="utf-8")


def _presentation_rows_mode(rows: list[dict[str, object]]) -> list[list[str]]:
    return [
        [
            str(row["move"]),
            _fmt(float(row["total_utility_norm"])),
            _fmt(float(row["mean_base_assigned"])),
            _fmt(float(row["mean_friend_norm_assigned"])),
            _fmt(float(row["avg_friend_overlaps_per_student"])),
            _pct(float(row["share_top3"])),
            _fmt(float(row["gini_total_norm"])),
            str(row["message"]),
        ]
        for row in rows
    ]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows_a = _read_table_1(TABLE1)
    rows_b = _read_table_2(TABLE2)
    students = _load_students(rows_a, rows_b)

    raw_mode: list[dict[str, object]] = []
    raw_scope: list[dict[str, object]] = []
    raw_lambda: list[dict[str, object]] = []

    for seed in SEEDS:
        for mode in MODE_FAMILY:
            metrics = _run(rows_a, rows_b, students, mode=mode, lambda_value=0.5, seed=seed)
            raw_mode.append({"mode": mode, "seed": seed, **metrics})
        for mode in SCOPE_MODES:
            metrics = _run(rows_a, rows_b, students, mode=mode, lambda_value=0.5, seed=seed)
            raw_scope.append({"mode": mode, "seed": seed, **metrics})
        for lambda_value in LAMBDA_VALUES:
            metrics = _run(rows_a, rows_b, students, mode="hybrid-global", lambda_value=lambda_value, seed=seed)
            raw_lambda.append({"lambda": lambda_value, "seed": seed, **metrics})

    mode_rows = _aggregate(raw_mode, "mode")
    for row in mode_rows:
        row["move"] = str(row["mode"]).replace("-global", "")
    mode_rows.sort(key=lambda r: {"swap": 0, "drop-add": 1, "hybrid": 2}[str(r["move"])])
    best_friend = max(mode_rows, key=lambda r: float(r["mean_friend_norm_assigned"]))
    best_base = max(mode_rows, key=lambda r: float(r["mean_base_assigned"]))
    for row in mode_rows:
        if row is best_friend:
            row["message"] = "largest social gain"
        elif row is best_base:
            row["message"] = "best preference retention"
        else:
            row["message"] = "middle trade-off"

    scope_rows = _aggregate(raw_scope, "mode")
    scope_rows.sort(key=lambda r: str(r["mode"]))
    scope_summary: list[dict[str, object]] = []
    for move in ("swap", "drop-add", "hybrid"):
        global_row = next(row for row in scope_rows if row["mode"] == f"{move}-global")
        personal_row = next(row for row in scope_rows if row["mode"] == f"{move}-personal")
        scope_summary.append(
            {
                "move": move,
                "global_total_norm": float(global_row["total_utility_norm"]),
                "personal_total_norm": float(personal_row["total_utility_norm"]),
                "global_friend_norm": float(global_row["mean_friend_norm_assigned"]),
                "personal_friend_norm": float(personal_row["mean_friend_norm_assigned"]),
                "global_gini": float(global_row["gini_total_norm"]),
                "personal_gini": float(personal_row["gini_total_norm"]),
                "message": "global keeps the system objective higher",
            }
        )

    lambda_rows = _aggregate(raw_lambda, "lambda")
    lambda_rows.sort(key=lambda r: float(r["lambda"]))
    for row in lambda_rows:
        row["message"] = "social rises, preference quality falls"

    _write_csv(OUT_DIR / "mode_family_comparison.csv", mode_rows)
    _write_csv(OUT_DIR / "global_vs_personal.csv", scope_summary)
    _write_csv(OUT_DIR / "lambda_tradeoff.csv", lambda_rows)
    _write_csv(OUT_DIR / "raw_runs.csv", raw_mode + raw_scope + raw_lambda)

    scope_md_rows = [
        [
            str(row["move"]),
            _fmt(float(row["global_total_norm"])),
            _fmt(float(row["personal_total_norm"])),
            _fmt(float(row["global_friend_norm"])),
            _fmt(float(row["personal_friend_norm"])),
            _fmt(float(row["global_gini"])),
            _fmt(float(row["personal_gini"])),
            str(row["message"]),
        ]
        for row in scope_summary
    ]
    lambda_md_rows = [
        [
            _fmt(float(row["lambda"]), 2),
            _fmt(float(row["total_utility_norm"])),
            _fmt(float(row["mean_base_assigned"])),
            _fmt(float(row["mean_friend_norm_assigned"])),
            _fmt(float(row["avg_friend_overlaps_per_student"])),
            _pct(float(row["share_top3"])),
            _fmt(float(row["gini_total_norm"])),
            str(row["message"]),
        ]
        for row in lambda_rows
    ]
    _write_markdown(
        OUT_DIR / "presentation_tables.md",
        [
            (
                "Move Type Comparison",
                ["Move", "Total norm", "Base", "Friend", "Overlaps", "Top-3", "Gini", "Message"],
                _presentation_rows_mode(mode_rows),
            ),
            (
                "Global vs Personal",
                [
                    "Move",
                    "Global total",
                    "Personal total",
                    "Global friend",
                    "Personal friend",
                    "Global Gini",
                    "Personal Gini",
                    "Message",
                ],
                scope_md_rows,
            ),
            (
                "Lambda Trade-off",
                ["Lambda", "Total norm", "Base", "Friend", "Overlaps", "Top-3", "Gini", "Message"],
                lambda_md_rows,
            ),
        ],
    )

    _save_grouped_bar_svg(
        OUT_DIR / "mode_family_base_vs_friend.svg",
        "Move types: base quality vs social component",
        mode_rows,
        "move",
    )
    _save_grouped_bar_svg(
        OUT_DIR / "global_vs_personal_base_vs_friend.svg",
        "Global vs personal: base quality vs social component",
        [
            {
                "scope": f"{row['move']} G",
                "mean_base_assigned": next(r for r in scope_rows if r["mode"] == f"{row['move']}-global")["mean_base_assigned"],
                "mean_friend_norm_assigned": row["global_friend_norm"],
            }
            for row in scope_summary
        ]
        + [
            {
                "scope": f"{row['move']} P",
                "mean_base_assigned": next(r for r in scope_rows if r["mode"] == f"{row['move']}-personal")["mean_base_assigned"],
                "mean_friend_norm_assigned": row["personal_friend_norm"],
            }
            for row in scope_summary
        ],
        "scope",
    )
    _save_two_series_bar_svg(
        OUT_DIR / "global_vs_personal_friend.svg",
        "Global vs personal: social component by move type",
        scope_summary,
        "move",
        [
            ("global_friend_norm", "Global", "#2f6f73"),
            ("personal_friend_norm", "Personal", "#c56b37"),
        ],
    )
    _save_line_svg(
        OUT_DIR / "lambda_base_friend_tradeoff.svg",
        "Lambda sweep: friend component rises as base preference falls",
        lambda_rows,
    )

    print(f"Wrote presentation artifacts to {OUT_DIR}")
    print(f"- {OUT_DIR / 'presentation_tables.md'}")
    print(f"- {OUT_DIR / 'mode_family_base_vs_friend.svg'}")
    print(f"- {OUT_DIR / 'global_vs_personal_base_vs_friend.svg'}")
    print(f"- {OUT_DIR / 'lambda_base_friend_tradeoff.svg'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
