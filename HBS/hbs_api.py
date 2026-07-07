from __future__ import annotations

import warnings
from pathlib import Path

from .hbs_config import _RunConfig
from .hbs_domain import RunResult
from .hbs_engine import _HbsSocialDraftEngine
from .hbs_io import _read_table_1, _read_table_2, _read_table_lambda

CANONICAL_MOVE_TYPES = ("swap", "drop-add", "hybrid")
CANONICAL_OBJECTIVE_SCOPES = ("global", "personal")
CANONICAL_INITIAL_METHODS = ("sequential", "simultaneous-priority")
CANONICAL_SEQUENCES = (
    "round-robin",
    "snake",
    "reverse-repeat",
    "last-first-static",
)
SEQUENCE_ALIASES = {
    "n-first": "reverse-repeat",
    "last-first": "last-first-static",
}
CANONICAL_PICK_RULES = ("personal", "utilitarian")
CANONICAL_IMPROVE_MODES = (
    "swap-global",
    "swap-personal",
    "drop-add-global",
    "drop-add-personal",
    "hybrid-global",
    "hybrid-personal",
)
_IMPROVE_MODE_ALIASES = {
    "swap": "swap-global",
    "add-drop": "drop-add-global",
    "drop-add": "drop-add-global",
    "adaptive-global": "hybrid-global",
    "adaptive-personal": "hybrid-personal",
    "adaptive-greedy": "hybrid-personal",
}


def compose_improve_mode(move_type: str, objective_scope: str) -> str:
    return f"{move_type}-{objective_scope}"


def normalize_improve_mode(improve_mode: str) -> str:
    return _IMPROVE_MODE_ALIASES.get(improve_mode, improve_mode)


def normalize_sequence(sequence: str) -> str:
    normalized = SEQUENCE_ALIASES.get(sequence, sequence)
    if normalized not in CANONICAL_SEQUENCES:
        allowed = ", ".join((*CANONICAL_SEQUENCES, *SEQUENCE_ALIASES))
        raise ValueError(f"sequence must be one of: {allowed}")
    return normalized


def normalize_pick_rule(pick_rule: str) -> str:
    if pick_rule == "social":
        warnings.warn(
            "pick_rule='social' is deprecated; use 'utilitarian'",
            DeprecationWarning,
            stacklevel=2,
        )
        return "utilitarian"
    if pick_rule not in CANONICAL_PICK_RULES:
        allowed = ", ".join((*CANONICAL_PICK_RULES, "social"))
        raise ValueError(f"pick_rule must be one of: {allowed}")
    return pick_rule


def _parse_effective_mode(improve_mode: str) -> tuple[str, str, str]:
    effective_mode = normalize_improve_mode(improve_mode)
    if effective_mode not in CANONICAL_IMPROVE_MODES:
        allowed = ", ".join(CANONICAL_IMPROVE_MODES)
        raise ValueError(f"improve_mode must be one of: {allowed}")
    move_type, objective_scope = effective_mode.rsplit("-", 1)
    return move_type, objective_scope, effective_mode


def normalize_improvement_config(
    *,
    improve_mode: str | None = None,
    move_type: str | None = None,
    objective_scope: str | None = None,
) -> tuple[str, str, str]:
    if move_type is None and objective_scope is None and improve_mode is None:
        move_type = "swap"
        objective_scope = "global"

    if (move_type is None) != (objective_scope is None):
        raise ValueError("move_type and objective_scope must be provided together")

    effective_from_axes: str | None = None
    if move_type is not None and objective_scope is not None:
        if move_type not in CANONICAL_MOVE_TYPES:
            allowed = ", ".join(CANONICAL_MOVE_TYPES)
            raise ValueError(f"move_type must be one of: {allowed}")
        if objective_scope not in CANONICAL_OBJECTIVE_SCOPES:
            allowed = ", ".join(CANONICAL_OBJECTIVE_SCOPES)
            raise ValueError(f"objective_scope must be one of: {allowed}")
        effective_from_axes = compose_improve_mode(move_type, objective_scope)

    if improve_mode is None:
        if effective_from_axes is None:
            raise ValueError("Either improve_mode or both move_type/objective_scope must be provided")
        return move_type, objective_scope, effective_from_axes

    mode_move_type, mode_objective_scope, effective_from_mode = _parse_effective_mode(improve_mode)
    if effective_from_axes is None:
        return mode_move_type, mode_objective_scope, effective_from_mode
    if effective_from_axes != effective_from_mode:
        raise ValueError(
            "improve_mode conflicts with move_type/objective_scope: "
            f"{effective_from_mode} != {effective_from_axes}"
        )
    return move_type, objective_scope, effective_from_axes


