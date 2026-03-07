import csv
import sqlite3
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

import HBS.hbs_experiments as hbs_experiments
from HBS.hbs_experiments import (
    Scenario,
    SweepRun,
    _allocation_hash,
    _canonical_allocation_json,
    _compute_stability_for_group,
    run_experiment_suite,
)


def _write_small_tables(base: Path) -> None:
    (base / "table1_small.csv").write_text(
        "\n".join(
            [
                "StudentID,CourseID,Score,Position",
                "S1,C1,5,1",
                "S1,C2,4,2",
                "S2,C1,4,2",
                "S2,C2,5,1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (base / "table2_small.csv").write_text(
        "StudentID_A,StudentID_B,CourseID,Position,Score\n",
        encoding="utf-8",
    )
    (base / "table3_small.csv").write_text(
        "\n".join(
            [
                "StudentID,LambdaFriend",
                "S1,0.4",
                "S2,0.4",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _make_run(
    *,
    post_iters: int,
    signature: str,
    improve_mode: str,
    has_noop: bool,
    has_early_stop: bool,
) -> SweepRun:
    move_type, objective_scope = improve_mode.rsplit("-", 1)
    return SweepRun(
        scenario_id="X",
        table1_ref="t1.csv",
        table2_ref="t2.csv",
        lambda_ref="t3.csv",
        cap_default=1,
        b=1,
        draft_rounds=1,
        seed=11,
        post_iters=post_iters,
        move_type=move_type,
        objective_scope=objective_scope,
        improve_mode=improve_mode,
        total_utility=1.0,
        gini_total_norm=0.1,
        gini_base_norm=0.2,
        metrics_extended={},
        metrics_maxima={},
        allocation_hash=signature.split("|")[0],
        summary_signature=signature.split("|")[1],
        post_log_len=post_iters,
        has_noop=has_noop,
        has_early_stop=has_early_stop,
        artifact_dir=".",
        allocation_path="allocation.json",
        post_allocation_path="post_allocation.csv",
        summary_path="summary.csv",
        metrics_extended_path="metrics_extended.csv",
    )


class TestExperimentsHelpers(unittest.TestCase):
    def test_allocation_hash_is_key_order_invariant(self) -> None:
        alloc_a = {"S2": ["C2"], "S1": ["C1", "C3"]}
        alloc_b = {"S1": ["C1", "C3"], "S2": ["C2"]}

        canonical_a = _canonical_allocation_json(alloc_a)
        canonical_b = _canonical_allocation_json(alloc_b)
        hash_a = _allocation_hash(alloc_a)
        hash_b = _allocation_hash(alloc_b)

        self.assertEqual(canonical_a, canonical_b)
        self.assertEqual(hash_a, hash_b)

    def test_stability_detector_finds_threshold_and_classification(self) -> None:
        runs = [
            _make_run(
                post_iters=0,
                signature="hA|sA",
                improve_mode="hybrid-global",
                has_noop=False,
                has_early_stop=False,
            ),
            _make_run(
                post_iters=1,
                signature="hB|sB",
                improve_mode="hybrid-global",
                has_noop=False,
                has_early_stop=False,
            ),
            _make_run(
                post_iters=5,
                signature="hB|sB",
                improve_mode="hybrid-global",
                has_noop=True,
                has_early_stop=True,
            ),
            _make_run(
                post_iters=10,
                signature="hB|sB",
                improve_mode="hybrid-global",
                has_noop=True,
                has_early_stop=True,
            ),
        ]

        check = _compute_stability_for_group(runs)
        self.assertEqual(check.stable_from_post, 1)
        self.assertFalse(check.all_equal)
        self.assertEqual(check.classification, "hybrid_early_stop")


class TestExperimentsIntegration(unittest.TestCase):
    def test_small_sweep_persists_outputs_and_db_rows(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            tables_dir = tmp_path / "tables"
            out_dir = tmp_path / "results"
            db_path = out_dir / "experiments.sqlite"
            tables_dir.mkdir(parents=True, exist_ok=True)
            _write_small_tables(tables_dir)

            scenario = Scenario(
                scenario_id="TEST",
                table1_ref="table1_small.csv",
                table2_ref="table2_small.csv",
                lambda_ref="table3_small.csv",
                cap_default=1,
                b=1,
                draft_rounds=1,
            )

            old_tables_dir = hbs_experiments.TABLES_DIR
            try:
                hbs_experiments.TABLES_DIR = tables_dir
                result = run_experiment_suite(
                    out_dir=out_dir,
                    db_path=db_path,
                    seed_start=1,
                    seed_count=1,
                    post_grid=[0, 1],
                    modes=["swap"],
                    resume=False,
                    progress=False,
                    scenarios=[scenario],
                )
            finally:
                hbs_experiments.TABLES_DIR = old_tables_dir

            self.assertEqual(result.total_planned_runs, 2)
            self.assertEqual(result.total_runs_used, 2)
            self.assertEqual(result.runs_executed, 2)
            self.assertTrue(result.runs_flat_csv.exists())
            self.assertTrue(result.mode_post_agg_csv.exists())
            self.assertTrue(result.stability_csv.exists())
            self.assertTrue(result.report_md.exists())

            with sqlite3.connect(db_path) as conn:
                run_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
                event_count = conn.execute("SELECT COUNT(*) FROM post_events").fetchone()[0]
                stability_count = conn.execute("SELECT COUNT(*) FROM stability_checks").fetchone()[0]

            self.assertEqual(run_count, 2)
            self.assertGreaterEqual(event_count, 1)
            self.assertEqual(stability_count, 1)

            with result.runs_flat_csv.open("r", encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2)


if __name__ == "__main__":
    unittest.main()
