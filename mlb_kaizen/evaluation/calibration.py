"""Post-hoc probability calibration fitted only on earlier observations."""

from __future__ import annotations

from dataclasses import dataclass
from bisect import bisect_right
import math
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
class PlattCalibrator:
    """A smooth, serialisable probability correction fitted on prior outcomes.

    ``slope`` and ``intercept`` are the only learned values.  Keeping those
    values instead of a live sklearn object makes the calibrator auditable and
    safe to persist beside a trusted trained-model artifact.
    """

    slope: float
    intercept: float

    @classmethod
    def fit(cls, probabilities: Iterable[float], outcomes: Iterable[int]) -> "PlattCalibrator":
        probabilities, outcomes = list(probabilities), list(outcomes)
        if len(probabilities) != len(outcomes) or len(probabilities) < 2:
            raise ValueError("probabilities and outcomes need at least two equally sized values")
        if any(not 0 <= probability <= 1 for probability in probabilities):
            raise ValueError("probabilities must be in [0, 1]")
        if any(outcome not in (0, 1) for outcome in outcomes):
            raise ValueError("outcomes must be binary")
        if len(set(outcomes)) < 2:
            raise ValueError("calibration requires both outcome classes")
        try:
            from sklearn.linear_model import LogisticRegression
        except ImportError as exc:  # pragma: no cover - minimal installs
            raise RuntimeError("scikit-learn is required for Platt calibration") from exc
        fitted = LogisticRegression(C=1.0, solver="lbfgs").fit([[p] for p in probabilities], outcomes)
        return cls(float(fitted.coef_[0][0]), float(fitted.intercept_[0]))

    def transform(self, probability: float) -> float:
        if not 0 <= probability <= 1:
            raise ValueError("probability must be in [0, 1]")
        score = self.slope * probability + self.intercept
        if score >= 0:
            return 1 / (1 + math.exp(-score))
        exp_score = math.exp(score)
        return exp_score / (1 + exp_score)

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


def temporal_platt_calibration_report(
    probabilities: list[float], outcomes: list[int], calibration_fraction: float = 0.5
) -> TemporalCalibrationReport:
    """Fit Platt calibration on the earlier block and score only the later block."""
    if not 0 < calibration_fraction < 1:
        raise ValueError("calibration_fraction must be between zero and one")
    if len(probabilities) != len(outcomes) or len(probabilities) < 4:
        raise ValueError("at least four equally sized probability/outcome observations are required")
    split = max(2, min(len(probabilities) - 2, int(len(probabilities) * calibration_fraction)))
    calibrator = PlattCalibrator.fit(probabilities[:split], outcomes[:split])
    raw, target = probabilities[split:], outcomes[split:]
    calibrated = list(calibrator.transform_many(raw))
    return TemporalCalibrationReport(split, len(raw), brier_score(raw, target), brier_score(calibrated, target), log_loss(raw, target), log_loss(calibrated, target))
