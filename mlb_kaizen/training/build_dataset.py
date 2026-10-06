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

from mlb_kaizen.domain.models import CompletedGameResult, PitcherGameLine
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
MINIMUM_GAMES_AT_VENUE = 20

#: Feature-contract identifier for the prior-only opponent-strength inputs.
#: Formula changes require a new version rather than silently rewriting a
#: historical experiment's meaning.
OPPONENT_STRENGTH_FORMULA_VERSION = "opponent_strength_formula_v1"

#: The pre-registered number of completed games used by the E8 recent-form
#: experiment.  It is a feature-contract choice, not a value tuned on 2026.
RECENT_FORM_WINDOW = 15
RECENT_FORM_FORMULA_VERSION = "recent_form_formula_v1"

CANONICAL_VENUE_NAMES = {
    "UNIQLO Field at Dodger Stadium": "Dodger Stadium",
    "Rate Field": "Guaranteed Rate Field",
    "Daikin Park": "Minute Maid Park",
}


@dataclass
class _TeamAccumulator:
    runs_scored: int = 0
    runs_allowed: int = 0
    games_played: int = 0


@dataclass
class _PitcherAccumulator:
    earned_runs: int = 0
    outs: int = 0
    starts: int = 0


@dataclass
class _VenueAccumulator:
    runs: int = 0
    games: int = 0


@dataclass
class _BullpenAccumulator:
    earned_runs: int = 0
    outs: int = 0


def canonical_venue_name(name: str) -> str:
    """Merge documented sponsorship renames, never genuine relocations."""
    return CANONICAL_VENUE_NAMES.get(name, name)


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


def build_point_in_time_rows_with_opponent_strength(
    games: list[CompletedGameResult],
    *,
    minimum_prior_games: int = MINIMUM_PRIOR_GAMES,
    minimum_league_games_for_average: int = MINIMUM_LEAGUE_GAMES_FOR_AVERAGE,
    minimum_prior_matchups: int = 1,
    home_advantage: float = DEFAULT_HOME_ADVANTAGE,
) -> list[HistoricalGameRow]:
    """Build team rows plus strictly-prior strength-of-schedule inputs.

    For each club, the two extra inputs are the match-count-weighted current
    offensive and run-prevention indices of opponents that club has already
    faced.  Every opponent profile is read before the current game is added to
    any accumulator, so neither this game's score nor future games can affect
    its own row.
    """

    if minimum_prior_games < 1:
        raise ValueError("minimum_prior_games must be at least 1")
    if minimum_league_games_for_average < 1:
        raise ValueError("minimum_league_games_for_average must be at least 1")
    if minimum_prior_matchups < 1:
        raise ValueError("minimum_prior_matchups must be at least 1")

    team_totals: dict[str, _TeamAccumulator] = {}
    opponent_counts: dict[str, dict[str, int]] = {}
    league_runs = league_games = 0
    rows: list[HistoricalGameRow] = []

    def schedule_profile(team_id: str, league_average: float) -> tuple[float, float]:
        opponents = opponent_counts.get(team_id, {})
        matchup_count = sum(opponents.values())
        if matchup_count < minimum_prior_matchups:
            raise ValueError("insufficient prior opponents for schedule profile")
        weighted_offence = weighted_prevention = 0.0
        for opponent_id, times_faced in opponents.items():
            opponent = team_totals[opponent_id]
            # An opponent can only enter this mapping after a completed prior
            # matchup, therefore it necessarily has a non-zero prior sample.
            weighted_offence += times_faced * run_rate_index(
                opponent.runs_scored / opponent.games_played, league_average
            )
            weighted_prevention += times_faced * run_rate_index(
                opponent.runs_allowed / opponent.games_played, league_average
            )
        return weighted_offence / matchup_count, weighted_prevention / matchup_count

    for game in sorted(games, key=lambda item: (item.start_time, item.game_id)):
        home = team_totals.get(game.home_team_id, _TeamAccumulator())
        away = team_totals.get(game.away_team_id, _TeamAccumulator())
        home_matchups = sum(opponent_counts.get(game.home_team_id, {}).values())
        away_matchups = sum(opponent_counts.get(game.away_team_id, {}).values())

        eligible = (
            home.games_played >= minimum_prior_games
            and away.games_played >= minimum_prior_games
            and league_games >= minimum_league_games_for_average
            and home_matchups >= minimum_prior_matchups
            and away_matchups >= minimum_prior_matchups
        )
        if eligible:
            league_average = league_runs / league_games
            home_opponent_offence, home_opponent_prevention = schedule_profile(
                game.home_team_id, league_average
            )
            away_opponent_offence, away_opponent_prevention = schedule_profile(
                game.away_team_id, league_average
            )
            rows.append(
                HistoricalGameRow(
                    game_id=game.game_id,
                    official_date=game.official_date,
                    prediction_timestamp=game.start_time,
                    feature_timestamp=game.start_time,
                    features={
                        "home_offensive_index": run_rate_index(
                            home.runs_scored / home.games_played, league_average
                        ),
                        "away_offensive_index": run_rate_index(
                            away.runs_scored / away.games_played, league_average
                        ),
                        "home_run_prevention_index": run_rate_index(
                            home.runs_allowed / home.games_played, league_average
                        ),
                        "away_run_prevention_index": run_rate_index(
                            away.runs_allowed / away.games_played, league_average
                        ),
                        "home_advantage": home_advantage,
                        "home_opponent_offensive_index": home_opponent_offence,
                        "home_opponent_run_prevention_index": home_opponent_prevention,
                        "away_opponent_offensive_index": away_opponent_offence,
                        "away_opponent_run_prevention_index": away_opponent_prevention,
                    },
                    home_runs=game.home_runs,
                    away_runs=game.away_runs,
                )
            )

        # Mutate only after every feature for this game was constructed.
        home.runs_scored += game.home_runs
        home.runs_allowed += game.away_runs
        home.games_played += 1
        away.runs_scored += game.away_runs
        away.runs_allowed += game.home_runs
        away.games_played += 1
        team_totals[game.home_team_id], team_totals[game.away_team_id] = home, away
        home_opponents = opponent_counts.setdefault(game.home_team_id, {})
        home_opponents[game.away_team_id] = home_opponents.get(game.away_team_id, 0) + 1
        away_opponents = opponent_counts.setdefault(game.away_team_id, {})
        away_opponents[game.home_team_id] = away_opponents.get(game.home_team_id, 0) + 1
        league_runs += game.home_runs + game.away_runs
        league_games += 2

    return rows


