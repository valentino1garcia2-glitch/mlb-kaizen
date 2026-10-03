"""Post-hoc probability calibration fitted only on earlier observations."""

from __future__ import annotations

from dataclasses import dataclass
from bisect import bisect_right
from typing import Iterable

from mlb_kaizen.evaluation.metrics import brier_score, log_loss


@dataclass(frozen=True, slots=True)
class BinnedCalibrator:
    """Empirical bin calibrator with Laplace smoothing."""

    boundaries: tuple[float, ...]
    rates: tuple[float, ...]

    @classmethod
    def fit(
        cls,
        probabilities: Iterable[float],
        outcomes: Iterable[int],
        bin_count: int = 10,
        smoothing: float = 1.0,
    ) -> "BinnedCalibrator":
        probabilities = list(probabilities)
        outcomes = list(outcomes)
        if len(probabilities) != len(outcomes) or not probabilities:
            raise ValueError("probabilities and outcomes must be non-empty and equally sized")
        if bin_count < 1 or smoothing < 0:
            raise ValueError("invalid calibration parameters")
        boundaries = tuple(index / bin_count for index in range(1, bin_count + 1))
        rates = []
        for index in range(bin_count):
            lower = index / bin_count
            upper = (index + 1) / bin_count
            selected = [
                outcome
                for probability, outcome in zip(probabilities, outcomes)
                if (lower <= probability < upper) or (index == bin_count - 1 and probability == upper)
            ]
            if selected:
                successes = sum(selected)
                rates.append((successes + smoothing) / (len(selected) + 2 * smoothing))
            else:
                rates.append((lower + upper) / 2)
        return cls(boundaries, tuple(rates))

    def transform(self, probability: float) -> float:
        if not 0 <= probability <= 1:
            raise ValueError("probability must be in [0, 1]")
        index = min(len(self.rates) - 1, bisect_right(self.boundaries, probability))
        return self.rates[index]

    def transform_many(self, probabilities: Iterable[float]) -> tuple[float, ...]:
        return tuple(self.transform(probability) for probability in probabilities)


@dataclass(frozen=True, slots=True)
class TemporalCalibrationReport:
    """Calibration fit on an earlier block and evaluated on a later block."""

    calibration_size: int
    evaluation_size: int
    raw_brier: float
    calibrated_brier: float
    raw_log_loss: float
    calibrated_log_loss: float


def temporal_calibration_report(
    probabilities: list[float], outcomes: list[int], calibration_fraction: float = 0.5
) -> TemporalCalibrationReport:
    if not 0 < calibration_fraction < 1:
        raise ValueError("calibration_fraction must be between zero and one")
    if len(probabilities) != len(outcomes) or len(probabilities) < 4:
        raise ValueError("at least four equally sized probability/outcome observations are required")
    split = max(2, min(len(probabilities) - 2, int(len(probabilities) * calibration_fraction)))
    calibrator = BinnedCalibrator.fit(probabilities[:split], outcomes[:split])
    raw = probabilities[split:]
    target = outcomes[split:]
    calibrated = list(calibrator.transform_many(raw))
    return TemporalCalibrationReport(
        calibration_size=split,
        evaluation_size=len(raw),
        raw_brier=brier_score(raw, target),
        calibrated_brier=brier_score(calibrated, target),
        raw_log_loss=log_loss(raw, target),
        calibrated_log_loss=log_loss(calibrated, target),
    )
