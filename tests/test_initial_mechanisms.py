from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.append(str(Path(__file__).resolve().parents[1]))

from HBS.hbs_api import (
    CANONICAL_IMPROVE_MODES,
    normalize_pick_rule,
    normalize_sequence,
    run_hbs_social,
)
from HBS.hbs_config import _RunConfig
from HBS.hbs_domain import IndividualPref
from HBS.hbs_engine import _HbsSocialDraftEngine


def _order_engine(students: list[str], sequence: str) -> _HbsSocialDraftEngine:
    prefs = [
        IndividualPref(student_id, "C1", 1, 1)
        for student_id in students
    ]
    config = _RunConfig(
        default_capacity=len(students),
        max_courses=3,
        draft_rounds=3,
        post_iters=0,
        total_iters=3,
        move_type="swap",
        objective_scope="global",
        effective_improve_mode="swap-global",
        progress=False,
        seed=1,
        sanity_checks=False,
        delta_check_every=0,
        sequence=sequence,
    )
    return _HbsSocialDraftEngine(
        individual_prefs=prefs,
        pair_prefs=[],
        student_lambdas=None,
        config=config,
    )


class TestPickingSequences(unittest.TestCase):
    def test_exact_orders_for_three_to_five_students(self) -> None:
        for n in (3, 4, 5):
            order = [f"S{i}" for i in range(1, n + 1)]
            reverse = list(reversed(order))
            last_first = [order[-1], *order[:-1]]
            expected = {
                "round-robin": (order, order, order),
                "snake": (order, reverse, order),
                "reverse-repeat": (order, reverse, reverse),
                "last-first-static": (order, last_first, last_first),
            }
            for sequence, rounds in expected.items():
                engine = _order_engine(order, sequence)
                for round_index, round_order in enumerate(rounds, start=1):
                    self.assertEqual(
                        engine._turn_order(order, round_index),
                        round_order,
                        msg=f"n={n}, sequence={sequence}, round={round_index}",
                    )

    def test_legacy_aliases_are_preserved(self) -> None:
        self.assertEqual(normalize_sequence("n-first"), "reverse-repeat")
        self.assertEqual(normalize_sequence("last-first"), "last-first-static")

    def test_social_alias_is_deprecated_utilitarian(self) -> None:
        with self.assertWarns(DeprecationWarning):
            self.assertEqual(normalize_pick_rule("social"), "utilitarian")


