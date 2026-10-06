"""Pregame, append-only E3+E7+E8 vectors from verified completed games."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from mlb_kaizen.domain.models import CompletedGameResult, Game, InferenceFeatureSnapshot
from mlb_kaizen.features.run_profile import run_rate_index
from mlb_kaizen.training.build_dataset import (
    DEFAULT_HOME_ADVANTAGE,
    MINIMUM_LEAGUE_GAMES_FOR_AVERAGE,
    MINIMUM_PRIOR_GAMES,
    OPPONENT_STRENGTH_FORMULA_VERSION,
    RECENT_FORM_FORMULA_VERSION,
    RECENT_FORM_WINDOW,
)
from mlb_kaizen.training.inference_artifact import E8_FEATURE_NAMES

E8_DAILY_SNAPSHOT_SCHEMA_VERSION = "e3_e7_e8_daily_features_v1"
E8_DAILY_SNAPSHOT_FORMULA_VERSION = (
    f"run_profile_formula_v1+{OPPONENT_STRENGTH_FORMULA_VERSION}+{RECENT_FORM_FORMULA_VERSION}"
)


@dataclass
class _TeamTotals:
    runs_scored: int = 0
    runs_allowed: int = 0
    games_played: int = 0


def build_e8_daily_feature_snapshot(
    game: Game,
    completed_games: Sequence[CompletedGameResult],
    *,
    prediction_timestamp: datetime,
    minimum_prior_games: int = MINIMUM_PRIOR_GAMES,
    minimum_league_games_for_average: int = MINIMUM_LEAGUE_GAMES_FOR_AVERAGE,
    minimum_prior_matchups: int = 1,
    recent_form_window: int = RECENT_FORM_WINDOW,
    home_advantage: float = DEFAULT_HOME_ADVANTAGE,
) -> InferenceFeatureSnapshot:
    """Build the exact E3+E7+E8 input vector known before ``game`` starts.

    Completed results are acceptable only when they were retrieved no later
    than the prediction instant. Future and simultaneous games are ignored;
    a result for the target game is never accepted as an input.
    """

    if game.start_time is None:
        raise ValueError("scheduled game requires a start_time")
    if prediction_timestamp.tzinfo is None or prediction_timestamp.utcoffset() is None:
        raise ValueError("prediction_timestamp must be timezone-aware")
    if prediction_timestamp >= game.start_time:
        raise ValueError("prediction_timestamp must be before game start_time")
    if game.provenance.retrieved_at > prediction_timestamp:
        raise ValueError("game schedule was retrieved after prediction_timestamp")
    if min(minimum_prior_games, minimum_league_games_for_average, minimum_prior_matchups, recent_form_window) < 1:
        raise ValueError("minimum history requirements must be positive")

    eligible_history: list[CompletedGameResult] = []
    for result in completed_games:
        if result.game_id == game.game_id:
            raise ValueError("target game result cannot be used for pregame features")
        if result.start_time >= prediction_timestamp:
            continue
        if result.provenance.retrieved_at > prediction_timestamp:
            raise ValueError("completed-game result was retrieved after prediction_timestamp")
        eligible_history.append(result)

    totals: dict[str, _TeamTotals] = {}
    opponents: dict[str, dict[str, int]] = {}
    recent: dict[str, list[tuple[int, int]]] = {}
    recent_season: dict[str, int] = {}
    league_runs = league_games = 0

    def record(team_id: str, season: int, scored: int, allowed: int) -> None:
        if recent_season.get(team_id) != season:
            recent_season[team_id] = season
            recent[team_id] = []
        history = recent[team_id]
        history.append((scored, allowed))
        if len(history) > recent_form_window:
            history.pop(0)

    for result in sorted(eligible_history, key=lambda item: (item.start_time, item.game_id)):
        home = totals.setdefault(result.home_team_id, _TeamTotals())
        away = totals.setdefault(result.away_team_id, _TeamTotals())
        home.runs_scored += result.home_runs
        home.runs_allowed += result.away_runs
        home.games_played += 1
        away.runs_scored += result.away_runs
        away.runs_allowed += result.home_runs
        away.games_played += 1
        opponents.setdefault(result.home_team_id, {})[result.away_team_id] = (
            opponents.setdefault(result.home_team_id, {}).get(result.away_team_id, 0) + 1
        )
        opponents.setdefault(result.away_team_id, {})[result.home_team_id] = (
            opponents.setdefault(result.away_team_id, {}).get(result.home_team_id, 0) + 1
        )
        record(result.home_team_id, result.official_date.year, result.home_runs, result.away_runs)
        record(result.away_team_id, result.official_date.year, result.away_runs, result.home_runs)
        league_runs += result.home_runs + result.away_runs
        league_games += 2

    home = totals.get(game.home_team_id, _TeamTotals())
    away = totals.get(game.away_team_id, _TeamTotals())
    home_opponents = opponents.get(game.home_team_id, {})
    away_opponents = opponents.get(game.away_team_id, {})
    home_recent = recent.get(game.home_team_id, []) if recent_season.get(game.home_team_id) == game.official_date.year else []
    away_recent = recent.get(game.away_team_id, []) if recent_season.get(game.away_team_id) == game.official_date.year else []
    if (
        home.games_played < minimum_prior_games
        or away.games_played < minimum_prior_games
        or league_games < minimum_league_games_for_average
        or sum(home_opponents.values()) < minimum_prior_matchups
        or sum(away_opponents.values()) < minimum_prior_matchups
        or len(home_recent) < recent_form_window
        or len(away_recent) < recent_form_window
    ):
        raise ValueError("insufficient strictly-prior completed-game history for E3+E7+E8")

    league_average = league_runs / league_games

    def opponent_indices(team_opponents: dict[str, int]) -> tuple[float, float]:
        count = sum(team_opponents.values())
        offensive = prevention = 0.0
        for team_id, times in team_opponents.items():
            opponent = totals[team_id]
            offensive += times * run_rate_index(opponent.runs_scored / opponent.games_played, league_average)
            prevention += times * run_rate_index(opponent.runs_allowed / opponent.games_played, league_average)
        return offensive / count, prevention / count

    home_opp_offence, home_opp_prevention = opponent_indices(home_opponents)
    away_opp_offence, away_opp_prevention = opponent_indices(away_opponents)
    features = {
        "home_offensive_index": run_rate_index(home.runs_scored / home.games_played, league_average),
        "away_offensive_index": run_rate_index(away.runs_scored / away.games_played, league_average),
        "home_run_prevention_index": run_rate_index(home.runs_allowed / home.games_played, league_average),
        "away_run_prevention_index": run_rate_index(away.runs_allowed / away.games_played, league_average),
        "home_advantage": home_advantage,
        "home_opponent_offensive_index": home_opp_offence,
        "home_opponent_run_prevention_index": home_opp_prevention,
        "away_opponent_offensive_index": away_opp_offence,
        "away_opponent_run_prevention_index": away_opp_prevention,
        "home_recent_offensive_index": run_rate_index(sum(value for value, _ in home_recent) / recent_form_window, league_average),
        "home_recent_run_prevention_index": run_rate_index(sum(value for _, value in home_recent) / recent_form_window, league_average),
        "away_recent_offensive_index": run_rate_index(sum(value for value, _ in away_recent) / recent_form_window, league_average),
        "away_recent_run_prevention_index": run_rate_index(sum(value for _, value in away_recent) / recent_form_window, league_average),
    }
    if tuple(features) != E8_FEATURE_NAMES:
        raise AssertionError("daily E8 feature order drifted from inference artifact")
    source_timestamp = max(
        [game.provenance.retrieved_at] + [item.provenance.retrieved_at for item in eligible_history]
    )
    return InferenceFeatureSnapshot(
        game_id=game.game_id,
        prediction_timestamp=prediction_timestamp,
        source_timestamp=source_timestamp,
        feature_schema_version=E8_DAILY_SNAPSHOT_SCHEMA_VERSION,
        formula_version=E8_DAILY_SNAPSHOT_FORMULA_VERSION,
        features=features,
    )
