import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from HBS.hbs_config import _RunConfig
from HBS.hbs_domain import IndividualPref, PairPref
from typing import Optional

from HBS.hbs_engine import _HbsSocialDraftEngine


def _make_engine(
    *,
    individual_prefs: list[IndividualPref],
    pair_prefs: list[PairPref],
    student_lambdas: Optional[dict[str, float]] = None,
) -> _HbsSocialDraftEngine:
    config = _RunConfig(
        default_capacity=2,
        max_courses=1,
        draft_rounds=0,
        post_iters=0,
        total_iters=0,
        improve_mode="swap",
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


class TestFriendBonus(unittest.TestCase):
    def test_friend_bonus_reactive(self) -> None:
        prefs = [
            IndividualPref(student_id="S1", course_id="C1", score=10, position=1),
            IndividualPref(student_id="S2", course_id="C1", score=10, position=1),
        ]
        pair_prefs = [
            PairPref(student_id_a="S1", student_id_b="S2", course_id="C1", position=1)
        ]
        engine = _make_engine(
            individual_prefs=prefs,
            pair_prefs=pair_prefs,
            student_lambdas={"S1": 1.0, "S2": 1.0},
        )

        self.assertAlmostEqual(engine._friend_bonus_reactive("S1", "C1"), 0.0, places=9)

        engine._alloc_set["S2"].add("C1")
        engine._alloc_list["S2"].append("C1")

        bonus = engine._friend_bonus_reactive("S1", "C1")
        self.assertAlmostEqual(bonus, 1.0, places=9)

        total, base, friend_bonus = engine._utility_components("S1", "C1")
        self.assertAlmostEqual(base, 1.0, places=9)
        self.assertAlmostEqual(friend_bonus, 1.0, places=9)
        self.assertAlmostEqual(total, 2.0, places=9)


if __name__ == "__main__":
    unittest.main()
