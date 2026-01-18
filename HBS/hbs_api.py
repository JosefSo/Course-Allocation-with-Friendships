from __future__ import annotations

from pathlib import Path

from .hbs_config import _RunConfig
from .hbs_domain import RunResult
from .hbs_engine import _HbsSocialDraftEngine
from .hbs_io import _read_table_1, _read_table_2, _read_table_lambda


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
    improve_mode: str = "swap",
    progress: bool = False,
    sanity_checks: bool = False,
    delta_check_every: int = 0,
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
    if improve_mode not in {"swap", "add-drop"}:
        raise ValueError("improve_mode must be one of: swap, add-drop")
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
        improve_mode=improve_mode,
        progress=progress,
        seed=seed,
        sanity_checks=sanity_checks,
        delta_check_every=delta_check_every,
    )
    engine = _HbsSocialDraftEngine(
        individual_prefs=rows_a,
        pair_prefs=rows_b,
        student_lambdas=student_lambdas,
        config=config,
    )
    return engine.run()
