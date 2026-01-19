from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IndividualPref:
    """A single student's preference for a course (Table 1: individual preferences)."""

    student_id: str
    course_id: str
    score: int
    position: int


@dataclass(frozen=True)
class PairPref:
    """A student's top-k friend choice for a specific course (Table 2)."""

    student_id_a: str
    student_id_b: str
    course_id: str
    position: int
    score: int | None


@dataclass(frozen=True)
class StudentLambda:
    """Per-student weight for the friend bonus (0..1)."""

    student_id: str
    lambda_friend: float


@dataclass(frozen=True)
class PickLogRow:
    """Audit row capturing what was chosen and why (utility decomposition at pick time)."""

    student_id: str
    course_id: str
    round_picked: int
    utility_at_pick: float
    base_at_pick: float
    friend_bonus_at_pick: float


@dataclass(frozen=True)
class RunSummary:
    """Aggregated metrics for a single run (used for analysis/experiments)."""

    total_utility: float
    gini_total_norm: float
    gini_base_norm: float


@dataclass(frozen=True)
class ExtendedMetrics:
    """Additional metrics for deeper analysis (exported to metrics_extended CSV)."""

    values: dict[str, float]


@dataclass(frozen=True)
class PostAllocLogRow:
    """
    One post-allocation iteration/event (swap or add/drop).

    If no improving move is found in an iteration, event_type is "" and all fields are empty.
    """

    iteration: int
    event_type: str
    student_id: str | None
    dropped_courses: tuple[str, ...] | None
    added_courses: tuple[str, ...] | None
    swap_student_1: str | None
    swap_course_1: str | None
    swap_student_2: str | None
    swap_course_2: str | None
    delta_utility: float | None


@dataclass(frozen=True)
class RunResult:
    """
    Outputs of a run.

    `alloc` is the final allocation (student -> list of courses in pick order).
    `pick_log` is an event log useful for debugging and analysis.
    """

    alloc: dict[str, list[str]]
    pick_log: list[PickLogRow]
    post_log: list[PostAllocLogRow]
    summary: RunSummary
    metrics_extended: ExtendedMetrics
