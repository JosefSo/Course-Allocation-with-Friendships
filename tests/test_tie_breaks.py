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
    student_lambdas: dict[str, float] | None = None,
) -> _HbsSocialDraftEngine:
    config = _RunConfig(
        default_capacity=2,
        max_courses=1,
        draft_rounds=1,
        post_iters=0,
        total_iters=1,
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
        student_lambdas=student_lambdas,
        config=config,
    )


class TestTieBreaks(unittest.TestCase):
    def test_pref_ignores_position_when_score_present(self) -> None:
        individual_prefs = [
            IndividualPref(student_id="S1", course_id="C1", score=5, position=1)
        ]
        pair_prefs = [
            PairPref(student_id_a="S1", student_id_b="S2", course_id="C1", position=1, score=3),
            PairPref(student_id_a="S1", student_id_b="S3", course_id="C1", position=2, score=3),
            PairPref(student_id_a="S2", student_id_b="S1", course_id="C1", position=1, score=1),
            PairPref(student_id_a="S3", student_id_b="S1", course_id="C1", position=1, score=5),
        ]
        engine = _make_engine(individual_prefs=individual_prefs, pair_prefs=pair_prefs)

        pref_1 = engine._friend_preference_utility("S1", "S2", "C1")
        pref_2 = engine._friend_preference_utility("S1", "S3", "C1")
        self.assertAlmostEqual(pref_1, pref_2, places=9)
        self.assertAlmostEqual(pref_1, 0.5, places=9)

    def test_pref_uses_position_when_score_missing(self) -> None:
        individual_prefs = [
            IndividualPref(student_id="S1", course_id="C1", score=5, position=1)
        ]
        pair_prefs = [
            PairPref(student_id_a="S1", student_id_b="S2", course_id="C1", position=1, score=None),
            PairPref(student_id_a="S1", student_id_b="S3", course_id="C1", position=3, score=None),
            PairPref(student_id_a="S2", student_id_b="S1", course_id="C1", position=1, score=None),
            PairPref(student_id_a="S3", student_id_b="S1", course_id="C1", position=1, score=None),
        ]
        engine = _make_engine(individual_prefs=individual_prefs, pair_prefs=pair_prefs)

        pref_rank_1 = engine._friend_preference_utility("S1", "S2", "C1")
        pref_rank_3 = engine._friend_preference_utility("S1", "S3", "C1")
        self.assertAlmostEqual(pref_rank_1, 1.0, places=9)
        self.assertAlmostEqual(pref_rank_3, 1.0 / 3.0, places=9)
        self.assertGreater(pref_rank_1, pref_rank_3)

    def test_course_choice_ties_by_position_first(self) -> None:
        individual_prefs = [
            IndividualPref(student_id="S1", course_id="C1", score=5, position=1),
            IndividualPref(student_id="S1", course_id="C2", score=8, position=2),
        ]
        engine = _make_engine(
            individual_prefs=individual_prefs,
            pair_prefs=[],
            student_lambdas={"S1": 1.0},
        )

        pick_log = engine._run_initial_draft(1)
        self.assertEqual(len(pick_log), 1)
        self.assertEqual(pick_log[0].course_id, "C1")

    def test_course_choice_ties_by_position_when_score_equal(self) -> None:
        individual_prefs = [
            IndividualPref(student_id="S1", course_id="C1", score=5, position=1),
            IndividualPref(student_id="S1", course_id="C2", score=5, position=2),
        ]
        engine = _make_engine(
            individual_prefs=individual_prefs,
            pair_prefs=[],
            student_lambdas={"S1": 1.0},
        )

        pick_log = engine._run_initial_draft(1)
        self.assertEqual(len(pick_log), 1)
        self.assertEqual(pick_log[0].course_id, "C1")

    def test_add_drop_ties_by_position_first(self) -> None:
        individual_prefs = [
            IndividualPref(student_id="S1", course_id="C1", score=5, position=1),
            IndividualPref(student_id="S1", course_id="C2", score=8, position=2),
        ]
        engine = _make_engine(
            individual_prefs=individual_prefs,
            pair_prefs=[],
            student_lambdas={"S1": 1.0},
        )

        self.assertEqual(engine._build_desired_rebuild_list("S1"), ["C1"])


if __name__ == "__main__":
    unittest.main()
