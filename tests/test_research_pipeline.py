from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.append(str(Path(__file__).resolve().parents[1]))

from HBS.hbs_research import run_research_config
from HBS.hbs_statistics import (
    bootstrap_mean_ci,
    holm_adjust,
    rank_biserial_from_differences,
)


class TestResearchStatistics(unittest.TestCase):
    def test_holm_is_monotone_and_bounded(self) -> None:
        adjusted = holm_adjust({"a": 0.01, "b": 0.03, "c": 0.2})
        self.assertAlmostEqual(adjusted["a"], 0.03)
        self.assertGreaterEqual(adjusted["b"], adjusted["a"])
        self.assertLessEqual(max(adjusted.values()), 1.0)

    def test_bootstrap_is_reproducible(self) -> None:
        first = bootstrap_mean_ci([1.0, 2.0, 3.0], resamples=100, seed=7)
        second = bootstrap_mean_ci([1.0, 2.0, 3.0], resamples=100, seed=7)
        self.assertEqual(first, second)

    def test_rank_biserial_direction(self) -> None:
        self.assertAlmostEqual(rank_biserial_from_differences([1, 2, 3]), 1.0)
        self.assertAlmostEqual(rank_biserial_from_differences([-1, -2, -3]), -1.0)
        self.assertAlmostEqual(rank_biserial_from_differences([0, 0]), 0.0)


class TestResearchPipeline(unittest.TestCase):
    def test_small_versioned_config_persists_provenance_and_reports(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            table1 = root / "table1.csv"
            table2 = root / "table2.csv"
            output = root / "out"
            config_path = root / "config.json"
            table1.write_text(
                "StudentID,CourseID,Score,Position\n"
                "A,C1,10,1\nA,C2,5,2\n"
                "B,C2,10,1\nB,C1,5,2\n",
                encoding="utf-8",
            )
            table2.write_text(
                "StudentID_A,StudentID_B,CourseID,Position,Score\n"
                "A,B,C1,1,5\nB,A,C2,1,5\n",
                encoding="utf-8",
            )
            config = {
                "schema_version": 1,
                "experiment_id": "ci-small",
                "dataset": {
                    "table1": "table1.csv",
                    "table2": "table2.csv",
                    "network_model": "legacy-independent",
                },
                "allocation": {
                    "cap_default": 2,
                    "b": 1,
                    "draft_rounds": 1,
                    "post_iters": 0,
                },
                "factors": {
                    "initial_methods": ["sequential", "simultaneous-priority"],
                    "sequences": ["snake"],
                    "pick_rules": ["personal"],
                    "post_modes": ["none"],
                    "lambda_values": [0.0, 0.5],
                    "seeds": [1, 2],
                },
                "output_dir": "out",
            }
            config_path.write_text(json.dumps(config), encoding="utf-8")

            result = run_research_config(config_path)
            self.assertEqual(result["runs"], 8)
            for artifact in (
                "research.sqlite3",
                "runs_flat.csv",
                "aggregates.csv",
                "results.html",
                "position_effects.csv",
                "position_effects.html",
                "position_effects.svg",
                "fairness.html",
                "statistics.json",
                "resolved_config.json",
            ):
                self.assertTrue((output / artifact).is_file(), artifact)

            with sqlite3.connect(output / "research.sqlite3") as conn:
                run_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
                metric_count = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
                pick_count = conn.execute("SELECT COUNT(*) FROM pick_events").fetchone()[0]
                substitution = conn.execute(
                    "SELECT COUNT(*) FROM metrics WHERE envy_definition='substitution'"
                ).fetchone()[0]
            self.assertEqual(run_count, 8)
            self.assertGreater(metric_count, 0)
            self.assertGreater(pick_count, 0)
            self.assertGreater(substitution, 0)

            repeated = run_research_config(config_path)
            self.assertEqual(repeated["runs"], 8)
            with sqlite3.connect(output / "research.sqlite3") as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 8)


if __name__ == "__main__":
    unittest.main()
