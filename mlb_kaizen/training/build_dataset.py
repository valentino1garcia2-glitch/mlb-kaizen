"""Turns a chronological list of real completed games into a point-in-time
HistoricalGameRow dataset, without any network access.

The core discipline: a team's offensive_index/run_prevention_index for game
N is computed ONLY from games 1..N-1 in the supplied list (strictly earlier
by start_time), never from game N itself or anything later. The league
average used for the same row is likewise the running average of every
team-game observed strictly before game N, not a constant computed from the
whole dataset -- using a whole-dataset average would leak future information
into early rows.

This mirrors mlb_kaizen.features.run_profile's formula exactly (same
run_rate_index helper), but is fed by running per-game accumulation instead
of a TeamSeasonStats season snapshot, because a season-aggregate endpoint
cannot give a point-in-time cut at an arbitrary date.
"""

from __future__ import annotations

from dataclasses import dataclass

from mlb_kaizen.domain.models import CompletedGameResult
from mlb_kaizen.features.run_profile import run_rate_index
from mlb_kaizen.training.dataset import HistoricalGameRow

#: Matches models.baseline.BaselineRunModel's own default -- this is a
#: documented model assumption, not a fitted value; see docs/features and
#: HANDOFF.md for why it isn't estimated from data yet.
DEFAULT_HOME_ADVANTAGE = 1.035

#: A team needs at least this many strictly-prior games in the window before
#: a row is emitted for it. 1 is the mathematical minimum (run_rate_index
#: needs games_played > 0); callers doing real analysis should pass a higher
#: value for less noisy features -- this module does not pick that for you.
MINIMUM_PRIOR_GAMES = 1

#: A row is only emitted once at least this many team-games have been
#: observed league-wide (both teams combined, across all teams), so the
#: point-in-time league average isn't a wildly noisy 1-2 game figure. This is
#: a documented default, not a fitted threshold.
MINIMUM_LEAGUE_GAMES_FOR_AVERAGE = 10


@dataclass
class _TeamAccumulator:
    runs_scored: int = 0
    runs_allowed: int = 0
    games_played: int = 0


def build_point_in_time_rows(
    games: list[CompletedGameResult],
    *,
    minimum_prior_games: int = MINIMUM_PRIOR_GAMES,
    minimum_league_games_for_average: int = MINIMUM_LEAGUE_GAMES_FOR_AVERAGE,
    home_advantage: float = DEFAULT_HOME_ADVANTAGE,
) -> list[HistoricalGameRow]:
    """Build rows in chronological order, skipping games without enough prior history.

    A skipped game still counts toward every team's running totals and the
    league total once processed -- it simply does not become a training row
    itself. This means later games in the same window benefit from earlier
    games even when those earlier games were too early to be rows themselves.
    """

    if minimum_prior_games < 1:
        raise ValueError("minimum_prior_games must be at least 1")
    if minimum_league_games_for_average < 1:
        raise ValueError("minimum_league_games_for_average must be at least 1")

    ordered = sorted(games, key=lambda game: (game.start_time, game.game_id))

    team_totals: dict[str, _TeamAccumulator] = {}
    league_runs = 0
    league_games = 0
    rows: list[HistoricalGameRow] = []

    for game in ordered:
        home = team_totals.get(game.home_team_id, _TeamAccumulator())
        away = team_totals.get(game.away_team_id, _TeamAccumulator())

        eligible = (
            home.games_played >= minimum_prior_games
            and away.games_played >= minimum_prior_games
            and league_games >= minimum_league_games_for_average
        )
        if eligible:
            league_average = league_runs / league_games
            home_offensive = run_rate_index(home.runs_scored / home.games_played, league_average)
            home_prevention = run_rate_index(home.runs_allowed / home.games_played, league_average)
            away_offensive = run_rate_index(away.runs_scored / away.games_played, league_average)
            away_prevention = run_rate_index(away.runs_allowed / away.games_played, league_average)

            feature_timestamp = game.start_time
            # feature_timestamp equals prediction_timestamp here: the
            # accumulation loop already guarantees every input to these
            # indices comes from strictly earlier games, so "known by game
            # time" is the correct and honest upper bound -- there is no
            # separate real-world timestamp for a computed point-in-time
            # aggregate the way there is for a single fetched record.
            rows.append(
                HistoricalGameRow(
                    game_id=game.game_id,
                    official_date=game.official_date,
                    prediction_timestamp=game.start_time,
                    feature_timestamp=feature_timestamp,
                    features={
                        "home_offensive_index": home_offensive,
                        "away_offensive_index": away_offensive,
                        "home_run_prevention_index": home_prevention,
                        "away_run_prevention_index": away_prevention,
                        "home_advantage": home_advantage,
                    },
                    home_runs=game.home_runs,
                    away_runs=game.away_runs,
                )
            )

        # Update accumulators AFTER using them, so this game's own result
        # never leaks into its own row -- only into rows for later games.
        home.runs_scored += game.home_runs
        home.runs_allowed += game.away_runs
        home.games_played += 1
        away.runs_scored += game.away_runs
        away.runs_allowed += game.home_runs
        away.games_played += 1
        team_totals[game.home_team_id] = home
        team_totals[game.away_team_id] = away
        league_runs += game.home_runs + game.away_runs
        league_games += 2

    return rows
