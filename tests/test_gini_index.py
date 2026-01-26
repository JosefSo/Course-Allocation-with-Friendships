import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from HBS.hbs_metrics import compute_gini_index, compute_total_utility


class TestGiniIndex(unittest.TestCase):
    def assertGiniClose(self, actual: float, expected: float, tol: float = 1e-6) -> None:
        self.assertLess(abs(actual - expected), tol)

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

    def test_gini_perfect_equality_known_value(self) -> None:
        values = [50.0, 50.0, 50.0, 50.0]
        self.assertGiniClose(compute_gini_index(values), 0.0)

    def test_gini_strong_inequality_known_value(self) -> None:
        values = [0.0, 0.0, 100.0, 100.0]
        self.assertGiniClose(compute_gini_index(values), 0.5)

    def test_gini_scale_invariance(self) -> None:
        base_values = [0.0, 0.0, 100.0, 100.0]
        scaled_values = [0.0, 0.0, 10.0, 10.0]
        base_gini = compute_gini_index(base_values)
        scaled_gini = compute_gini_index(scaled_values)
        self.assertGiniClose(base_gini, 0.5)
        self.assertGiniClose(scaled_gini, 0.5)
        self.assertGiniClose(base_gini, scaled_gini)

    def test_gini_permutation_invariance(self) -> None:
        values = [100.0, 0.0, 100.0, 0.0]
        self.assertGiniClose(compute_gini_index(values), 0.5)

    def test_gini_edge_cases_zero_or_singleton(self) -> None:
        self.assertGiniClose(compute_gini_index([0.0, 0.0, 0.0]), 0.0)
        self.assertGiniClose(compute_gini_index([42.0]), 0.0)


if __name__ == "__main__":
    unittest.main()