def _validate_input_rows(rows_a, rows_b) -> None:
    students = {row.student_id for row in rows_a}
    courses = {row.course_id for row in rows_a}
    seen_a: set[tuple[str, str]] = set()
    for row in rows_a:
        if not row.student_id or not row.course_id:
            raise ValueError("Table 1 StudentID/CourseID cannot be empty")
        if row.position <= 0:
            raise ValueError("Table 1 Position must be > 0")
        key = (row.student_id, row.course_id)
        if key in seen_a:
            raise ValueError(f"Table 1 duplicate row: {key}")
        seen_a.add(key)

    seen_b: set[tuple[str, str, str]] = set()
    positions: dict[tuple[str, str], set[int]] = {}
    for row in rows_b:
        if not row.student_id_a or not row.student_id_b or not row.course_id:
            raise ValueError("Table 2 student/course IDs cannot be empty")
        if row.student_id_a == row.student_id_b:
            raise ValueError(f"Table 2 self-friend is not allowed: {row.student_id_a}")
        if row.student_id_a not in students or row.student_id_b not in students:
            raise ValueError("Every Table 2 student must also exist in Table 1")
        if row.course_id not in courses:
            raise ValueError("Every Table 2 course must also exist in Table 1")
        if row.position <= 0:
            raise ValueError("Table 2 Position must be > 0")
        key = (row.student_id_a, row.student_id_b, row.course_id)
        if key in seen_b:
            raise ValueError(f"Table 2 duplicate row: {key}")
        seen_b.add(key)
        group = (row.student_id_a, row.course_id)
        group_positions = positions.setdefault(group, set())
        if row.position in group_positions:
            raise ValueError(f"Table 2 duplicate Position in group: {group}")
        group_positions.add(row.position)


def run_hbs_social(
    csv_a: Path,
    csv_b: Path,
    *,
    csv_lambda: Path | None = None,
    cap_default: int,
    b: int,
    seed: int,
    draft_rounds: int | None = None,
    post_iters: int = 0,
    improve_mode: str | None = None,
    move_type: str | None = None,
    objective_scope: str | None = None,
    initial_method: str = "sequential",
    sequence: str = "snake",
    pick_rule: str = "personal",
    progress: bool = False,
    sanity_checks: bool = False,
    delta_check_every: int = 0,
    progress_cb=None,
) -> RunResult:
    """
    Public API function: run a single allocation using the social snake draft.

    This is a thin orchestration layer:
      - Validates parameters
      - Loads CSV inputs
      - Builds and runs the draft engine

    Keeping a stable, simple function interface is useful for notebooks/tests
    and avoids coupling callers to CLI details.
    """
    if cap_default <= 0:
        raise ValueError("cap_default must be > 0")
    if b <= 0:
        raise ValueError("b must be > 0")
    if post_iters < 0:
        raise ValueError("post_iters must be >= 0")
    move_type, objective_scope, effective_improve_mode = normalize_improvement_config(
        improve_mode=improve_mode,
        move_type=move_type,
        objective_scope=objective_scope,
    )
    if initial_method not in CANONICAL_INITIAL_METHODS:
        allowed = ", ".join(CANONICAL_INITIAL_METHODS)
        raise ValueError(f"initial_method must be one of: {allowed}")
    sequence = normalize_sequence(sequence)
    pick_rule = normalize_pick_rule(pick_rule)
    if delta_check_every < 0:
        raise ValueError("delta_check_every must be >= 0")
    if draft_rounds is None:
        draft_rounds = b
    if draft_rounds < 0:
        raise ValueError("draft_rounds must be >= 0")
    if draft_rounds > b:
        raise ValueError("draft_rounds must be <= b")

    rows_a = _read_table_1(csv_a)
    rows_b = _read_table_2(csv_b)
    _validate_input_rows(rows_a, rows_b)
    student_lambdas: dict[str, float] | None = None
    if csv_lambda is not None:
        lambda_rows = _read_table_lambda(csv_lambda)
        student_lambdas = {}
        for row in lambda_rows:
            if not (0.0 <= row.lambda_friend <= 1.0):
                raise ValueError(
                    f"LambdaFriend must be in [0,1], got {row.lambda_friend} for {row.student_id}"
                )
            student_lambdas[row.student_id] = row.lambda_friend

    total_iters = draft_rounds + post_iters
    config = _RunConfig(
        default_capacity=cap_default,
        max_courses=b,
        draft_rounds=draft_rounds,
        post_iters=post_iters,
        total_iters=total_iters,
        move_type=move_type,
        objective_scope=objective_scope,
        effective_improve_mode=effective_improve_mode,
        progress=progress,
        seed=seed,
        sanity_checks=sanity_checks,
        delta_check_every=delta_check_every,
        initial_method=initial_method,
        sequence=sequence,
        pick_rule=pick_rule,
        progress_cb=progress_cb,
    )
    engine = _HbsSocialDraftEngine(
        individual_prefs=rows_a,
        pair_prefs=rows_b,
        student_lambdas=student_lambdas,
        config=config,
    )
    return engine.run()
