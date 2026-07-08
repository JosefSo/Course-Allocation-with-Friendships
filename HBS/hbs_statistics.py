from __future__ import annotations

import itertools
import math
import random
from typing import Sequence


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    """Holm step-down adjusted p-values, monotone in sorted raw p-values."""

    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted: dict[str, float] = {}
    running = 0.0
    count = len(ordered)
    for index, (name, p_value) in enumerate(ordered):
        candidate = min(1.0, (count - index) * float(p_value))
        running = max(running, candidate)
        adjusted[name] = running
    return adjusted


def bootstrap_mean_ci(
    values: Sequence[float],
    *,
    confidence: float = 0.95,
    resamples: int = 1000,
    seed: int = 0,
) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if not (0.0 < confidence < 1.0):
        raise ValueError("confidence must be in (0,1)")
    if resamples <= 0:
        raise ValueError("resamples must be > 0")
    vals = [float(value) for value in values]
    rng = random.Random(seed)
    means = sorted(
        sum(rng.choice(vals) for _ in vals) / len(vals)
        for _ in range(resamples)
    )
    tail = (1.0 - confidence) / 2.0
    low_index = max(0, min(len(means) - 1, int(tail * len(means))))
    high_index = max(
        0,
        min(len(means) - 1, int((1.0 - tail) * len(means)) - 1),
    )
    return means[low_index], means[high_index]


def rank_biserial_from_differences(differences: Sequence[float]) -> float:
    """Matched-pairs rank-biserial correlation with average ranks for ties."""

    nonzero = [float(value) for value in differences if abs(float(value)) > 1e-12]
    if not nonzero:
        return 0.0
    ordered = sorted(enumerate(nonzero), key=lambda item: abs(item[1]))
    ranks = [0.0] * len(nonzero)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and math.isclose(
            abs(ordered[end][1]), abs(ordered[cursor][1]), abs_tol=1e-12
        ):
            end += 1
        average_rank = ((cursor + 1) + end) / 2.0
        for index in range(cursor, end):
            ranks[ordered[index][0]] = average_rank
        cursor = end
    positive = sum(rank for rank, value in zip(ranks, nonzero) if value > 0.0)
    negative = sum(rank for rank, value in zip(ranks, nonzero) if value < 0.0)
    total = positive + negative
    return (positive - negative) / total if total else 0.0


def paired_nonparametric_tests(
    values_by_mechanism: dict[str, Sequence[float]],
) -> dict[str, object]:
    """Friedman followed by Wilcoxon-Holm; requires the research SciPy extra."""

    try:
        from scipy.stats import friedmanchisquare, wilcoxon
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "SciPy is required for inferential statistics; install research_requirements.txt"
        ) from exc

    names = sorted(values_by_mechanism)
    if len(names) < 2:
        raise ValueError("at least two mechanisms are required")
    lengths = {len(values_by_mechanism[name]) for name in names}
    if len(lengths) != 1 or not lengths or next(iter(lengths)) == 0:
        raise ValueError("mechanisms must have the same non-zero paired sample size")

    friedman = None
    if len(names) > 2:
        statistic, p_value = friedmanchisquare(
            *(values_by_mechanism[name] for name in names)
        )
        friedman = {"statistic": float(statistic), "p_value": float(p_value)}

    raw_p: dict[str, float] = {}
    effects: dict[str, float] = {}
    for left, right in itertools.combinations(names, 2):
        left_values = [float(value) for value in values_by_mechanism[left]]
        right_values = [float(value) for value in values_by_mechanism[right]]
        differences = [a - b for a, b in zip(left_values, right_values)]
        key = f"{left}__vs__{right}"
        if all(abs(value) <= 1e-12 for value in differences):
            raw_p[key] = 1.0
        else:
            raw_p[key] = float(wilcoxon(differences, alternative="two-sided").pvalue)
        effects[key] = rank_biserial_from_differences(differences)
    adjusted = holm_adjust(raw_p)
    return {
        "friedman": friedman,
        "pairs": {
            key: {
                "p_value": raw_p[key],
                "holm_p_value": adjusted[key],
                "rank_biserial": effects[key],
            }
            for key in raw_p
        },
    }
