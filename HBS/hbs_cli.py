from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .hbs_api import run_hbs_social
from .hbs_io import (
    _write_allocation_csv,
    _write_metrics_extended_csv,
    _write_post_alloc_csv,
    _write_summary_csv,
)

LOG = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="HBS Snake Draft + social (reactive) utilities",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--csv-a", type=Path, default=Path("tables/table1_individual.csv"))
    p.add_argument("--csv-b", type=Path, default=Path("tables/table2_pair.csv"))
    p.add_argument(
        "--csv-lambda",
        type=Path,
        default=None,
        help="CSV с per-student lambda (StudentID, LambdaFriend)",
    )
    p.add_argument("--cap-default", type=int, default=10)
    p.add_argument("--b", type=int, default=3, help="Максимум курсов на студента")
    p.add_argument(
        "--draft-rounds",
        type=int,
        default=None,
        help="Количество раундов драфта (по умолчанию = b)",
    )
    p.add_argument(
        "--post-iters",
        "--n",
        dest="post_iters",
        type=int,
        default=None,
        help="Количество итераций пост-фазы (alias: --n, по умолчанию 0)",
    )
    p.add_argument(
        "--improve-mode",
        choices=["swap", "add-drop", "adaptive"],
        default="swap",
        help=(
            "Режим улучшений после драфта: swap (обмены), add-drop (HBS-style) "
            "или adaptive (snake-order pull + swap/add-drop)"
        ),
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--progress",
        action="store_true",
        help="Печатать прогресс по итерациям (draft/improve)",
    )
    p.add_argument(
        "--out-allocation",
        type=Path,
        default=Path("allocation.csv"),
        help="CSV с результатами драфта (только round picks)",
    )
    p.add_argument(
        "--out-adddrop",
        type=Path,
        default=Path("post_allocation.csv"),
        help="CSV с логом add/drop или swap событий (после драфта)",
    )
    p.add_argument("--out-summary", type=Path, default=Path("summary.csv"))
    p.add_argument(
        "--out-metrics-extended",
        type=Path,
        default=Path("metrics_extended.csv"),
        help="CSV с расширенными метриками",
    )
    p.add_argument(
        "--sanity-checks",
        action="store_true",
        help="Включить дополнительные инварианты/проверки корректности",
    )
    p.add_argument(
        "--delta-check-every",
        type=int,
        default=0,
        help="Проверять _swap_delta() каждые N свопов (0 = выкл)",
    )
    p.add_argument(
        "--log-level",
        default="WARNING",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Logging verbosity",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))
    LOG.debug("Starting run with args=%s", args)

    result = run_hbs_social(
        args.csv_a,
        args.csv_b,
        csv_lambda=args.csv_lambda,
        cap_default=args.cap_default,
        b=args.b,
        draft_rounds=args.draft_rounds,
        post_iters=(args.post_iters if args.post_iters is not None else 0),
        improve_mode=args.improve_mode,
        seed=args.seed,
        progress=args.progress,
        sanity_checks=args.sanity_checks,
        delta_check_every=args.delta_check_every,
    )

    _write_allocation_csv(
        args.out_allocation,
        pick_log=result.pick_log,
    )
    _write_post_alloc_csv(
        args.out_adddrop,
        post_log=result.post_log,
    )
    _write_summary_csv(
        args.out_summary,
        seed=args.seed,
        cap_default=args.cap_default,
        b=args.b,
        draft_rounds=(args.draft_rounds if args.draft_rounds is not None else args.b),
        post_iters=(args.post_iters if args.post_iters is not None else 0),
        summary=result.summary,
    )
    _write_metrics_extended_csv(
        args.out_metrics_extended,
        metrics=result.metrics_extended,
    )

    print(f"OK: {args.out_allocation} ({len(result.pick_log)} picks)")
    print(
        "Metrics: "
        f"TotalUtility={result.summary.total_utility:.6f} "
        f"GiniTotalNorm={result.summary.gini_total_norm:.6f} "
        f"GiniBaseNorm={result.summary.gini_base_norm:.6f}"
    )
    return 0
