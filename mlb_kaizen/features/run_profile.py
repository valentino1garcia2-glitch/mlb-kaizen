"""Fase 4 feature: offensive_index / run_prevention_index (formula v1).

Turns a raw TeamSeasonStats snapshot into the normalised TeamRunProfile the
baseline model consumes. See docs/features/run_profile.md for the full fiche
(source, temporal availability, formula, missing-value policy) required by
HANDOFF.md's Fase 4 plan — this module is the implementation of that fiche,
not a replacement for it; change both together.

This module never fetches anything itself. league_average_runs_per_game is a
required argument, not a default: MLBStatsProvider.league_average_runs_per_game
computes a real one from all 30 teams (see mlb_kaizen/data/mlb_stats.py), but
this module still takes it as a plain float parameter rather than importing
the provider, so the formula stays testable without any network dependency
and reusable if a league average is ever sourced a different way (e.g. a
stored historical snapshot for a backtest instead of a live fetch).
"""

from __future__ import annotations

from mlb_kaizen.domain.models import AvailabilityStatus, DataProvenance, TeamRunProfile, TeamSeasonStats

#: Bumped whenever the formula below changes, so a stored TeamRunProfile's
#: provenance.source_version says exactly which formula produced it —
#: required by the project rule that changing the model must never silently
#: alter what a past prediction was based on.
FORMULA_VERSION = "run_profile_formula_v1"

#: Games played at which data_quality reaches 1.0. Below this, data_quality
#: scales linearly with games_played/this value — an April team with 8 games
#: played gets a low-confidence profile, not a false-certain one. This is a
#: documented assumption, not a fitted value; revisit once real backtesting
#: (Fase 6) can say what sample size actually stabilises team run rates.
GAMES_FOR_FULL_CONFIDENCE = 30


def run_rate_index(runs_per_game: float, league_average_runs_per_game: float) -> float:
    """Ratio of a per-game run rate to the league average -- 1.0 is exactly average.

    Single source of truth for the formula v1 math, shared by
    compute_team_run_profile (season-snapshot input) and
    mlb_kaizen.training.build_dataset (point-in-time accumulation input) so
    the two can never silently drift apart.
    """

    if league_average_runs_per_game <= 0:
        raise ValueError("league_average_runs_per_game must be positive")
    return runs_per_game / league_average_runs_per_game


def compute_team_run_profile(
    stats: TeamSeasonStats,
    league_average_runs_per_game: float,
    *,
    games_for_full_confidence: int = GAMES_FOR_FULL_CONFIDENCE,
) -> TeamRunProfile:
    """Compute offensive_index and run_prevention_index for one team.

    offensive_index = (runs_scored / games_played) / league_average_runs_per_game
    run_prevention_index = (runs_allowed / games_played) / league_average_runs_per_game

    Both are ratios to the same league-wide runs-per-team-game rate, so 1.0
    means exactly average in both directions; run_prevention_index uses
    total runs allowed (not just earned runs — see TeamSeasonStats docstring)
    because that is what actually crosses the plate against this team.

    Missing-value policy: raises ValueError rather than returning a
    default-looking profile when games_played is 0 (nothing to compute from)
    or league_average_runs_per_game is not positive (a caller bug, not a
    data-availability case) — silently returning offensive_index=1.0 would
    be indistinguishable from a genuinely average team, which is exactly the
    kind of invented-looking number this project forbids.
    """

    if stats.games_played == 0:
        raise ValueError("cannot compute a run profile with zero games played")
    if games_for_full_confidence <= 0:
        raise ValueError("games_for_full_confidence must be positive")

    runs_scored_per_game = stats.runs_scored / stats.games_played
    runs_allowed_per_game = stats.runs_allowed / stats.games_played

    offensive_index = run_rate_index(runs_scored_per_game, league_average_runs_per_game)
    run_prevention_index = run_rate_index(runs_allowed_per_game, league_average_runs_per_game)

    data_quality = min(1.0, stats.games_played / games_for_full_confidence)

    provenance = DataProvenance(
        source=f"computed: {FORMULA_VERSION} from TeamSeasonStats",
        retrieved_at=stats.provenance.retrieved_at,
        status=AvailabilityStatus.AVAILABLE,
        source_url=stats.provenance.source_url,
        source_version=FORMULA_VERSION,
    )

    return TeamRunProfile(
        team_id=stats.team_id,
        team_name=stats.team_name,
        offensive_index=offensive_index,
        run_prevention_index=run_prevention_index,
        sample_size=stats.games_played,
        data_quality=data_quality,
        provenance=provenance,
    )