def build_point_in_time_rows_with_opponent_strength_and_recent_form(
    games: list[CompletedGameResult],
    *,
    minimum_prior_games: int = MINIMUM_PRIOR_GAMES,
    minimum_league_games_for_average: int = MINIMUM_LEAGUE_GAMES_FOR_AVERAGE,
    minimum_prior_matchups: int = 1,
    recent_form_window: int = RECENT_FORM_WINDOW,
    home_advantage: float = DEFAULT_HOME_ADVANTAGE,
) -> list[HistoricalGameRow]:
    """Build E7 rows plus same-season, strictly-prior recent-form inputs.

    The recent window holds only completed games earlier than the current row
    and is cleared for a club when its next season begins.  This deliberately
    avoids treating last season's final games as current form.
    """

    if minimum_prior_games < 1:
        raise ValueError("minimum_prior_games must be at least 1")
    if minimum_league_games_for_average < 1:
        raise ValueError("minimum_league_games_for_average must be at least 1")
    if minimum_prior_matchups < 1:
        raise ValueError("minimum_prior_matchups must be at least 1")
    if recent_form_window < 1:
        raise ValueError("recent_form_window must be at least 1")

    team_totals: dict[str, _TeamAccumulator] = {}
    opponent_counts: dict[str, dict[str, int]] = {}
    recent_results: dict[str, list[tuple[int, int]]] = {}
    recent_season: dict[str, int] = {}
    league_runs = league_games = 0
    rows: list[HistoricalGameRow] = []

    def schedule_profile(team_id: str, league_average: float) -> tuple[float, float]:
        opponents = opponent_counts.get(team_id, {})
        matchup_count = sum(opponents.values())
        if matchup_count < minimum_prior_matchups:
            raise ValueError("insufficient prior opponents for schedule profile")
        weighted_offence = weighted_prevention = 0.0
        for opponent_id, times_faced in opponents.items():
            opponent = team_totals[opponent_id]
            weighted_offence += times_faced * run_rate_index(
                opponent.runs_scored / opponent.games_played, league_average
            )
            weighted_prevention += times_faced * run_rate_index(
                opponent.runs_allowed / opponent.games_played, league_average
            )
        return weighted_offence / matchup_count, weighted_prevention / matchup_count

    def prior_recent(team_id: str, season: int) -> list[tuple[int, int]]:
        if recent_season.get(team_id) != season:
            return []
        return recent_results.get(team_id, [])

    def record_recent(team_id: str, season: int, scored: int, allowed: int) -> None:
        if recent_season.get(team_id) != season:
            recent_season[team_id] = season
            recent_results[team_id] = []
        history = recent_results[team_id]
        history.append((scored, allowed))
        if len(history) > recent_form_window:
            history.pop(0)

    for game in sorted(games, key=lambda item: (item.start_time, item.game_id)):
        season = game.official_date.year
        home = team_totals.get(game.home_team_id, _TeamAccumulator())
        away = team_totals.get(game.away_team_id, _TeamAccumulator())
        home_recent = prior_recent(game.home_team_id, season)
        away_recent = prior_recent(game.away_team_id, season)
        home_matchups = sum(opponent_counts.get(game.home_team_id, {}).values())
        away_matchups = sum(opponent_counts.get(game.away_team_id, {}).values())

        eligible = (
            home.games_played >= minimum_prior_games
            and away.games_played >= minimum_prior_games
            and league_games >= minimum_league_games_for_average
            and home_matchups >= minimum_prior_matchups
            and away_matchups >= minimum_prior_matchups
            and len(home_recent) >= recent_form_window
            and len(away_recent) >= recent_form_window
        )
        if eligible:
            league_average = league_runs / league_games
            home_opponent_offence, home_opponent_prevention = schedule_profile(
                game.home_team_id, league_average
            )
            away_opponent_offence, away_opponent_prevention = schedule_profile(
                game.away_team_id, league_average
            )
            rows.append(
                HistoricalGameRow(
                    game_id=game.game_id,
                    official_date=game.official_date,
                    prediction_timestamp=game.start_time,
                    feature_timestamp=game.start_time,
                    features={
                        "home_offensive_index": run_rate_index(home.runs_scored / home.games_played, league_average),
                        "away_offensive_index": run_rate_index(away.runs_scored / away.games_played, league_average),
                        "home_run_prevention_index": run_rate_index(home.runs_allowed / home.games_played, league_average),
                        "away_run_prevention_index": run_rate_index(away.runs_allowed / away.games_played, league_average),
                        "home_advantage": home_advantage,
                        "home_opponent_offensive_index": home_opponent_offence,
                        "home_opponent_run_prevention_index": home_opponent_prevention,
                        "away_opponent_offensive_index": away_opponent_offence,
                        "away_opponent_run_prevention_index": away_opponent_prevention,
                        "home_recent_offensive_index": run_rate_index(
                            sum(scored for scored, _ in home_recent) / recent_form_window,
                            league_average,
                        ),
                        "home_recent_run_prevention_index": run_rate_index(
                            sum(allowed for _, allowed in home_recent) / recent_form_window,
                            league_average,
                        ),
                        "away_recent_offensive_index": run_rate_index(
                            sum(scored for scored, _ in away_recent) / recent_form_window,
                            league_average,
                        ),
                        "away_recent_run_prevention_index": run_rate_index(
                            sum(allowed for _, allowed in away_recent) / recent_form_window,
                            league_average,
                        ),
                    },
                    home_runs=game.home_runs,
                    away_runs=game.away_runs,
                )
            )

        # All state changes happen after row construction.  Therefore a
        # game's own score is available only to later games.
        home.runs_scored += game.home_runs
        home.runs_allowed += game.away_runs
        home.games_played += 1
        away.runs_scored += game.away_runs
        away.runs_allowed += game.home_runs
        away.games_played += 1
        team_totals[game.home_team_id], team_totals[game.away_team_id] = home, away
        home_opponents = opponent_counts.setdefault(game.home_team_id, {})
        home_opponents[game.away_team_id] = home_opponents.get(game.away_team_id, 0) + 1
        away_opponents = opponent_counts.setdefault(game.away_team_id, {})
        away_opponents[game.home_team_id] = away_opponents.get(game.home_team_id, 0) + 1
        record_recent(game.home_team_id, season, game.home_runs, game.away_runs)
        record_recent(game.away_team_id, season, game.away_runs, game.home_runs)
        league_runs += game.home_runs + game.away_runs
        league_games += 2

    return rows


