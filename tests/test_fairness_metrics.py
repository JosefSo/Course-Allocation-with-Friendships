from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from HBS.hbs_config import _RunConfig
from HBS.hbs_domain import IndividualPref, PairPref
from HBS.hbs_engine import _HbsSocialDraftEngine
from HBS.hbs_metrics import compute_nash_welfare


def _engine(
    *,
    students: list[str],
    courses: list[str],
    pair_prefs: list[PairPref],
    lambdas: dict[str, float],
) -> _HbsSocialDraftEngine:
    individual_prefs = [
        IndividualPref(
            student_id=student_id,
            course_id=course_id,
            score=len(courses) - index + 1,
            position=index,
        )
        for student_id in students
        for index, course_id in enumerate(courses, start=1)
    ]
    config = _RunConfig(
        default_capacity=len(students),
        max_courses=2,
        draft_rounds=0,
        post_iters=0,
        total_iters=0,
        move_type="swap",
        objective_scope="global",
        effective_improve_mode="swap-global",
        progress=False,
        seed=1,
        sanity_checks=False,
        delta_check_every=0,
    )
    return _HbsSocialDraftEngine(
        individual_prefs=individual_prefs,
        pair_prefs=pair_prefs,
        student_lambdas=lambdas,
        config=config,
    )


def _assign(engine: _HbsSocialDraftEngine, student_id: str, *courses: str) -> None:
    engine._alloc_list[student_id] = list(courses)
    engine._alloc_set[student_id] = set(courses)


class TestNashWelfare(unittest.TestCase):
    def test_zero_policy_excludes_zeros_and_reports_share(self) -> None:
        geomean, zero_share, zero_safe = compute_nash_welfare([0.0, 1.0, 4.0])
        self.assertAlmostEqual(geomean, 2.0)
        self.assertAlmostEqual(zero_share, 1.0 / 3.0)
        self.assertAlmostEqual(zero_safe, math.log(2.0) + math.log(5.0))

    def test_all_zero(self) -> None:
        self.assertEqual(compute_nash_welfare([0.0, 0.0]), (0.0, 1.0, 0.0))

    def test_no_zero_uses_standard_geometric_mean(self) -> None:
        geomean, zero_share, _zero_safe = compute_nash_welfare([1.0, 4.0])
        self.assertAlmostEqual(geomean, 2.0)
        self.assertEqual(zero_share, 0.0)


class TestPreregisteredEf1(unittest.TestCase):
    def _friendship_case(self, lambda_value: float) -> _HbsSocialDraftEngine:
        engine = _engine(
            students=["A", "B"],
            courses=["C1", "C2", "C3"],
            pair_prefs=[
                PairPref("A", "B", "C1", 1, 5),
                PairPref("A", "B", "C2", 1, 5),
            ],
            lambdas={"A": lambda_value, "B": lambda_value},
        )
        _assign(engine, "A", "C3")
        _assign(engine, "B", "C1", "C2")
        return engine

    def test_substitution_and_swap_diverge_with_externality(self) -> None:
        metrics = self._friendship_case(1.0)._envy_ef1_metrics()
        self.assertAlmostEqual(metrics["envy_pair_share_substitution_combined"], 0.5)
        self.assertAlmostEqual(
            metrics["ef1_violation_pair_share_substitution_combined"], 0.5
        )
        self.assertAlmostEqual(metrics["envy_pair_share_swap_combined"], 0.0)
        self.assertAlmostEqual(metrics["ef1_violation_pair_share_swap_combined"], 0.0)
        self.assertGreater(metrics["envy_gap_max_substitution_combined"], 0.0)
        self.assertGreater(metrics["ef1_residual_gap_max_substitution_combined"], 0.0)

    def test_all_definitions_agree_when_lambda_is_zero(self) -> None:
        metrics = self._friendship_case(0.0)._envy_ef1_metrics()
        for metric in (
            "envy_pair_share",
            "ef1_violation_pair_share",
            "ef1_violation_student_share",
            "envy_gap_mean",
            "envy_gap_max",
            "ef1_residual_gap_mean",
            "ef1_residual_gap_max",
        ):
            base = metrics[f"{metric}_base_only_course"]
            self.assertAlmostEqual(base, metrics[f"{metric}_substitution_combined"])
            self.assertAlmostEqual(base, metrics[f"{metric}_swap_combined"])

    def test_legacy_keys_map_to_primary_substitution_metrics(self) -> None:
        metrics = self._friendship_case(1.0)._envy_ef1_metrics()
        self.assertEqual(
            metrics["envy_pairs_share_total"],
            metrics["envy_pair_share_substitution_combined"],
        )
        self.assertEqual(
            metrics["ef1_violation_share_total"],
            metrics["ef1_violation_student_share_substitution_combined"],
        )


class TestOverlapRate(unittest.TestCase):
    def test_denominator_uses_declared_links_on_received_courses(self) -> None:
        engine = _engine(
            students=["A", "B", "C"],
            courses=["C1", "C2"],
            pair_prefs=[
                PairPref("A", "B", "C1", 1, 5),
                PairPref("A", "C", "C1", 2, 5),
                PairPref("A", "C", "C2", 1, 5),
            ],
            lambdas={"A": 0.5, "B": 0.5, "C": 0.5},
        )
        _assign(engine, "A", "C1")
        _assign(engine, "B", "C1")
        _assign(engine, "C", "C2")

        _summary, metrics = engine._compute_metrics()
        self.assertEqual(metrics.values["friend_overlap_total"], 1.0)
        self.assertEqual(metrics.values["friend_possible_overlap_total"], 2.0)
        self.assertAlmostEqual(metrics.values["overlap_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
