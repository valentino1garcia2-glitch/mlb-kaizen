"""Descriptive data/model readiness without hiding usable calculations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from mlb_kaizen.config.settings import Settings
from mlb_kaizen.domain.models import (
    AnalysisContext,
    AnalysisMode,
    AvailabilityStatus,
    CalculationStatus,
    DataQualityStatus,
    ModelValidationStatus,
    SignalStatus,
    TeamRunProfile,
)


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    """Separate mathematical readiness, data quality and model validation."""

    data_quality: float
    status: SignalStatus
    calculation_status: CalculationStatus
    data_quality_status: DataQualityStatus
    model_validation_status: ModelValidationStatus
    warnings: tuple[str, ...]
    blocking_reasons: tuple[str, ...]


class QualityGate:
    """Classify readiness; do not turn ordinary missing context into a math lockout."""

    critical_fields = ("starting_pitchers", "lineups", "odds")

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def assess(
        self,
        context: AnalysisContext,
        profiles: Iterable[TeamRunProfile],
        calibrated: bool,
        probability_uncertainty: float,
        mode: AnalysisMode = AnalysisMode.SNAPSHOT,
    ) -> QualityAssessment:
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
                # Signal/decision blocker only; the mathematical calculation may still run.
                message = f"{field}: {status.value}"
                warnings.append(message)
                blockers.append(message)
            elif status in {AvailabilityStatus.PROJECTED, AvailabilityStatus.NOT_YET_PUBLISHED, AvailabilityStatus.STALE}:
                warnings.append(f"{field}: {status.value}")

        if quality < self.settings.minimum_data_quality:
            warnings.append("profile data quality below configured minimum")
        if probability_uncertainty > self.settings.maximum_probability_uncertainty:
            warnings.append("probability uncertainty exceeds configured maximum")

        if mode is AnalysisMode.MANUAL:
            quality_status = DataQualityStatus.MANUAL
        elif mode is AnalysisMode.HYBRID:
            quality_status = DataQualityStatus.HYBRID
        elif any("stale" in warning for warning in warnings):
            quality_status = DataQualityStatus.STALE
        elif warnings:
            quality_status = DataQualityStatus.PARTIAL
        else:
            quality_status = DataQualityStatus.VERIFIED

        validation_status = (
            ModelValidationStatus.VALIDATED if calibrated else ModelValidationStatus.EXPERIMENTAL
        )
        has_material_data_gap = any(
            field in warning
            and any(token in warning for token in ("missing", "not_available", "unknown"))
            for warning in warnings
            for field in self.critical_fields
        )
        if has_material_data_gap:
            status = SignalStatus.DATA_INCOMPLETE
        else:
            status = SignalStatus.NO_SIGNAL if calibrated else SignalStatus.MODEL_UNCALIBRATED
        if not calibrated:
            blockers.append("model output is experimental; market signal is preliminary")

        return QualityAssessment(
            data_quality=quality,
            status=status,
            calculation_status=CalculationStatus.READY,
            data_quality_status=quality_status,
            model_validation_status=validation_status,
            warnings=tuple(warnings),
            blocking_reasons=tuple(blockers),
        )
