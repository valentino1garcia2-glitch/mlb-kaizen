"""Composition layer for practical pre-game analysis and human-vs-machine tracking."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from mlb_kaizen.config.settings import Settings
from mlb_kaizen.domain.models import (
    AnalysisContext,
    AnalysisMode,
    CalculationStatus,
    DataQualityStatus,
    Game,
    ModelValidationStatus,
    TeamRunProfile,
)
from mlb_kaizen.market.odds import (
    decimal_to_implied_probability,
    edge,
    expected_value_per_unit,
    expected_value_per_unit_with_push,
    proportional_no_vig,
)
from mlb_kaizen.models.baseline import BaselineRunModel, RunProjection
from mlb_kaizen.simulation.monte_carlo import MonteCarloEngine, SimulationSummary
from mlb_kaizen.storage.database import KaizenDatabase
from mlb_kaizen.validation.quality import QualityAssessment, QualityGate


@dataclass(frozen=True, slots=True)
class MarketInput:
    """Market prices in decimal odds; missing markets remain explicitly absent."""

    home_decimal_odds: float | None = None
    away_decimal_odds: float | None = None
    total_line: float | None = None
    over_decimal_odds: float | None = None
    under_decimal_odds: float | None = None
    home_run_line: float | None = None
    home_run_line_decimal_odds: float | None = None
    away_run_line_decimal_odds: float | None = None
    sportsbook: str | None = None


@dataclass(frozen=True, slots=True)
class AnalysisRequest:
    """All inputs needed for one timestamped model execution."""

    game: Game
    home_profile: TeamRunProfile
    away_profile: TeamRunProfile
    context: AnalysisContext
    league_runs_per_team: float
    market: MarketInput = MarketInput()
    mode: AnalysisMode = AnalysisMode.SNAPSHOT


@dataclass(frozen=True, slots=True)
class MarketCandidate:
    """One market side evaluated by the model."""

    market: str
    selection: str
    line: float | None
    decimal_odds: float
    model_probability: float
    market_probability: float
    edge: float
    expected_value: float
    push_probability: float = 0.0


@dataclass(frozen=True, slots=True)
class MachinePick:
    """Transparent preliminary pick; absence means no priced opportunity is available."""

    market: str
    selection: str
    line: float | None
    model_probability: float
    market_probability: float
    edge: float
    expected_value: float
    decimal_odds: float
    status: str
    reason: str


@dataclass(frozen=True, slots=True)
class MarketComparison:
    """Market and model values kept distinct from the final machine output."""

    market_implied_home_probability: float | None
    no_vig_home_probability: float | None
    raw_model_edge: float | None
    preliminary_raw_ev: float | None
    candidates: tuple[MarketCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Baseline analysis output, usable before predictive validation is complete."""

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
    mode: AnalysisMode
    calculation_status: CalculationStatus
    data_quality_status: DataQualityStatus
    model_validation_status: ModelValidationStatus
    machine_pick: MachinePick | None
    prediction_id: str | None
    warnings: tuple[str, ...]


