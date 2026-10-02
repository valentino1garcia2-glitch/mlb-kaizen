"""Typed, provider-independent records used by every system layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Mapping


class AvailabilityStatus(str, Enum):
    """A missing value must retain its meaning rather than becoming zero."""

    CONFIRMED = "confirmed"
    PROJECTED = "projected"
    AVAILABLE = "available"
    MISSING = "missing"
    NOT_AVAILABLE = "not_available"
    NOT_YET_PUBLISHED = "not_yet_published"
    NOT_APPLICABLE = "not_applicable"
    STALE = "stale"
    UNKNOWN = "unknown"


class SignalStatus(str, Enum):
    """Descriptive statuses; none implies a guaranteed outcome."""

    NO_SIGNAL = "no_signal"
    DATA_INCOMPLETE = "data_incomplete"
    INSUFFICIENT_EDGE = "insufficient_edge"
    MODEL_UNCALIBRATED = "model_uncalibrated"
    MODEL_DISAGREEMENT = "model_disagreement"
    POSITIVE_EXPECTED_VALUE = "positive_expected_value"


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class DataProvenance:
    """Where a datum came from and when it was known."""

    source: str
    retrieved_at: datetime
    status: AvailabilityStatus
    effective_at: datetime | None = None
    source_url: str | None = None
    source_version: str | None = None

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("source is required")
        _require_aware(self.retrieved_at, "retrieved_at")
        if self.effective_at is not None:
            _require_aware(self.effective_at, "effective_at")


@dataclass(frozen=True, slots=True)
class Game:
    """A game identity from a provider, never inferred from display names."""

    game_id: str
    official_date: date
    home_team_id: str
    home_team_name: str
    away_team_id: str
    away_team_name: str
    provenance: DataProvenance
    start_time: datetime | None = None
    venue_name: str | None = None

    def __post_init__(self) -> None:
        if not self.game_id or not self.home_team_id or not self.away_team_id:
            raise ValueError("game and team identifiers are required")
        if self.home_team_id == self.away_team_id:
            raise ValueError("home and away teams must differ")
        if self.start_time is not None:
            _require_aware(self.start_time, "start_time")


@dataclass(frozen=True, slots=True)
class TeamRunProfile:
    """Normalised, timestamped team inputs for the transparent run model.

    Values are multiplicative indices relative to the league average. An offensive
    index above 1.0 scores more runs than league average; a run-prevention index
    above 1.0 allows more runs than league average. These are model inputs, not
    raw baseball statistics.
    """

    team_id: str
    team_name: str
    offensive_index: float
    run_prevention_index: float
    sample_size: int
    data_quality: float
    provenance: DataProvenance

    def __post_init__(self) -> None:
        if not self.team_id or not self.team_name:
            raise ValueError("team identity is required")
        if self.offensive_index <= 0 or self.run_prevention_index <= 0:
            raise ValueError("run indices must be positive")
        if self.sample_size < 0:
            raise ValueError("sample_size cannot be negative")
        if not 0 <= self.data_quality <= 1:
            raise ValueError("data_quality must be between zero and one")


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    """The information set available at a specific prediction timestamp."""

    prediction_timestamp: datetime
    information_state: str
    data_statuses: Mapping[str, AvailabilityStatus] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_aware(self.prediction_timestamp, "prediction_timestamp")
        if not self.information_state.strip():
            raise ValueError("information_state is required")