def _parse_innings_pitched_to_outs(value: str) -> int:
    """Convert MLB's ``5.1``/``5.2`` innings notation into outs.

    The digit after the decimal is outs in the inning, not a base-10 fraction.
    """

    if not isinstance(value, str) or not value.strip():
        raise ValueError("innings_pitched must be a non-empty string")
    parts = value.strip().split(".")
    if len(parts) > 2 or not parts[0].isdigit():
        raise ValueError(f"invalid innings_pitched: {value!r}")
    whole = int(parts[0])
    remainder = 0 if len(parts) == 1 else parts[1]
    if remainder not in (0, "0", "1", "2"):
        raise ValueError(f"invalid innings_pitched fraction: {value!r}")
    return whole * 3 + int(remainder)


def build_point_in_time_rows_with_starters(
    games: list[CompletedGameResult],
    starters: list[PitcherGameLine],
    *,
    minimum_prior_games: int = MINIMUM_PRIOR_GAMES,
    minimum_league_games_for_average: int = MINIMUM_LEAGUE_GAMES_FOR_AVERAGE,
    minimum_prior_starts: int = 1,
    minimum_league_outs_for_average: int = 90,
    home_advantage: float = DEFAULT_HOME_ADVANTAGE,
) -> list[HistoricalGameRow]:
    """Build team and actual-starter features using only earlier games."""

    if minimum_prior_games < 1:
        raise ValueError("minimum_prior_games must be at least 1")
    if minimum_league_games_for_average < 1:
        raise ValueError("minimum_league_games_for_average must be at least 1")
    if minimum_prior_starts < 1:
        raise ValueError("minimum_prior_starts must be at least 1")
    if minimum_league_outs_for_average < 1:
        raise ValueError("minimum_league_outs_for_average must be at least 1")

    starter_by_game_side: dict[tuple[str, str], PitcherGameLine] = {}
    for starter in starters:
        if starter.is_actual_starter:
            key = (starter.game_id, starter.side)
            if key in starter_by_game_side:
                raise ValueError(f"duplicate actual starter for {starter.game_id}/{starter.side}")
            starter_by_game_side[key] = starter

    team_totals: dict[str, _TeamAccumulator] = {}
    pitcher_totals: dict[str, _PitcherAccumulator] = {}
    league_runs = league_games = 0
    league_starter_earned_runs = league_starter_outs = 0
    rows: list[HistoricalGameRow] = []

    for game in sorted(games, key=lambda item: (item.start_time, item.game_id)):
        home = team_totals.get(game.home_team_id, _TeamAccumulator())
        away = team_totals.get(game.away_team_id, _TeamAccumulator())
        home_starter = starter_by_game_side.get((game.game_id, "home"))
        away_starter = starter_by_game_side.get((game.game_id, "away"))
        home_history = pitcher_totals.get(home_starter.pitcher_id, _PitcherAccumulator()) if home_starter else None
        away_history = pitcher_totals.get(away_starter.pitcher_id, _PitcherAccumulator()) if away_starter else None

        eligible = (
            home_starter is not None
            and away_starter is not None
            and home_history is not None
            and away_history is not None
            and home.games_played >= minimum_prior_games
            and away.games_played >= minimum_prior_games
            and league_games >= minimum_league_games_for_average
            and home_history.starts >= minimum_prior_starts
            and away_history.starts >= minimum_prior_starts
            and home_history.outs > 0
            and away_history.outs > 0
            and league_starter_outs >= minimum_league_outs_for_average
        )
        if eligible:
            league_average = league_runs / league_games
            league_starter_era = 27 * league_starter_earned_runs / league_starter_outs
            features = {
                "home_offensive_index": run_rate_index(home.runs_scored / home.games_played, league_average),
                "away_offensive_index": run_rate_index(away.runs_scored / away.games_played, league_average),
                "home_run_prevention_index": run_rate_index(home.runs_allowed / home.games_played, league_average),
                "away_run_prevention_index": run_rate_index(away.runs_allowed / away.games_played, league_average),
                "home_advantage": home_advantage,
                "home_starter_era_index": (27 * home_history.earned_runs / home_history.outs) / league_starter_era,
                "away_starter_era_index": (27 * away_history.earned_runs / away_history.outs) / league_starter_era,
            }
            rows.append(HistoricalGameRow(
                game_id=game.game_id,
                official_date=game.official_date,
                prediction_timestamp=game.start_time,
                feature_timestamp=game.start_time,
                features=features,
                home_runs=game.home_runs,
                away_runs=game.away_runs,
            ))

        # Team totals always advance.  Pitcher totals advance only where an
        # actual-starter record exists; a missing record must never be guessed.
        home.runs_scored += game.home_runs
        home.runs_allowed += game.away_runs
        home.games_played += 1
        away.runs_scored += game.away_runs
        away.runs_allowed += game.home_runs
        away.games_played += 1
        team_totals[game.home_team_id], team_totals[game.away_team_id] = home, away
        league_runs += game.home_runs + game.away_runs
        league_games += 2
        for starter in (home_starter, away_starter):
            if starter is None:
                continue
            history = pitcher_totals.setdefault(starter.pitcher_id, _PitcherAccumulator())
            history.earned_runs += starter.earned_runs
            history.outs += _parse_innings_pitched_to_outs(starter.innings_pitched)
            history.starts += 1
            league_starter_earned_runs += starter.earned_runs
            league_starter_outs += _parse_innings_pitched_to_outs(starter.innings_pitched)

    return rows


