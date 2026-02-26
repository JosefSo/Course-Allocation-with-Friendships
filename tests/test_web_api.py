import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

import HBS.hbs_web as hbs_web
from HBS.hbs_web import _list_run_history, _list_table_files, _run_payload


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
        self.assertIn("metrics:", latest["summary_line"])


if __name__ == "__main__":
    unittest.main()
