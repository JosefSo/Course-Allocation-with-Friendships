import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.append(str(Path(__file__).resolve().parents[1]))

from HBS.hbs_api import CANONICAL_IMPROVE_MODES, run_hbs_social


class TestNewUiIntegration(unittest.TestCase):
    def _tables(self, root: Path) -> tuple[Path, Path]:
        table1 = root / "table1.csv"
        table2 = root / "table2.csv"
        table1.write_text(
            "StudentID,CourseID,Score,Position\n"
            "S1,C1,5,1\nS1,C2,4,2\n"
            "S2,C1,4,2\nS2,C2,5,1\n"
            "S3,C1,5,1\nS3,C2,4,2\n",
            encoding="utf-8",
        )
        table2.write_text(
            "StudentID_A,StudentID_B,CourseID,Position,Score\n"
            "S1,S2,C1,1,5\nS2,S1,C1,1,5\n"
            "S2,S3,C2,1,5\nS3,S2,C2,1,5\n",
            encoding="utf-8",
        )
        return table1, table2

    def test_all_post_modes_support_new_draft_options_and_progress(self) -> None:
        with TemporaryDirectory() as tmp:
            table1, table2 = self._tables(Path(tmp))
            for mode in CANONICAL_IMPROVE_MODES:
                events: list[dict] = []
                result = run_hbs_social(
                    table1,
                    table2,
                    cap_default=2,
                    b=1,
                    seed=7,
                    draft_rounds=1,
                    post_iters=1,
                    improve_mode=mode,
                    sequence="n-first",
                    pick_rule="social",
                    progress_cb=events.append,
                    sanity_checks=True,
                )
                self.assertEqual(set(result.alloc), {"S1", "S2", "S3"})
                self.assertTrue(any(e.get("stage") == "draft" for e in events))
                self.assertIn("egalitarian_welfare", result.metrics_extended.values)
                self.assertIn("ef1_violation_share_total", result.metrics_extended.values)

    def test_global_modes_do_not_reduce_total_welfare(self) -> None:
        with TemporaryDirectory() as tmp:
            table1, table2 = self._tables(Path(tmp))
            baseline = run_hbs_social(
                table1,
                table2,
                cap_default=2,
                b=1,
                seed=5,
                draft_rounds=1,
                post_iters=0,
            ).summary.total_utility
            for mode in ("swap-global", "drop-add-global", "hybrid-global"):
                improved = run_hbs_social(
                    table1,
                    table2,
                    cap_default=2,
                    b=1,
                    seed=5,
                    draft_rounds=1,
                    post_iters=5,
                    improve_mode=mode,
                ).summary.total_utility
                self.assertGreaterEqual(improved + 1e-9, baseline)

    def test_table2_cannot_introduce_unknown_students(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            table1 = root / "table1.csv"
            table2 = root / "table2.csv"
            table1.write_text(
                "StudentID,CourseID,Score,Position\nS1,C1,5,1\n",
                encoding="utf-8",
            )
            table2.write_text(
                "StudentID_A,StudentID_B,CourseID,Position,Score\n"
                "S1,S2,C1,1,5\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Table 2 student"):
                run_hbs_social(
                    table1,
                    table2,
                    cap_default=1,
                    b=1,
                    seed=1,
                )


if __name__ == "__main__":
    unittest.main()