def build_point_in_time_rows_with_park_factor(
    games: list[CompletedGameResult], venues: dict[str, str], *,
    minimum_prior_games: int = MINIMUM_PRIOR_GAMES,
    minimum_league_games_for_average: int = MINIMUM_LEAGUE_GAMES_FOR_AVERAGE,
    minimum_games_at_venue: int = MINIMUM_GAMES_AT_VENUE,
    home_advantage: float = DEFAULT_HOME_ADVANTAGE,
) -> list[HistoricalGameRow]:
    """Build team features plus a prior-only empirical park run factor."""
    if minimum_prior_games < 1 or minimum_league_games_for_average < 1 or minimum_games_at_venue < 1:
        raise ValueError("all park-factor thresholds must be positive")
    teams: dict[str, _TeamAccumulator] = {}
    parks: dict[str, _VenueAccumulator] = {}
    league_runs = league_games = 0
    rows: list[HistoricalGameRow] = []
    for game in sorted(games, key=lambda item: (item.start_time, item.game_id)):
        home, away = teams.get(game.home_team_id, _TeamAccumulator()), teams.get(game.away_team_id, _TeamAccumulator())
        raw_venue = venues.get(game.game_id)
        venue = canonical_venue_name(raw_venue) if raw_venue else None
        park = parks.get(venue, _VenueAccumulator()) if venue else None
        if (venue and park and home.games_played >= minimum_prior_games and away.games_played >= minimum_prior_games
                and league_games >= minimum_league_games_for_average and park.games >= minimum_games_at_venue):
            league_average = league_runs / league_games
            rows.append(HistoricalGameRow(game.game_id, game.official_date, game.start_time, game.start_time, {
                "home_offensive_index": run_rate_index(home.runs_scored / home.games_played, league_average),
                "away_offensive_index": run_rate_index(away.runs_scored / away.games_played, league_average),
                "home_run_prevention_index": run_rate_index(home.runs_allowed / home.games_played, league_average),
                "away_run_prevention_index": run_rate_index(away.runs_allowed / away.games_played, league_average),
                "home_advantage": home_advantage,
                "park_run_factor_index": run_rate_index(park.runs / park.games / 2, league_average),
            }, game.home_runs, game.away_runs))
        home.runs_scored += game.home_runs; home.runs_allowed += game.away_runs; home.games_played += 1
        away.runs_scored += game.away_runs; away.runs_allowed += game.home_runs; away.games_played += 1
        teams[game.home_team_id], teams[game.away_team_id] = home, away
        league_runs += game.home_runs + game.away_runs; league_games += 2
        if venue:
            park = parks.setdefault(venue, _VenueAccumulator()); park.runs += game.home_runs + game.away_runs; park.games += 1
    return rows


