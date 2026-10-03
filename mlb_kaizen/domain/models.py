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


class AnalysisMode(str, Enum):
    """How the analysis information set was assembled."""

    LIVE = "live"
    SNAPSHOT = "snapshot"
    MANUAL = "manual"
    HYBRID = "hybrid"


class CalculationStatus(str, Enum):
    """Whether the mathematical pipeline could execute."""

    READY = "ready"
    BLOCKED = "blocked"


class DataQualityStatus(str, Enum):
    """Describes provenance/completeness separately from calculation readiness."""

    VERIFIED = "verified"
    PARTIAL = "partial"
    MANUAL = "manual"
    HYBRID = "hybrid"
    STALE = "stale"
    NOT_VERIFIED = "not_verified"


class ModelValidationStatus(str, Enum):
    """Predictive-validation state, independent from calculation readiness."""

    EXPERIMENTAL = "experimental"
    VALIDATED = "validated"


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
class CompletedGameResult:
    """A finished game's identity, teams and final score.

    Distinct from Game (which is pregame identity, no score) because a
    result is only valid once the game is actually Final -- mixing the two
    concepts risks treating an in-progress score as a final one.
    """

    game_id: str
    official_date: date
    start_time: datetime
    home_team_id: str
    home_team_name: str
    away_team_id: str
    away_team_name: str
    home_runs: int
    away_runs: int
    provenance: DataProvenance

    def __post_init__(self) -> None:
        if not self.game_id or not self.home_team_id or not self.away_team_id:
            raise ValueError("game and team identifiers are required")
        if self.home_team_id == self.away_team_id:
            raise ValueError("home and away teams must differ")
        _require_aware(self.start_time, "start_time")
        if self.home_runs < 0 or self.away_runs < 0:
            raise ValueError("run totals cannot be negative")


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
class ProbablePitcher:
    """A probable starting pitcher for one team, or a recorded absence.

    Even when nothing has been posted yet, the provenance records that this
    was checked at a specific time. "Not yet published" is point-in-time
    information, not a missing observation.
    """

    game_id: str
    team_id: str
    status: AvailabilityStatus
    provenance: DataProvenance
    pitcher_id: str | None = None
    pitcher_name: str | None = None

    def __post_init__(self) -> None:
        if not self.game_id or not self.team_id:
            raise ValueError("game_id and team_id are required")
        reported = {AvailabilityStatus.CONFIRMED, AvailabilityStatus.PROJECTED}
        has_identity = bool(self.pitcher_id) and bool(self.pitcher_name)
        if self.status in reported and not has_identity:
            raise ValueError("pitcher_id and pitcher_name are required when status reports a pitcher")
        if self.status not in reported and (self.pitcher_id or self.pitcher_name):
            raise ValueError("pitcher identity must be empty unless status reports a pitcher")


@dataclass(frozen=True, slots=True)
class LineupSlot:
    """One confirmed batting-order entry for a team in a specific game."""

    game_id: str
    team_id: str
    batting_order: int
    player_id: str
    player_name: str
    position: str
    provenance: DataProvenance

    def __post_init__(self) -> None:
        if not self.game_id or not self.team_id:
            raise ValueError("game_id and team_id are required")
        if not 1 <= self.batting_order <= 9:
            raise ValueError("batting_order must be between 1 and 9")
        if not self.player_id or not self.player_name:
            raise ValueError("player identity is required")


@dataclass(frozen=True, slots=True)
class GameLineups:
    """Confirmed lineups for both teams, or a recorded not-yet-posted state.

    provenance is required even when nothing was posted yet: knowing *when*
    the lineup was checked is itself point-in-time information a feature
    pipeline needs, not something that can be reconstructed from empty slots.
    """

    game_id: str
    status: AvailabilityStatus
    provenance: DataProvenance
    home_slots: tuple[LineupSlot, ...] = ()
    away_slots: tuple[LineupSlot, ...] = ()

    def __post_init__(self) -> None:
        if not self.game_id:
            raise ValueError("game_id is required")
        posted = {AvailabilityStatus.CONFIRMED, AvailabilityStatus.AVAILABLE}
        if self.status in posted and not (self.home_slots and self.away_slots):
            raise ValueError("a posted status requires slots for both teams")
        if self.status not in posted and (self.home_slots or self.away_slots):
            raise ValueError("slots must be empty unless status reports a posted lineup")


@dataclass(frozen=True, slots=True)
class VenueLocation:
    """A venue's fixed geographic coordinates, used to look up its weather."""

    venue_id: str
    latitude: float
    longitude: float
    provenance: DataProvenance

    def __post_init__(self) -> None:
        if not self.venue_id:
            raise ValueError("venue_id is required")
        if not -90 <= self.latitude <= 90:
            raise ValueError("latitude must be between -90 and 90")
        if not -180 <= self.longitude <= 180:
            raise ValueError("longitude must be between -180 and 180")


@dataclass(frozen=True, slots=True)
class GameWeather:
    """A point-in-time forecast for a game's venue, or a recorded absence.

    NWS forecasts are not point-in-time-immutable the way a boxscore is: the
    forecast changes as game time approaches, so every fetch is its own
    snapshot with its own retrieved_at, never a value to overwrite in place.
    """

    game_id: str
    status: AvailabilityStatus
    provenance: DataProvenance
    temperature_fahrenheit: float | None = None
    wind_speed_text: str | None = None
    wind_direction: str | None = None
    short_forecast: str | None = None
    forecast_period_start: datetime | None = None

    def __post_init__(self) -> None:
        if not self.game_id:
            raise ValueError("game_id is required")
        reported = {AvailabilityStatus.AVAILABLE, AvailabilityStatus.CONFIRMED}
        has_forecast = self.temperature_fahrenheit is not None or self.short_forecast is not None
        if self.status in reported and not has_forecast:
            raise ValueError("an available weather record needs at least a forecast reading")
        if self.status not in reported and has_forecast:
            raise ValueError("forecast fields must be empty unless status reports a forecast")
        if self.forecast_period_start is not None:
            _require_aware(self.forecast_period_start, "forecast_period_start")


@dataclass(frozen=True, slots=True)
class TeamSeasonStats:
    """Raw season aggregates for one team, straight from the provider.

    earned_runs (pitching stat "earnedRuns") excludes runs that scored due to
    a fielding error; runs_allowed (pitching stat "runs") is the total, which
    is what a run-prevention feature needs — earned_runs alone would
    understate how many runs a team actually gives up.

    Deliberately NOT a normalised model feature: no league-average scaling,
    no offensive_index/run_prevention_index. Turning these into a model
    feature is Fase 4 (feature store) work, with its own documented formula,
    missing-value policy, and test — not something this record does for you.
    """

    team_id: str
    team_name: str
    season: str
    games_played: int
    batting_avg: float
    batting_obp: float
    batting_slg: float
    runs_scored: int
    plate_appearances: int
    pitching_era: float
    pitching_whip: float
    innings_pitched: str
    earned_runs: int
    runs_allowed: int
    provenance: DataProvenance

    def __post_init__(self) -> None:
        if not self.team_id or not self.team_name:
            raise ValueError("team_id and team_name are required")
        if not self.season:
            raise ValueError("season is required")
        if self.games_played < 0:
            raise ValueError("games_played cannot be negative")
        if self.runs_allowed < self.earned_runs:
            raise ValueError("runs_allowed cannot be less than earned_runs")


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
