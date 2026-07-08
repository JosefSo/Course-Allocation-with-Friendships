from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

import hbs_web as primary_web


class TestPrimaryWebTableSelection(unittest.TestCase):
    def _tables(self, root: Path) -> tuple[Path, Path, Path]:
        table1 = root / "table1_demo.csv"
        table2 = root / "table2_demo.csv"
        table3 = root / "table3_demo.csv"
        table1.write_text(
            "StudentID,CourseID,Score,Position\nS1,C1,5,1\n",
            encoding="utf-8",
        )
        table2.write_text(
            "StudentID_A,StudentID_B,CourseID,Position,Score\n",
            encoding="utf-8",
        )
        table3.write_text(
            "StudentID,LambdaFriend\nS1,0.5\n",
            encoding="utf-8",
        )
        return table1, table2, table3

    def test_each_table_kind_accepts_only_its_schema(self) -> None:
        with TemporaryDirectory() as tmp:
            table1, table2, table3 = self._tables(Path(tmp))
            primary_web._validate_table_kind(table1, "table1")
            primary_web._validate_table_kind(table2, "table2")
            primary_web._validate_table_kind(table3, "lambda")
            with self.assertRaisesRegex(ValueError, "wrong CSV"):
                primary_web._validate_table_kind(table1, "table2")
            with self.assertRaisesRegex(ValueError, "wrong CSV"):
                primary_web._validate_table_kind(table2, "table1")

    def test_run_rejects_table1_file_in_table2_slot_before_background_job(self) -> None:
        with TemporaryDirectory() as tmp:
            tables_dir = Path(tmp)
            table1, _table2, _table3 = self._tables(tables_dir)
            old_tables_dir = primary_web.TABLES_DIR
            try:
                primary_web.TABLES_DIR = tables_dir
                with self.assertRaisesRegex(ValueError, "table2 selected the wrong CSV"):
                    primary_web._api_run_start(
                        {
                            "csv_a": table1.name,
                            "csv_b": table1.name,
                            "cap_default": 1,
                            "b": 1,
                            "seed": 1,
                        }
                    )
            finally:
                primary_web.TABLES_DIR = old_tables_dir

    def test_ui_filters_table_files_by_real_filename_prefixes(self) -> None:
        source = (ROOT / "webui" / "index.html").read_text(encoding="utf-8")
        self.assertIn("/^(t1|table1)", source)
        self.assertIn("/^(t2|table2)", source)
        self.assertIn("/^(t3|table3)", source)


if __name__ == "__main__":
    unittest.main()
