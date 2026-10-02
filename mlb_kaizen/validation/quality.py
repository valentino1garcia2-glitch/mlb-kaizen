"""Validation that preserves uncertainty and blocks unjustified signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from mlb_kaizen.config.settings import Settings
from mlb_kaizen.domain.models import AnalysisContext, AvailabilityStatus, SignalStatus, TeamRunProfile


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    """Result of automatic data-quality checks before market recommendations."""

    data_quality: float
    status: SignalStatus
    warnings: tuple[str, ...]
    blocking_reasons: tuple[str, ...]


class QualityGate:
    """Apply configurable readiness checks without pretending missing data is neutral."""

    critical_fields = ("starting_pitchers", "lineups", "odds")

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def assess(
        self,
        context: AnalysisContext,
        profiles: Iterable[TeamRunProfile],
        calibrated: bool,
        probability_uncertainty: float,
    ) -> QualityAssessment:
        """Assess data completeness separately from model probability."""

        profiles = tuple(profiles)
        if not profiles:
            raise ValueError("at least one profile is required")
        if probability_uncertainty < 0:
            raise ValueError("probability uncertainty cannot be negative")

        warnings: list[str] = []
        blockers: list[str] = []
        quality = sum(profile.data_quality for profile in profiles) / len(profiles)

        for field in self.critical_fields:
            status = context.data_statuses.get(field, AvailabilityStatus.UNKNOWN)
            if status in {AvailabilityStatus.MISSING, AvailabilityStatus.NOT_AVAILABLE, AvailabilityStatus.UNKNOWN}:
                blockers.append(f"{field}: {status.value}")
            elif status in {AvailabilityStatus.PROJECTED, AvailabilityStatus.NOT_YET_PUBLISHED, AvailabilityStatus.STALE}:
                warnings.append(f"{field}: {status.value}")

        if quality < self.settings.minimum_data_quality:
            blockers.append("profile data quality below configured minimum")
        if probability_uncertainty > self.settings.maximum_probability_uncertainty:
            blockers.append("probability uncertainty exceeds configured maximum")
        if blockers:
            return QualityAssessment(quality, SignalStatus.DATA_INCOMPLETE, tuple(warnings), tuple(blockers))
        if not calibrated:
            return QualityAssessment(
                quality,
                SignalStatus.MODEL_UNCALIBRATED,
                tuple(warnings),
                ("no out-of-sample temporal calibration is registered",),
            )
        return QualityAssessment(quality, SignalStatus.NO_SIGNAL, tuple(warnings), tuple())
