from __future__ import annotations

import math
from typing import Sequence


def compute_total_utility(per_student_utilities: Sequence[float]) -> float:
    return float(sum(per_student_utilities))


def compute_gini_index(per_student_utilities: Sequence[float]) -> float:
    """
    Deterministic Gini index over non-negative values.

    For sorted values x_1..x_n and X = sum(x):
      G = sum_i (2i - n - 1) * x_i / (n * X)    if X > 0
      G = 0                                     if X == 0
    """

    values = [max(0.0, float(v)) for v in per_student_utilities]
    n = len(values)
    if n == 0:
        return 0.0
    values.sort()

    total = sum(values)
    if total <= 0.0:
        return 0.0

    numerator = 0.0
    for i, x in enumerate(values, start=1):
        numerator += (2 * i - n - 1) * x
    return numerator / (n * total)


def compute_jain_index(values: Sequence[float]) -> float:
    vals = [max(0.0, float(v)) for v in values]
    total = sum(vals)
    if total <= 0.0:
        return 0.0
    denom = sum(v * v for v in vals)
    if denom <= 0.0:
        return 0.0
    n = len(vals)
    return (total * total) / (n * denom)


def compute_theil_index(values: Sequence[float]) -> float:
    vals = [max(0.0, float(v)) for v in values]
    n = len(vals)
    if n == 0:
        return 0.0
    mean = sum(vals) / n
    if mean <= 0.0:
        return 0.0
    total = 0.0
    for v in vals:
        if v <= 0.0:
            continue
        ratio = v / mean
        total += ratio * (0.0 if ratio <= 0.0 else math.log(ratio))
    return total / n


def compute_atkinson_index(values: Sequence[float], *, epsilon: float = 0.5) -> float:
    vals = [max(0.0, float(v)) for v in values]
    n = len(vals)
    if n == 0:
        return 0.0
    mean = sum(vals) / n
    if mean <= 0.0:
        return 0.0
    if epsilon == 1.0:
        # Avoid log(0); ignore zeros in geometric mean (if all zero, mean=0 handled above).
        logs = [math.log(v) for v in vals if v > 0.0]
        if not logs:
            return 0.0
        geo_mean = math.exp(sum(logs) / len(logs))
        return 1.0 - (geo_mean / mean)
    if epsilon < 0.0:
        raise ValueError("epsilon must be >= 0")
    power = 1.0 - epsilon
    mean_power = sum((v ** power) for v in vals) / n
    if mean_power <= 0.0:
        return 0.0
    eq = mean_power ** (1.0 / power)
    return 1.0 - (eq / mean)