class AnalysisService:
    """Run usable analysis while clearly labelling experimental validation state."""

    def __init__(
        self,
        settings: Settings,
        run_model: BaselineRunModel | None = None,
        database: KaizenDatabase | None = None,
    ) -> None:
        self.settings = settings
        self.run_model = run_model
        self.database = database

    def analyse(self, request: AnalysisRequest, persist: bool = False) -> AnalysisResult:
        run_model = self.run_model or BaselineRunModel(request.league_runs_per_team)
        projection = run_model.project(request.game, request.home_profile, request.away_profile)
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
            mode=request.mode,
        )
        comparison = self._compare_market(raw_probability, simulation, request.market)
        machine_pick = self._select_machine_pick(comparison.candidates)
        data_timestamp = max(
            request.home_profile.provenance.retrieved_at,
            request.away_profile.provenance.retrieved_at,
        )
        warnings = (
            "La salida es experimental: no existe calibración temporal out-of-sample registrada.",
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
            mode=request.mode,
            calculation_status=quality.calculation_status,
            data_quality_status=quality.data_quality_status,
            model_validation_status=quality.model_validation_status,
            machine_pick=machine_pick,
            prediction_id=None,
            warnings=tuple(dict.fromkeys(warnings)),
        )
        if persist:
            if self.database is None:
                raise ValueError("database is required when persist=True")
            self.database.initialise()
            prediction_id = self.database.store_prediction(
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
            result = replace(result, prediction_id=prediction_id)
        return result

    def _select_machine_pick(self, candidates: tuple[MarketCandidate, ...]) -> MachinePick | None:
        viable = [
            candidate
            for candidate in candidates
            if candidate.edge >= self.settings.minimum_edge
            and candidate.expected_value >= self.settings.minimum_ev
        ]
        if not viable:
            return None
        selected = max(viable, key=lambda candidate: (candidate.expected_value, candidate.edge))
        return MachinePick(
            market=selected.market,
            selection=selected.selection,
            line=selected.line,
            model_probability=selected.model_probability,
            market_probability=selected.market_probability,
            edge=selected.edge,
            expected_value=selected.expected_value,
            decimal_odds=selected.decimal_odds,
            status="preliminary",
            reason="Mejor EV preliminar entre mercados que superan los umbrales configurados.",
        )

    @staticmethod
    def _compare_market(
        raw_probability: float, simulation: SimulationSummary, market: MarketInput
    ) -> MarketComparison:
        candidates: list[MarketCandidate] = []
        home_implied = None
        home_no_vig = None
        if market.home_decimal_odds is not None:
            home_implied = decimal_to_implied_probability(market.home_decimal_odds)
            away_for_no_vig = market.away_decimal_odds
            if away_for_no_vig is not None:
                home_no_vig = proportional_no_vig(
                    {"home": market.home_decimal_odds, "away": away_for_no_vig}
                )["home"]
            market_prob = home_no_vig if home_no_vig is not None else home_implied
            candidates.append(
                MarketCandidate(
                    market="moneyline",
                    selection="home",
                    line=None,
                    decimal_odds=market.home_decimal_odds,
                    model_probability=raw_probability,
                    market_probability=market_prob,
                    edge=edge(raw_probability, market_prob),
                    expected_value=expected_value_per_unit(raw_probability, market.home_decimal_odds),
                )
            )
        if market.away_decimal_odds is not None:
            away_implied = decimal_to_implied_probability(market.away_decimal_odds)
            away_no_vig = None
            if market.home_decimal_odds is not None:
                away_no_vig = proportional_no_vig(
                    {"home": market.home_decimal_odds, "away": market.away_decimal_odds}
                )["away"]
            away_market_prob = away_no_vig if away_no_vig is not None else away_implied
            candidates.append(
                MarketCandidate(
                    market="moneyline",
                    selection="away",
                    line=None,
                    decimal_odds=market.away_decimal_odds,
                    model_probability=simulation.away_win_probability,
                    market_probability=away_market_prob,
                    edge=edge(simulation.away_win_probability, away_market_prob),
                    expected_value=expected_value_per_unit(
                        simulation.away_win_probability, market.away_decimal_odds
                    ),
                )
            )
        if market.total_line is not None and market.over_decimal_odds is not None:
            over_prob = simulation.over_probability
            if over_prob is not None:
                market_prob = decimal_to_implied_probability(market.over_decimal_odds)
                push_prob = simulation.total_push_probability or 0.0
                if market.under_decimal_odds is not None:
                    market_prob = proportional_no_vig(
                        {"over": market.over_decimal_odds, "under": market.under_decimal_odds}
                    )["over"]
                candidates.append(
                    MarketCandidate(
                        market="total",
                        selection="over",
                        line=market.total_line,
                        decimal_odds=market.over_decimal_odds,
                        model_probability=over_prob,
                        market_probability=market_prob,
                        edge=edge(over_prob, market_prob),
                        expected_value=expected_value_per_unit_with_push(
                            over_prob, push_prob, market.over_decimal_odds
                        ),
                        push_probability=push_prob,
                    )
                )
        if market.total_line is not None and market.under_decimal_odds is not None:
            under_prob = simulation.under_probability
            if under_prob is not None:
                market_prob = decimal_to_implied_probability(market.under_decimal_odds)
                push_prob = simulation.total_push_probability or 0.0
                if market.over_decimal_odds is not None:
                    market_prob = proportional_no_vig(
                        {"over": market.over_decimal_odds, "under": market.under_decimal_odds}
                    )["under"]
                candidates.append(
                    MarketCandidate(
                        market="total",
                        selection="under",
                        line=market.total_line,
                        decimal_odds=market.under_decimal_odds,
                        model_probability=under_prob,
                        market_probability=market_prob,
                        edge=edge(under_prob, market_prob),
                        expected_value=expected_value_per_unit_with_push(
                            under_prob, push_prob, market.under_decimal_odds
                        ),
                        push_probability=push_prob,
                    )
                )
        if market.home_run_line is not None and market.home_run_line_decimal_odds is not None:
            home_cover = simulation.home_run_line_cover_probability
            if home_cover is not None:
                push_prob = simulation.home_run_line_push_probability or 0.0
                market_prob = decimal_to_implied_probability(market.home_run_line_decimal_odds)
                if market.away_run_line_decimal_odds is not None:
                    market_prob = proportional_no_vig(
                        {
                            "home": market.home_run_line_decimal_odds,
                            "away": market.away_run_line_decimal_odds,
                        }
                    )["home"]
                candidates.append(
                    MarketCandidate(
                        market="run_line",
                        selection="home",
                        line=market.home_run_line,
                        decimal_odds=market.home_run_line_decimal_odds,
                        model_probability=home_cover,
                        market_probability=market_prob,
                        edge=edge(home_cover, market_prob),
                        expected_value=expected_value_per_unit_with_push(
                            home_cover, push_prob, market.home_run_line_decimal_odds
                        ),
                        push_probability=push_prob,
                    )
                )
                if market.away_run_line_decimal_odds is not None:
                    away_cover = max(0.0, 1.0 - home_cover - push_prob)
                    away_market_prob = proportional_no_vig(
                        {
                            "home": market.home_run_line_decimal_odds,
                            "away": market.away_run_line_decimal_odds,
                        }
                    )["away"]
                    candidates.append(
                        MarketCandidate(
                            market="run_line",
                            selection="away",
                            line=-market.home_run_line,
                            decimal_odds=market.away_run_line_decimal_odds,
                            model_probability=away_cover,
                            market_probability=away_market_prob,
                            edge=edge(away_cover, away_market_prob),
                            expected_value=expected_value_per_unit_with_push(
                                away_cover, push_prob, market.away_run_line_decimal_odds
                            ),
                            push_probability=push_prob,
                        )
                    )
        raw_edge = None
        raw_ev = None
        if market.home_decimal_odds is not None:
            reference = home_no_vig if home_no_vig is not None else home_implied
            raw_edge = edge(raw_probability, reference)
            raw_ev = expected_value_per_unit(raw_probability, market.home_decimal_odds)
        return MarketComparison(home_implied, home_no_vig, raw_edge, raw_ev, tuple(candidates))
