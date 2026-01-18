import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from HBS.hbs_config import _RunConfig
from HBS.hbs_domain import IndividualPref, PairPref
from HBS.hbs_engine import _HbsSocialDraftEngine, _pos_u


def _make_engine(
    *,
    individual_prefs: list[IndividualPref],
    pair_prefs: list[PairPref],
) -> _HbsSocialDraftEngine:
    config = _RunConfig(
        default_capacity=2,
        max_courses=2,
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
        student_lambdas=None,
        config=config,
    )


class TestBaseUtility(unittest.TestCase):
    def test_pos_u_mapping(self) -> None:
        self.assertAlmostEqual(_pos_u(1, 4), 1.0, places=9)
        self.assertAlmostEqual(_pos_u(2, 4), 2.0 / 3.0, places=9)
        self.assertAlmostEqual(_pos_u(4, 4), 0.0, places=9)
        self.assertAlmostEqual(_pos_u(None, 4), 0.0, places=9)

    def test_pos_u_single_course(self) -> None:
        self.assertAlmostEqual(_pos_u(1, 1), 1.0, places=9)
        self.assertAlmostEqual(_pos_u(2, 1), 0.0, places=9)

    def test_base_utility_from_table(self) -> None:
        prefs = [
            IndividualPref(student_id="S1", course_id="C1", score=10, position=1),
            IndividualPref(student_id="S1", course_id="C2", score=5, position=2),
        ]
        engine = _make_engine(individual_prefs=prefs, pair_prefs=[])
        self.assertAlmostEqual(engine._base_utility("S1", "C1"), 1.0, places=9)
        self.assertAlmostEqual(engine._base_utility("S1", "C2"), 0.0, places=9)
        self.assertAlmostEqual(engine._base_utility("S1", "C3"), 0.0, places=9)


if __name__ == "__main__":
    unittest.main()
