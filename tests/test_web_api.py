import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

import HBS.hbs_web as hbs_web
from HBS.hbs_web import (
    _build_run_history_stats,
    _generate_tables_payload,
    _list_run_history,
    _list_table_files,
    _read_compare_progress,
    _reset_run_history,
    _run_mode_comparison_payload,
    _run_payload,
)


class TestWebApi(unittest.TestCase):
    def setUp(self) -> None:
        self._history_tmp = TemporaryDirectory()
        self._old_history_db = hbs_web.HISTORY_DB_PATH
        hbs_web.HISTORY_DB_PATH = Path(self._history_tmp.name) / "web_history.sqlite3"

    def tearDown(self) -> None:
        hbs_web.HISTORY_DB_PATH = self._old_history_db
        self._history_tmp.cleanup()

    def test_run_payload_success(self) -> None:
        payload = {
            "table1_csv": (
                "StudentID,CourseID,Score,Position\n"
                "S1,C1,100,1\n"
                "S2,C1,90,1\n"
            ),
            "table2_csv": "StudentID_A,StudentID_B,CourseID,Position,Score\n",
            "cap_default": 1,
            "b": 1,
            "seed": 7,
            "draft_rounds": 1,
            "post_iters": 0,
            "improve_mode": "swap",
        }

        result = _run_payload(payload)
        self.assertTrue(result["ok"])
        self.assertEqual(result["config"]["seed"], 7)
        self.assertEqual(result["config"]["move_type"], "swap")
        self.assertEqual(result["config"]["objective_scope"], "global")
        self.assertEqual(result["config"]["improve_mode"], "swap-global")
        self.assertIn("S1", result["allocation"])
        self.assertIn("RoundPicked,StudentID,CourseID", result["csv_outputs"]["allocation"])
        self.assertIsInstance(result["run_history_id"], int)

    def test_run_payload_requires_table1(self) -> None:
        payload = {
            "table1_csv": "",
            "table2_csv": "StudentID_A,StudentID_B,CourseID,Position,Score\n",
        }

        with self.assertRaises(ValueError):
            _run_payload(payload)

    def test_run_payload_with_files(self) -> None:
        with TemporaryDirectory() as tmp:
            tables_dir = Path(tmp)
            (tables_dir / "table1_small.csv").write_text(
                "StudentID,CourseID,Score,Position\n"
                "S1,C1,100,1\n"
                "S2,C1,90,1\n",
                encoding="utf-8",
            )
            (tables_dir / "table2_small.csv").write_text(
                "StudentID_A,StudentID_B,CourseID,Position,Score\n",
                encoding="utf-8",
            )

            old_tables_dir = hbs_web.TABLES_DIR
            try:
                hbs_web.TABLES_DIR = tables_dir
                payload = {
                    "table1_file": "table1_small.csv",
                    "table2_file": "table2_small.csv",
                    "cap_default": 1,
                    "b": 1,
                    "seed": 11,
                    "draft_rounds": 1,
                    "post_iters": 0,
                    "improve_mode": "swap",
                }
                result = _run_payload(payload)
            finally:
                hbs_web.TABLES_DIR = old_tables_dir

        self.assertTrue(result["ok"])
        self.assertEqual(result["config"]["seed"], 11)
        self.assertIn("S1", result["allocation"])

    def test_run_payload_rejects_parent_traversal(self) -> None:
        payload = {
            "table1_file": "../outside.csv",
            "table2_csv": "StudentID_A,StudentID_B,CourseID,Position,Score\n",
        }
        with self.assertRaises(ValueError):
            _run_payload(payload)

    def test_list_table_files(self) -> None:
        with TemporaryDirectory() as tmp:
            tables_dir = Path(tmp)
            (tables_dir / "table1_demo.csv").write_text(
                "StudentID,CourseID,Score,Position\nS1,C1,1,1\n",
                encoding="utf-8",
            )
            (tables_dir / "table2_demo.csv").write_text(
                "StudentID_A,StudentID_B,CourseID,Position,Score\n",
                encoding="utf-8",
            )
            (tables_dir / "table3_lambda_demo.csv").write_text(
                "StudentID,LambdaFriend\nS1,0.2\n",
                encoding="utf-8",
            )

            old_tables_dir = hbs_web.TABLES_DIR
            try:
                hbs_web.TABLES_DIR = tables_dir
                listing = _list_table_files()
            finally:
                hbs_web.TABLES_DIR = old_tables_dir

        self.assertTrue(listing["ok"])
        self.assertIn("table1_demo.csv", listing["table1"])
        self.assertIn("table2_demo.csv", listing["table2"])
        self.assertIn("table3_lambda_demo.csv", listing["lambda"])

    def test_generate_tables_payload_writes_selected_files(self) -> None:
        with TemporaryDirectory() as tmp:
            tables_dir = Path(tmp)
            old_tables_dir = hbs_web.TABLES_DIR
            try:
                hbs_web.TABLES_DIR = tables_dir
                result = _generate_tables_payload(
                    {
                        "students": 4,
                        "courses": 3,
                        "seed": 30,
                        "generate_table1": True,
                        "generate_table2": True,
                        "generate_lambda": False,
                    }
                )
            finally:
                hbs_web.TABLES_DIR = old_tables_dir

            self.assertTrue(result["ok"])
            self.assertEqual(result["created"]["table1"], "table1_4×3.csv")
            self.assertEqual(result["created"]["table2"], "table2_4×3.csv")
            self.assertNotIn("lambda", result["created"])
            self.assertTrue((tables_dir / "table1_4×3.csv").exists())
            self.assertTrue((tables_dir / "table2_4×3.csv").exists())
            self.assertFalse((tables_dir / "table3_4×3.csv").exists())

    def test_run_history_contains_latest_run(self) -> None:
        payload = {
            "table1_csv": (
                "StudentID,CourseID,Score,Position\n"
                "S1,C1,100,1\n"
                "S2,C1,90,1\n"
            ),
            "table2_csv": "StudentID_A,StudentID_B,CourseID,Position,Score\n",
            "cap_default": 2,
            "b": 1,
            "seed": 13,
            "draft_rounds": 1,
            "post_iters": 0,
            "improve_mode": "swap",
        }
        _run_payload(payload)

        history = _list_run_history(limit=10)
        self.assertTrue(history["ok"])
        self.assertGreaterEqual(len(history["items"]), 1)
        latest = history["items"][0]
        self.assertEqual(latest["seed"], 13)
        self.assertEqual(latest["cap_default"], 2)
        self.assertEqual(latest["move_type"], "swap")
        self.assertEqual(latest["objective_scope"], "global")
        self.assertIn("metrics:", latest["summary_line"])

    def test_build_run_history_stats_empty(self) -> None:
        stats = _build_run_history_stats(limit=10)
        self.assertTrue(stats["ok"])
        self.assertEqual(stats["trend"], [])
        self.assertEqual(stats["by_mode"], [])
        self.assertEqual(stats["overall"]["runs_total"], 0)
        self.assertIsNone(stats["overall"]["best_utility"])
        self.assertIsNone(stats["overall"]["best_fairness_g_total"])
        self.assertIsNone(stats["overall"]["best_fairness_g_base"])

    def test_build_run_history_stats_grouping_and_extrema(self) -> None:
        table1_csv = (
            "StudentID,CourseID,Score,Position\n"
            "S1,C1,100,1\n"
            "S2,C1,90,1\n"
        )
        table2_csv = "StudentID_A,StudentID_B,CourseID,Position,Score\n"

        payloads = [
            {
                "table1_csv": table1_csv,
                "table2_csv": table2_csv,
                "cap_default": 1,
                "b": 1,
                "seed": 21,
                "draft_rounds": 1,
                "post_iters": 0,
                "improve_mode": "swap",
            },
            {
                "table1_csv": table1_csv,
                "table2_csv": table2_csv,
                "cap_default": 2,
                "b": 1,
                "seed": 22,
                "draft_rounds": 1,
                "post_iters": 0,
                "improve_mode": "drop-add",
            },
            {
                "table1_csv": table1_csv,
                "table2_csv": table2_csv,
                "cap_default": 1,
                "b": 1,
                "seed": 23,
                "draft_rounds": 1,
                "post_iters": 0,
                "improve_mode": "swap",
            },
        ]
        for payload in payloads:
            _run_payload(payload)

        stats = _build_run_history_stats(limit=10)
        self.assertTrue(stats["ok"])
        trend = stats["trend"]
        self.assertEqual(len(trend), 3)
        self.assertEqual([point["run_index"] for point in trend], [1, 2, 3])
        self.assertEqual(
            [point["improve_mode"] for point in trend],
            ["swap-global", "drop-add-global", "swap-global"],
        )
        self.assertEqual([point["move_type"] for point in trend], ["swap", "drop-add", "swap"])
        self.assertEqual(
            [point["objective_scope"] for point in trend],
            ["global", "global", "global"],
        )

        by_mode_map = {row["improve_mode"]: row for row in stats["by_mode"]}
        self.assertEqual(by_mode_map["swap-global"]["runs"], 2)
        self.assertEqual(by_mode_map["drop-add-global"]["runs"], 1)

        best_utility = max(trend, key=lambda p: p["total_utility"])
        self.assertEqual(stats["overall"]["best_utility"]["run_index"], best_utility["run_index"])
        self.assertAlmostEqual(stats["overall"]["best_utility"]["value"], best_utility["total_utility"])

        best_g_total = min(trend, key=lambda p: p["gini_total_norm"])
        self.assertEqual(
            stats["overall"]["best_fairness_g_total"]["run_index"],
            best_g_total["run_index"],
        )
        self.assertAlmostEqual(
            stats["overall"]["best_fairness_g_total"]["value"],
            best_g_total["gini_total_norm"],
        )

        best_g_base = min(trend, key=lambda p: p["gini_base_norm"])
        self.assertEqual(
            stats["overall"]["best_fairness_g_base"]["run_index"],
            best_g_base["run_index"],
        )
        self.assertAlmostEqual(
            stats["overall"]["best_fairness_g_base"]["value"],
            best_g_base["gini_base_norm"],
        )

    def test_reset_run_history_clears_all_rows(self) -> None:
        payload = {
            "table1_csv": (
                "StudentID,CourseID,Score,Position\n"
                "S1,C1,100,1\n"
                "S2,C1,90,1\n"
            ),
            "table2_csv": "StudentID_A,StudentID_B,CourseID,Position,Score\n",
            "cap_default": 2,
            "b": 1,
            "seed": 15,
            "draft_rounds": 1,
            "post_iters": 0,
            "improve_mode": "swap",
        }
        _run_payload(payload)
        before_reset = _list_run_history(limit=10)
        self.assertGreaterEqual(len(before_reset["items"]), 1)

        reset_result = _reset_run_history()
        self.assertTrue(reset_result["ok"])
        self.assertEqual(reset_result["items"], [])

        after_reset = _list_run_history(limit=10)
        self.assertEqual(after_reset["items"], [])

    def test_stats_after_reset_is_empty(self) -> None:
        payload = {
            "table1_csv": (
                "StudentID,CourseID,Score,Position\n"
                "S1,C1,100,1\n"
                "S2,C1,90,1\n"
            ),
            "table2_csv": "StudentID_A,StudentID_B,CourseID,Position,Score\n",
            "cap_default": 2,
            "b": 1,
            "seed": 16,
            "draft_rounds": 1,
            "post_iters": 0,
            "improve_mode": "swap",
        }
        _run_payload(payload)
        _reset_run_history()
        stats = _build_run_history_stats(limit=10)
        self.assertEqual(stats["overall"]["runs_total"], 0)
        self.assertEqual(stats["trend"], [])
        self.assertEqual(stats["by_mode"], [])

    def test_run_mode_comparison_payload_groups_all_modes(self) -> None:
        payload = {
            "table1_csv": (
                "StudentID,CourseID,Score,Position\n"
                "S1,C1,100,1\n"
                "S1,C2,80,2\n"
                "S2,C1,90,1\n"
                "S2,C2,70,2\n"
            ),
            "table2_csv": "StudentID_A,StudentID_B,CourseID,Position,Score\n",
            "cap_default": 2,
            "b": 1,
            "seed": 31,
            "draft_rounds": 1,
            "post_iters": 0,
            "batch_size": 2,
            "progress_job_id": "test_progress_job",
        }

        result = _run_mode_comparison_payload(payload)

        self.assertTrue(result["ok"])
        self.assertEqual(result["config"]["batch_size"], 2)
        self.assertEqual(result["config"]["parallel_workers"], 6)
        self.assertIn(result["config"]["effective_parallel_workers"], {1, 6})
        self.assertEqual(result["config"]["seed_start"], 31)
        self.assertEqual(result["config"]["seed_end"], 32)
        self.assertEqual(result["overall"]["runs_total"], 12)
        self.assertEqual(len(result["run_history_ids"]), 12)
        self.assertEqual(len(result["by_mode"]), 6)
        for row in result["by_mode"]:
            self.assertEqual(row["runs"], 2)
            self.assertEqual(row["seed_start"], 31)
            self.assertEqual(row["seed_end"], 32)
            self.assertIn("avg_total_utility", row)
            self.assertIn("avg_gini_total_norm", row)
            self.assertIn("avg_gini_base_norm", row)

        history = _list_run_history(limit=20)
        self.assertEqual(len(history["items"]), 12)
        modes = {item["improve_mode"] for item in history["items"]}
        self.assertEqual(
            modes,
            {
                "swap-global",
                "swap-personal",
                "drop-add-global",
                "drop-add-personal",
                "hybrid-global",
                "hybrid-personal",
            },
        )
        progress = _read_compare_progress("test_progress_job")
        self.assertTrue(progress["ok"])
        self.assertEqual(progress["status"], "done")
        self.assertEqual(progress["completed"], 12)
        self.assertEqual(progress["total"], 12)
        self.assertEqual(len(progress["workers"]), 6)


if __name__ == "__main__":
    unittest.main()