def build_point_in_time_rows_with_bullpen(
    games: list[CompletedGameResult], bullpen_lines: list[PitcherGameLine], *,
    minimum_prior_games: int = MINIMUM_PRIOR_GAMES,
    minimum_league_games_for_average: int = MINIMUM_LEAGUE_GAMES_FOR_AVERAGE,
    minimum_team_bullpen_outs: int = 90,
    minimum_league_outs_for_average: int = 90,
    home_advantage: float = DEFAULT_HOME_ADVANTAGE,
) -> list[HistoricalGameRow]:
    """Build team plus relief-pitching ERA indices, strictly prior to each game."""
    if min(minimum_prior_games, minimum_league_games_for_average, minimum_team_bullpen_outs, minimum_league_outs_for_average) < 1:
        raise ValueError("all bullpen thresholds must be positive")
    by_game: dict[str, list[PitcherGameLine]] = {}
    for line in bullpen_lines:
        if not line.is_actual_starter: by_game.setdefault(line.game_id, []).append(line)
    teams: dict[str, _TeamAccumulator] = {}; bullpens: dict[str, _BullpenAccumulator] = {}
    league_runs = league_games = league_er = league_outs = 0; rows: list[HistoricalGameRow] = []
    for game in sorted(games, key=lambda item:(item.start_time,item.game_id)):
        home, away = teams.get(game.home_team_id,_TeamAccumulator()), teams.get(game.away_team_id,_TeamAccumulator())
        home_bp, away_bp = bullpens.get(game.home_team_id,_BullpenAccumulator()), bullpens.get(game.away_team_id,_BullpenAccumulator())
        if (home.games_played >= minimum_prior_games and away.games_played >= minimum_prior_games and league_games >= minimum_league_games_for_average and home_bp.outs >= minimum_team_bullpen_outs and away_bp.outs >= minimum_team_bullpen_outs and league_outs >= minimum_league_outs_for_average):
            league_avg=league_runs/league_games; league_era=27*league_er/league_outs
            rows.append(HistoricalGameRow(game.game_id,game.official_date,game.start_time,game.start_time,{
                'home_offensive_index':run_rate_index(home.runs_scored/home.games_played,league_avg),'away_offensive_index':run_rate_index(away.runs_scored/away.games_played,league_avg),'home_run_prevention_index':run_rate_index(home.runs_allowed/home.games_played,league_avg),'away_run_prevention_index':run_rate_index(away.runs_allowed/away.games_played,league_avg),'home_advantage':home_advantage,'home_bullpen_era_index':(27*home_bp.earned_runs/home_bp.outs)/league_era,'away_bullpen_era_index':(27*away_bp.earned_runs/away_bp.outs)/league_era},game.home_runs,game.away_runs))
        home.runs_scored+=game.home_runs; home.runs_allowed+=game.away_runs; home.games_played+=1; away.runs_scored+=game.away_runs; away.runs_allowed+=game.home_runs; away.games_played+=1; teams[game.home_team_id],teams[game.away_team_id]=home,away; league_runs+=game.home_runs+game.away_runs; league_games+=2
        for line in by_game.get(game.game_id,[]):
            team_id=game.home_team_id if line.side=='home' else game.away_team_id; bp=bullpens.setdefault(team_id,_BullpenAccumulator()); outs=_parse_innings_pitched_to_outs(line.innings_pitched); bp.earned_runs+=line.earned_runs; bp.outs+=outs; league_er+=line.earned_runs; league_outs+=outs
    return rows
