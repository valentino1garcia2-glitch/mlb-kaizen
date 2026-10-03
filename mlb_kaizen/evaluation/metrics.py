"""Small, dependency-light scoring and calibration metrics."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


def mean_absolute_error(errors: Iterable[float]) -> float:
    """Return mean absolute error from a sequence of prediction errors."""

    values = list(errors)
    return sum(abs(value) for value in values) / len(values) if values else math.nan


def rmse(errors: Iterable[float]) -> float:
    values = list(errors)
    return math.sqrt(sum(value * value for value in values) / len(values)) if values else math.nan


def brier_score(probabilities: Iterable[float], outcomes: Iterable[int]) -> float:
    pairs = list(zip(probabilities, outcomes))
    if not pairs:
        return math.nan
    return sum((probability - outcome) ** 2 for probability, outcome in pairs) / len(pairs)


def log_loss(probabilities: Iterable[float], outcomes: Iterable[int], eps: float = 1e-15) -> float:
    pairs = list(zip(probabilities, outcomes))
    if not pairs:
        return math.nan
    total = 0.0
    for probability, outcome in pairs:
        p = min(1 - eps, max(eps, probability))
        total += -(outcome * math.log(p) + (1 - outcome) * math.log(1 - p))
    return total / len(pairs)


@dataclass(frozen=True, slots=True)
class CalibrationBin:
    lower: float
    upper: float
    count: int
    mean_predicted: float
    observed_rate: float


def calibration_bins(probabilities: list[float], outcomes: list[int], bin_count: int = 10) -> tuple[CalibrationBin, ...]:
    if bin_count < 1:
        raise ValueError("bin_count must be positive")
    bins: list[CalibrationBin] = []
    for index in range(bin_count):
        lower = index / bin_count
        upper = (index + 1) / bin_count
        selected = [
            (probability, outcome)
            for probability, outcome in zip(probabilities, outcomes)
            if (lower <= probability < upper) or (index == bin_count - 1 and probability == upper)
        ]
        if not selected:
            continue
        bins.append(
            CalibrationBin(
                lower=lower,
                upper=upper,
                count=len(selected),
                mean_predicted=sum(p for p, _ in selected) / len(selected),
                observed_rate=sum(o for _, o in selected) / len(selected),
            )
        )
    return tuple(bins)
