from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


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
    # Initial allocation architecture:
    #   "sequential"            - live reactive draft.
    #   "simultaneous-priority" - frozen per-round rankings resolved by one priority.
    initial_method: str = "sequential"
    # Picking sequence (fair-division terminology):
    #   "snake"       - balanced alternation: 1..n, n..1, 1..n, ...
    #   "round-robin" - 1..n every round
    #   "reverse-repeat"   - 1..n, then n..1 in every later round.
    #   "last-first-static"- 1..n, then n,1,..,n-1 in every later round.
    sequence: str = "snake"
    # Pick rule during the draft:
    #   "personal" - each student maximizes their own utility U(s,c).
    #   "utilitarian" - each student maximizes marginal global welfare
    #                U(s,c) + SocialGain(s,c) (internalizes friendship externalities).
    pick_rule: str = "personal"
    # Optional callback receiving small progress events during the run,
    # e.g. {"stage": "swap", "iter": 5, "event": "S1:C2 <-> S7:C4", "delta": 0.01}.
    # Used by the web UI; None keeps the engine silent.
    progress_cb: Callable[[dict], None] | None = None
