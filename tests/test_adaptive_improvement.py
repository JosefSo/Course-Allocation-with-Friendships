import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.append(str(Path(__file__).resolve().parents[1]))

from HBS.hbs_api import run_hbs_social


def _write_tables(csv_a: Path, csv_b: Path) -> None:
    csv_a.write_text(
        "\n".join(
            [
                "StudentID,CourseID,Score,Position",
                # S1 prefers C1 initially, but will benefit from moving to C2 after friends are there.
                "S1,C1,5,1",
                "S1,C2,4,2",
                "S1,C3,1,3",
                # S2 and S3 strongly prefer C2.
                "S2,C2,5,1",
                "S2,C1,4,2",
                "S2,C3,1,3",
                "S3,C2,5,1",
                "S3,C1,4,2",
                "S3,C3,1,3",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    csv_b.write_text(
        "\n".join(
            [
                "StudentID_A,StudentID_B,CourseID,Position,Score",
                # Mutual friend preferences on C2 to create positive externalities.
                "S1,S2,C2,1,5",
                "S1,S3,C2,2,5",
                "S2,S1,C2,1,5",
                "S2,S3,C2,2,5",
                "S3,S1,C2,1,5",
                "S3,S2,C2,2,5",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_tradeoff_tables(csv_a: Path, csv_b: Path) -> None:
    csv_a.write_text(
        "\n".join(
            [
                "StudentID,CourseID,Score,Position",
                # S1 prefers C2 and is initially forced into C1.
                "S1,C1,1,2",
                "S1,C2,5,1",
                # S2 prefers C2 and is the holder after draft.
                "S2,C1,1,2",
                "S2,C2,5,1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    csv_b.write_text(
        "StudentID_A,StudentID_B,CourseID,Position,Score\n",
        encoding="utf-8",
    )


class TestAdaptiveImprovement(unittest.TestCase):
    def test_hybrid_global_add_drop_improves_and_stops_early(self) -> None:
        with TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            csv_a = workdir / "table1.csv"
            csv_b = workdir / "table2.csv"
            _write_tables(csv_a, csv_b)

            result = run_hbs_social(
                csv_a,
                csv_b,
                cap_default=3,
                b=1,
                seed=5,  # Ensures S1 drafts before S2/S3.
                draft_rounds=1,
                post_iters=5,
                improve_mode="hybrid-global",
                delta_check_every=1,
            )

            # S1 should be pulled into C2 after friends draft into C2.
            self.assertIn("C2", result.alloc["S1"])
            self.assertTrue(
                any(r.event_type == "HYBRID_GLOBAL_DROP_ADD" for r in result.post_log)
            )

            # Early stop: post_log should contain a no-op row and be shorter than post_iters.
            self.assertLess(len(result.post_log), 5)
            self.assertEqual(result.post_log[-1].event_type, "")

    def test_hybrid_personal_accepts_student_gain_when_global_is_not_positive(self) -> None:
        with TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            csv_a = workdir / "table1.csv"
            csv_b = workdir / "table2.csv"
            _write_tradeoff_tables(csv_a, csv_b)

            result_global = run_hbs_social(
                csv_a,
                csv_b,
                cap_default=1,
                b=1,
                seed=1,
                draft_rounds=1,
                post_iters=1,
                improve_mode="hybrid-global",
                delta_check_every=1,
            )
            result_personal = run_hbs_social(
                csv_a,
                csv_b,
                cap_default=1,
                b=1,
                seed=1,
                draft_rounds=1,
                post_iters=1,
                improve_mode="hybrid-personal",
                delta_check_every=1,
            )

            self.assertFalse(
                any(r.event_type == "HYBRID_GLOBAL_SWAP" for r in result_global.post_log)
            )
            self.assertTrue(
                any(r.event_type == "HYBRID_PERSONAL_SWAP" for r in result_personal.post_log)
            )

            # In personal mode, S1 should gain C2 despite non-positive global delta.
            self.assertIn("C2", result_personal.alloc["S1"])
            self.assertIn("C1", result_personal.alloc["S2"])

            # Capacity/duplicates invariants.
            self.assertEqual(
                len(result_personal.alloc["S1"]),
                len(set(result_personal.alloc["S1"])),
            )
            self.assertEqual(
                len(result_personal.alloc["S2"]),
                len(set(result_personal.alloc["S2"])),
            )

    def test_hybrid_personal_is_reproducible_with_same_seed(self) -> None:
        with TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            csv_a = workdir / "table1.csv"
            csv_b = workdir / "table2.csv"
            _write_tables(csv_a, csv_b)

            result_1 = run_hbs_social(
                csv_a,
                csv_b,
                cap_default=3,
                b=1,
                seed=5,
                draft_rounds=1,
                post_iters=5,
                improve_mode="hybrid-personal",
                delta_check_every=1,
            )
            result_2 = run_hbs_social(
                csv_a,
                csv_b,
                cap_default=3,
                b=1,
                seed=5,
                draft_rounds=1,
                post_iters=5,
                improve_mode="hybrid-personal",
                delta_check_every=1,
            )

            self.assertEqual(result_1.alloc, result_2.alloc)
            self.assertEqual(result_1.post_log, result_2.post_log)

    def test_swap_personal_accepts_local_gain(self) -> None:
        with TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            csv_a = workdir / "table1.csv"
            csv_b = workdir / "table2.csv"
            _write_tradeoff_tables(csv_a, csv_b)

            result_global = run_hbs_social(
                csv_a,
                csv_b,
                cap_default=1,
                b=1,
                seed=1,
                draft_rounds=1,
                post_iters=1,
                improve_mode="swap-global",
            )
            result_personal = run_hbs_social(
                csv_a,
                csv_b,
                cap_default=1,
                b=1,
                seed=1,
                draft_rounds=1,
                post_iters=1,
                improve_mode="swap-personal",
            )

            self.assertFalse(any(r.event_type == "SWAP_GLOBAL" for r in result_global.post_log))
            self.assertTrue(any(r.event_type == "SWAP_PERSONAL" for r in result_personal.post_log))
            self.assertIn("C2", result_personal.alloc["S1"])


if __name__ == "__main__":
    unittest.main()
