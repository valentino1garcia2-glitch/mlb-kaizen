"""Composition layer for an analysis that remains explicit about limitations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from mlb_kaizen.config.settings import Settings
from mlb_kaizen.domain.models import AnalysisContext, Game, SignalStatus, TeamRunProfile
from mlb_kaizen.market.odds import (
    decimal_to_implied_probability,
    edge,
    expected_value_per_unit,
    proportional_no_vig,
)
from mlb_kaizen.models.baseline import BaselineRunModel, RunProjection
from mlb_kaizen.simulation.monte_carlo import MonteCarloEngine, SimulationSummary
from mlb_kaizen.storage.database import KaizenDatabase
from mlb_kaizen.validation.quality import QualityAssessment, QualityGate


@dataclass(frozen=True, slots=True)
class MarketInput:
    """A paired moneyline plus optional totals/run-line, expressed in decimal odds."""

    home_decimal_odds: float | None = None
    away_decimal_odds: float | None = None
    total_line: float | None = None
    home_run_line: float | None = None


@dataclass(frozen=True, slots=True)
class AnalysisRequest:
    """All inputs needed for one timestamped model execution."""

    game: Game
    home_profile: TeamRunProfile
    away_profile: TeamRunProfile
    context: AnalysisContext
    market: MarketInput = MarketInput()


@dataclass(frozen=True, slots=True)
class MarketComparison:
    """Market and model values kept distinct from a final betting signal."""

    market_implied_home_probability: float | None
    no_vig_home_probability: float | None
    raw_model_edge: float | None
    preliminary_raw_ev: float | None


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Standard model-output contract for the initial baseline workflow."""

    projection: RunProjection
    simulation: SimulationSummary
    market: MarketComparison
    quality: QualityAssessment
    raw_probability: float
    calibrated_probability: float | None
    uncertainty: float
    model_version: str
    feature_version: str
    data_timestamp: datetime
    sample_size: int
    warnings: tuple[str, ...]


class AnalysisService:
    """Run analysis while preventing an uncalibrated simulation from becoming a bet."""

    def __init__(
        self,
        settings: Settings,
        run_model: BaselineRunModel | None = None,
        database: KaizenDatabase | None = None,
    ) -> None:
        self.settings = settings
        self.run_model = run_model or BaselineRunModel()
        self.database = database

    def analyse(self, request: AnalysisRequest, persist: bool = False) -> AnalysisResult:
        """Execute deterministic components; calibration is intentionally unavailable in v0.1."""

        projection = self.run_model.project(request.game, request.home_profile, request.away_profile)
        simulation = MonteCarloEngine(
            simulation_count=self.settings.simulation_count,
            random_seed=self.settings.random_seed,
        ).run(
            projection,
            total_line=request.market.total_line,
            home_run_line=request.market.home_run_line,
        )
        raw_probability = simulation.home_win_probability
        quality = QualityGate(self.settings).assess(
            request.context,
            (request.home_profile, request.away_profile),
            calibrated=False,
            probability_uncertainty=simulation.home_win_standard_error,
        )
        comparison = self._compare_market(raw_probability, request.market)
        data_timestamp = max(
            request.home_profile.provenance.retrieved_at,
            request.away_profile.provenance.retrieved_at,
        )
        warnings = (
            "Probabilidad no calibrada: no usar EV preliminar como señal de apuesta.",
            "La resolución de empates en extra innings es un proxy simétrico y se reporta aparte.",
            *quality.warnings,
            *quality.blocking_reasons,
        )
        result = AnalysisResult(
            projection=projection,
            simulation=simulation,
            market=comparison,
            quality=quality,
            raw_probability=raw_probability,
            calibrated_probability=None,
            uncertainty=simulation.home_win_standard_error,
            model_version=projection.model_version,
            feature_version=projection.feature_version,
            data_timestamp=data_timestamp,
            sample_size=min(request.home_profile.sample_size, request.away_profile.sample_size),
            warnings=tuple(warnings),
        )
        if persist:
            if self.database is None:
                raise ValueError("database is required when persist=True")
            self.database.initialise()
            self.database.store_prediction(
                game_id=request.game.game_id,
                prediction_timestamp=request.context.prediction_timestamp,
                data_timestamp=data_timestamp,
                model_version=result.model_version,
                feature_version=result.feature_version,
                raw_probability=result.raw_probability,
                calibrated_probability=result.calibrated_probability,
                uncertainty=result.uncertainty,
                data_quality=result.quality.data_quality,
                model_input=request,
                model_output=result,
            )
        return result

    @staticmethod
    def _compare_market(raw_probability: float, market: MarketInput) -> MarketComparison:
        if market.home_decimal_odds is None:
            return MarketComparison(None, None, None, None)
        implied = decimal_to_implied_probability(market.home_decimal_odds)
        no_vig = None
        if market.away_decimal_odds is not None:
            no_vig = proportional_no_vig(
                {"home": market.home_decimal_odds, "away": market.away_decimal_odds}
            )["home"]
        return MarketComparison(
            market_implied_home_probability=implied,
            no_vig_home_probability=no_vig,
            raw_model_edge=edge(raw_probability, no_vig if no_vig is not None else implied),
            preliminary_raw_ev=expected_value_per_unit(raw_probability, market.home_decimal_odds),
        )
