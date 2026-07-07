from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from HBS.hbs_config import _RunConfig
from HBS.hbs_domain import IndividualPref, PairPref
from HBS.hbs_engine import _HbsSocialDraftEngine


def _make_engine(
    *,
    individual_prefs: list[IndividualPref],
    pair_prefs: list[PairPref],
    lambdas: dict[str, float] | None = None,
    max_courses: int = 1,
    capacity: int = 4,
) -> _HbsSocialDraftEngine:
    config = _RunConfig(
        default_capacity=capacity,
        max_courses=max_courses,
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


def _prefs(students: list[str], courses: list[str]) -> list[IndividualPref]:
    rows: list[IndividualPref] = []
    for student_id in students:
        for index, course_id in enumerate(courses, start=1):
            rows.append(
                IndividualPref(
                    student_id=student_id,
                    course_id=course_id,
                    score=len(courses) + 1 - index,
                    position=index,
                )
            )
    return rows


def _assign(engine: _HbsSocialDraftEngine, student_id: str, *courses: str) -> None:
    engine._alloc_list[student_id] = list(courses)
    engine._alloc_set[student_id] = set(courses)


def _friend_norm(engine: _HbsSocialDraftEngine, student_id: str, course_id: str) -> float:
    return engine._friend_bonus_reactive(student_id, course_id) / engine._max_friend_bonus(student_id)


class TestFriendNormalization(unittest.TestCase):
    def test_one_friend_one_common_course_normalizes_to_one(self) -> None:
        engine = _make_engine(
            individual_prefs=_prefs(["S1", "S2"], ["C1"]),
            pair_prefs=[PairPref("S1", "S2", "C1", 1, 5)],
            lambdas={"S1": 1.0, "S2": 1.0},
        )
        _assign(engine, "S2", "C1")

        self.assertAlmostEqual(_friend_norm(engine, "S1", "C1"), 1.0)
        total, base, raw_friend = engine._utility_components("S1", "C1")
        self.assertAlmostEqual(base, 1.0)
        self.assertAlmostEqual(raw_friend, 1.0)
        self.assertAlmostEqual(total, 1.0)

    def test_two_friends_on_one_course_normalize_to_one_when_both_overlap(self) -> None:
        engine = _make_engine(
            individual_prefs=_prefs(["S1", "S2", "S3"], ["C1"]),
            pair_prefs=[
                PairPref("S1", "S2", "C1", 1, 5),
                PairPref("S1", "S3", "C1", 2, 5),
            ],
            lambdas={"S1": 1.0, "S2": 1.0, "S3": 1.0},
        )
        _assign(engine, "S2", "C1")
        _assign(engine, "S3", "C1")

        self.assertAlmostEqual(engine._friend_bonus_reactive("S1", "C1"), 2.0)
        self.assertAlmostEqual(_friend_norm(engine, "S1", "C1"), 1.0)

    def test_student_level_denominator_makes_non_best_social_course_less_than_one(self) -> None:
        engine = _make_engine(
            individual_prefs=_prefs(["S1", "S2", "S3"], ["C1", "C2"]),
            pair_prefs=[
                PairPref("S1", "S2", "C1", 1, 5),
                PairPref("S1", "S3", "C1", 2, 5),
                PairPref("S1", "S2", "C2", 1, 5),
            ],
            lambdas={"S1": 1.0, "S2": 1.0, "S3": 1.0},
        )
        _assign(engine, "S2", "C2")

        self.assertAlmostEqual(engine._max_friend_bonus("S1"), 2.0)
        self.assertAlmostEqual(engine._friend_bonus_reactive("S1", "C2"), 1.0)
        self.assertAlmostEqual(_friend_norm(engine, "S1", "C2"), 0.5)

    def test_student_without_friends_has_zero_friend_norm_and_valid_total(self) -> None:
        engine = _make_engine(
            individual_prefs=_prefs(["S1"], ["C1", "C2"]),
            pair_prefs=[],
            lambdas={"S1": 1.0},
        )

        total, base, raw_friend = engine._utility_components("S1", "C1")
        self.assertAlmostEqual(engine._max_friend_bonus("S1"), 1.0)
        self.assertAlmostEqual(raw_friend, 0.0)
        self.assertAlmostEqual(total, 0.0)
        self.assertGreaterEqual(base, 0.0)

    def test_directed_friendship_normalization_differs_by_direction(self) -> None:
        engine = _make_engine(
            individual_prefs=_prefs(["A", "B"], ["C1"]),
            pair_prefs=[PairPref("A", "B", "C1", 1, 5)],
            lambdas={"A": 1.0, "B": 1.0},
        )
        _assign(engine, "A", "C1")
        _assign(engine, "B", "C1")

        self.assertAlmostEqual(_friend_norm(engine, "A", "C1"), 1.0)
        self.assertAlmostEqual(_friend_norm(engine, "B", "C1"), 0.0)


class TestFriendFairnessDiagnostics(unittest.TestCase):
    def test_symmetric_case_has_equal_total_and_social_gini(self) -> None:
        students = ["S1", "S2", "S3", "S4"]
        pair_prefs = [
            PairPref(a, b, "C1", 1, 5)
            for a in students
            for b in students
            if a != b
        ]
        engine = _make_engine(
            individual_prefs=_prefs(students, ["C1", "C2"]),
            pair_prefs=pair_prefs,
            lambdas={s: 1.0 for s in students},
            capacity=4,
        )
        for student_id in students:
            _assign(engine, student_id, "C1")

        _summary, metrics = engine._compute_metrics()
        self.assertAlmostEqual(metrics.values["gini_total_norm"], 0.0)
        self.assertAlmostEqual(metrics.values["gini_friend_norm"], 0.0)
        self.assertAlmostEqual(metrics.values["gini_friend_opportunity_norm"], 0.0)

    def test_unequal_opportunity_social_gini_is_structural(self) -> None:
        students = ["S1", "S2", "S3", "S4"]
        engine = _make_engine(
            individual_prefs=_prefs(students, ["C1", "C2"]),
            pair_prefs=[
                PairPref("S1", "S2", "C1", 1, 5),
                PairPref("S2", "S1", "C1", 1, 5),
            ],
            lambdas={s: 1.0 for s in students},
            capacity=4,
        )
        for student_id in students:
            _assign(engine, student_id, "C1")

        _summary, metrics = engine._compute_metrics()
        self.assertGreater(metrics.values["gini_friend_norm"], 0.0)
        self.assertAlmostEqual(metrics.values["gini_friend_opportunity_norm"], 0.0)
        self.assertAlmostEqual(metrics.values["share_students_no_friend_bonus_opportunity"], 0.5)

    def test_normalization_removes_automatic_advantage_from_more_friends(self) -> None:
        engine = _make_engine(
            individual_prefs=_prefs(["S1", "S2", "S3", "S4"], ["C1"]),
            pair_prefs=[
                PairPref("S1", "S3", "C1", 1, 5),
                PairPref("S2", "S3", "C1", 1, 5),
                PairPref("S2", "S4", "C1", 2, 5),
            ],
            lambdas={"S1": 1.0, "S2": 1.0, "S3": 1.0, "S4": 1.0},
            capacity=4,
        )
        for student_id in ["S1", "S2", "S3", "S4"]:
            _assign(engine, student_id, "C1")

        self.assertAlmostEqual(engine._friend_bonus_reactive("S1", "C1"), 1.0)
        self.assertAlmostEqual(engine._friend_bonus_reactive("S2", "C1"), 2.0)
        self.assertAlmostEqual(_friend_norm(engine, "S1", "C1"), 1.0)
        self.assertAlmostEqual(_friend_norm(engine, "S2", "C1"), 1.0)


if __name__ == "__main__":
    unittest.main()
