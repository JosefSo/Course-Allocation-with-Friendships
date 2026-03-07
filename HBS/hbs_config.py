from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class _RunConfig:
    """
    User-controlled parameters that define the draft and its objective.
    """

    default_capacity: int
    max_courses: int
    draft_rounds: int
    post_iters: int
    total_iters: int
    move_type: str
    objective_scope: str
    effective_improve_mode: str
    progress: bool
    seed: int
    sanity_checks: bool
    delta_check_every: int
