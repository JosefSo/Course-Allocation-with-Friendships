from __future__ import annotations

import csv
from pathlib import Path
from typing import Sequence

from .hbs_domain import (
    ExtendedMetrics,
    IndividualPref,
    PairPref,
    PickLogRow,
    PostAllocLogRow,
    RunSummary,
    StudentLambda,
)


def _read_table_1(path: Path) -> list[IndividualPref]:
    """Read Table 1 CSV (individual preferences) into strongly-typed records."""

    rows: list[IndividualPref] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"StudentID", "CourseID", "Score", "Position"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"CSV A need to include rows: {sorted(required)} (file: {path})")
        for r in reader:
            rows.append(
                IndividualPref(
                    student_id=str(r["StudentID"]).strip(),
                    course_id=str(r["CourseID"]).strip(),
                    score=int(r["Score"]),
                    position=int(r["Position"]),
                )
            )
    return rows


def _read_table_2(path: Path) -> list[PairPref]:
    """Read Table 2 CSV (pair preferences) into strongly-typed records."""

    rows: list[PairPref] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"StudentID_A", "StudentID_B", "CourseID", "Position"}
        fieldnames = set(reader.fieldnames or [])
        if reader.fieldnames is None or not required.issubset(fieldnames):
            raise ValueError(f"CSV B need to include rows: {sorted(required)} (file: {path})")
        has_score = "Score" in fieldnames
        for r in reader:
            score_raw = str(r.get("Score", "")).strip() if has_score else ""
            score = int(score_raw) if score_raw != "" else None
            rows.append(
                PairPref(
                    student_id_a=str(r["StudentID_A"]).strip(),
                    student_id_b=str(r["StudentID_B"]).strip(),
                    course_id=str(r["CourseID"]).strip(),
                    position=int(r["Position"]),
                    score=score,
                )
            )
    return rows


def _read_table_lambda(path: Path) -> list[StudentLambda]:
    """Read per-student lambda CSV into strongly-typed records."""

    rows: list[StudentLambda] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"StudentID", "LambdaFriend"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"CSV Lambda needs rows: {sorted(required)} (file: {path})")
        for r in reader:
            rows.append(
                StudentLambda(
                    student_id=str(r["StudentID"]).strip(),
                    lambda_friend=float(r["LambdaFriend"]),
                )
            )
    return rows


def _write_allocation_csv(
    path: Path,
    *,
    pick_log: list[PickLogRow],
) -> None:
    """
    Write draft-only allocation log (round picks only).
    """

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["RoundPicked", "StudentID", "CourseID"])
        for row in pick_log:
            writer.writerow(
                [
                    row.round_picked,
                    row.student_id,
                    row.course_id,
                ]
            )


def _write_post_alloc_csv(
    path: Path,
    *,
    post_log: list[PostAllocLogRow],
) -> None:
    """
    Write post-allocation events (swap or add/drop) to a separate CSV.
    """

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Iteration",
                "EventType",
                "StudentID",
                "DroppedCourses",
                "AddedCourses",
                "SwapStudent1",
                "SwapCourse1",
                "SwapStudent2",
                "SwapCourse2",
                "DeltaUtility",
            ]
        )
        for row in post_log:
            dropped = "" if not row.dropped_courses else ";".join(row.dropped_courses)
            added = "" if not row.added_courses else ";".join(row.added_courses)
            writer.writerow(
                [
                    row.iteration,
                    row.event_type,
                    (row.student_id or ""),
                    dropped,
                    added,
                    (row.swap_student_1 or ""),
                    (row.swap_course_1 or ""),
                    (row.swap_student_2 or ""),
                    (row.swap_course_2 or ""),
                    (f"{row.delta_utility:.12f}" if row.delta_utility is not None else ""),
                ]
            )


def _write_summary_csv(
    path: Path,
    *,
    seed: int,
    cap_default: int,
    b: int,
    draft_rounds: int,
    post_iters: int,
    summary: RunSummary,
) -> None:
    """
    Write a one-row summary CSV.
    """

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "seed",
                "cap_default",
                "b",
                "draft_rounds",
                "post_iters",
                "total_utility",
                "gini_total_norm",
                "gini_base_norm",
            ]
        )
        writer.writerow(
            [
                seed,
                cap_default,
                b,
                draft_rounds,
                post_iters,
                f"{summary.total_utility:.6f}",
                f"{summary.gini_total_norm:.6f}",
                f"{summary.gini_base_norm:.6f}",
            ]
        )


def _write_metrics_extended_csv(
    path: Path,
    *,
    metrics: ExtendedMetrics,
) -> None:
    """
    Write extended metrics as a one-row CSV.
    """

    keys = list(metrics.values.keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(keys)
        writer.writerow([f"{metrics.values[k]:.6f}" for k in keys])