class TestSimultaneousPriority(unittest.TestCase):
    def _write_common_tables(self, root: Path) -> tuple[Path, Path, Path]:
        table1 = root / "table1.csv"
        table2 = root / "table2.csv"
        lambdas = root / "lambda.csv"
        table1.write_text(
            "StudentID,CourseID,Score,Position\n"
            "A,C1,30,1\nA,C2,20,2\nA,C3,10,3\n"
            "B,C2,30,1\nB,C3,20,2\nB,C1,10,3\n"
            "C,C3,30,1\nC,C1,20,2\nC,C2,10,3\n",
            encoding="utf-8",
        )
        table2.write_text(
            "StudentID_A,StudentID_B,CourseID,Position,Score\n",
            encoding="utf-8",
        )
        lambdas.write_text(
            "StudentID,LambdaFriend\nA,0\nB,0\nC,0\n",
            encoding="utf-8",
        )
        return table1, table2, lambdas

    def test_matches_round_robin_at_lambda_zero(self) -> None:
        with TemporaryDirectory() as tmp:
            table1, table2, lambdas = self._write_common_tables(Path(tmp))
            common = dict(
                csv_lambda=lambdas,
                cap_default=2,
                b=2,
                draft_rounds=2,
                post_iters=0,
                seed=0,
                sequence="round-robin",
            )
            sequential = run_hbs_social(
                table1,
                table2,
                initial_method="sequential",
                **common,
            )
            simultaneous = run_hbs_social(
                table1,
                table2,
                initial_method="simultaneous-priority",
                **common,
            )
            self.assertEqual(simultaneous.alloc, sequential.alloc)

    def test_n_first_alias_matches_reverse_repeat_allocation(self) -> None:
        with TemporaryDirectory() as tmp:
            table1, table2, lambdas = self._write_common_tables(Path(tmp))
            common = dict(
                csv_lambda=lambdas,
                cap_default=2,
                b=2,
                draft_rounds=2,
                post_iters=0,
                seed=9,
            )
            legacy = run_hbs_social(table1, table2, sequence="n-first", **common)
            canonical = run_hbs_social(
                table1, table2, sequence="reverse-repeat", **common
            )
            self.assertEqual(legacy.alloc, canonical.alloc)
            self.assertEqual(legacy.pick_log, canonical.pick_log)

    def test_rankings_are_frozen_within_round(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            table1 = root / "table1.csv"
            table2 = root / "table2.csv"
            lambdas = root / "lambda.csv"
            table1.write_text(
                "StudentID,CourseID,Score,Position\n"
                "A,C1,10,1\nA,C2,1,2\n"
                "B,C2,10,1\nB,C1,1,2\n",
                encoding="utf-8",
            )
            table2.write_text(
                "StudentID_A,StudentID_B,CourseID,Position,Score\n"
                "B,A,C1,1,10\n",
                encoding="utf-8",
            )
            lambdas.write_text(
                "StudentID,LambdaFriend\nA,0.8\nB,0.8\n",
                encoding="utf-8",
            )
            common = dict(
                csv_lambda=lambdas,
                cap_default=2,
                b=1,
                draft_rounds=1,
                post_iters=0,
                seed=0,
                sequence="round-robin",
            )
            sequential = run_hbs_social(
                table1, table2, initial_method="sequential", **common
            )
            simultaneous = run_hbs_social(
                table1,
                table2,
                initial_method="simultaneous-priority",
                **common,
            )
            self.assertEqual(sequential.alloc["A"], ["C1"])
            self.assertEqual(sequential.alloc["B"], ["C1"])
            self.assertEqual(simultaneous.alloc["A"], ["C1"])
            self.assertEqual(simultaneous.alloc["B"], ["C2"])

    def test_respects_capacity_quota_and_no_duplicates(self) -> None:
        with TemporaryDirectory() as tmp:
            table1, table2, lambdas = self._write_common_tables(Path(tmp))
            result = run_hbs_social(
                table1,
                table2,
                csv_lambda=lambdas,
                cap_default=2,
                b=2,
                draft_rounds=2,
                post_iters=0,
                seed=4,
                initial_method="simultaneous-priority",
                sanity_checks=True,
            )
            for courses in result.alloc.values():
                self.assertLessEqual(len(courses), 2)
                self.assertEqual(len(courses), len(set(courses)))
            for course_id in ("C1", "C2", "C3"):
                assigned = sum(course_id in courses for courses in result.alloc.values())
                self.assertLessEqual(assigned, 2)

    def test_all_post_modes_accept_simultaneous_allocation(self) -> None:
        with TemporaryDirectory() as tmp:
            table1, table2, lambdas = self._write_common_tables(Path(tmp))
            for mode in CANONICAL_IMPROVE_MODES:
                result = run_hbs_social(
                    table1,
                    table2,
                    csv_lambda=lambdas,
                    cap_default=2,
                    b=2,
                    draft_rounds=2,
                    post_iters=1,
                    improve_mode=mode,
                    seed=3,
                    initial_method="simultaneous-priority",
                    sanity_checks=True,
                )
                self.assertEqual(set(result.alloc), {"A", "B", "C"})

    def test_pick_log_contains_positions_opportunity_and_ex_post_values(self) -> None:
        with TemporaryDirectory() as tmp:
            table1, table2, lambdas = self._write_common_tables(Path(tmp))
            result = run_hbs_social(
                table1,
                table2,
                csv_lambda=lambdas,
                cap_default=2,
                b=1,
                draft_rounds=1,
                post_iters=0,
                seed=2,
            )
            self.assertTrue(result.pick_log)
            for row in result.pick_log:
                self.assertGreaterEqual(row.initial_position, 1)
                self.assertGreaterEqual(row.turn_position, 1)
                self.assertGreaterEqual(row.normalized_turn_position, 0.0)
                self.assertLessEqual(row.normalized_turn_position, 1.0)
                self.assertGreaterEqual(row.friend_opportunity_at_pick, 0.0)
                self.assertGreaterEqual(row.ex_post_course_utility, 0.0)
                self.assertGreaterEqual(row.ex_post_friend_utility, 0.0)
                self.assertGreaterEqual(row.ex_post_combined_utility, 0.0)


if __name__ == "__main__":
    unittest.main()
