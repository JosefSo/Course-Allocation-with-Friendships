import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from HBS.hbs_metrics import compute_gini_index, compute_total_utility


class TestGiniIndex(unittest.TestCase):
    def test_gini_zero_for_equal_values(self) -> None:
        values = [1.0, 1.0, 1.0]
        self.assertAlmostEqual(compute_gini_index(values), 0.0, places=9)

    def test_gini_simple_inequality(self) -> None:
        values = [0.0, 0.0, 1.0]
        self.assertAlmostEqual(compute_gini_index(values), 2.0 / 3.0, places=9)

    def test_gini_clamps_negatives(self) -> None:
        values = [-1.0, 1.0]
        self.assertAlmostEqual(compute_gini_index(values), 0.5, places=9)

    def test_total_utility_sum(self) -> None:
        values = [1.25, 2.5, 0.25]
        self.assertAlmostEqual(compute_total_utility(values), 4.0, places=9)


if __name__ == "__main__":
    unittest.main()
