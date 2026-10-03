#!/usr/bin/env python3
"""Build a real, point-in-time HistoricalGameRow dataset from completed MLB games.

Usage:
    python3 scripts/build_historical_dataset.py \
        --start-date 2025-06-01 --end-date 2025-08-31 \
        --output data/historical/2025_summer.jsonl

Only ONE assumption is hardcoded and undocumented-nowhere: home_advantage
uses models.baseline's own default (1.035) -- see
mlb_kaizen.training.build_dataset.DEFAULT_HOME_ADVANTAGE. Everything else
(offensive_index, run_prevention_index, the league average) is computed from
real games actually returned by the MLB Stats API for the requested range,
accumulated strictly point-in-time (see build_dataset.py's module docstring).

Requires real network access. This project's own development sandbox does
not have it for arbitrary date ranges (see HANDOFF.md sections 16, 18, 20) --
run this where a real, unrestricted fetch to statsapi.mlb.com works: Claude
Code, a local machine, another session with genuine internet access.

IMPORTANT: a date range only produces usable rows once
minimum_prior_games and minimum_league_games_for_average are satisfied (see
build_dataset.py). A narrow range (a few days) will skip its early games and
may produce zero rows -- request a few weeks at minimum for the defaults to
produce any output, and check the coverage summary this script prints.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mlb_kaizen.config.settings import Settings
from mlb_kaizen.data.http import CachedHttpClient, DataProviderError
from mlb_kaizen.data.mlb_stats import MLBStatsProvider
from mlb_kaizen.observability.logging import configure_logging
from mlb_kaizen.training.build_dataset import (
    DEFAULT_HOME_ADVANTAGE,
    MINIMUM_LEAGUE_GAMES_FOR_AVERAGE,
    MINIMUM_PRIOR_GAMES,
    build_point_in_time_rows,
)
from mlb_kaizen.training.dataset import save_jsonl


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", required=True, type=date.fromisoformat)
    parser.add_argument("--end-date", required=True, type=date.fromisoformat)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--minimum-prior-games", type=int, default=MINIMUM_PRIOR_GAMES,
        help="minimum strictly-prior games a team needs before a row is emitted for it",
    )
    parser.add_argument(
        "--minimum-league-games-for-average", type=int, default=MINIMUM_LEAGUE_GAMES_FOR_AVERAGE,
        help="minimum league-wide team-games observed before the running league average is used",
    )
    parser.add_argument("--home-advantage", type=float, default=DEFAULT_HOME_ADVANTAGE)
    args = parser.parse_args(argv)

    if args.end_date < args.start_date:
        parser.error("--end-date must not be before --start-date")

    settings = Settings.from_environment()
    client = CachedHttpClient(
        settings.cache_dir,
        timeout_seconds=settings.http_timeout_seconds,
        retries=settings.http_retries,
        cache_ttl_seconds=settings.cache_ttl_seconds,
    )
    provider = MLBStatsProvider(client)

    try:
        games = provider.completed_games(args.start_date, args.end_date)
    except DataProviderError as exc:
        print(f"DATA NOT VERIFIED: {exc}")
        return 2

    if not games:
        print(f"No Final games found between {args.start_date} and {args.end_date}.")
        return 1

    rows = build_point_in_time_rows(
        games,
        minimum_prior_games=args.minimum_prior_games,
        minimum_league_games_for_average=args.minimum_league_games_for_average,
        home_advantage=args.home_advantage,
    )

    if not rows:
        print(
            f"Fetched {len(games)} completed games but produced 0 usable rows -- "
            "the date range is too narrow for --minimum-prior-games/"
            "--minimum-league-games-for-average. Widen the range or lower the thresholds."
        )
        return 1

    save_jsonl(args.output, rows)

    teams_seen = {g.home_team_id for g in games} | {g.away_team_id for g in games}
    print(
        f"Fetched {len(games)} completed games across {len(teams_seen)} teams "
        f"({args.start_date} to {args.end_date})."
    )
    print(f"Wrote {len(rows)} point-in-time rows to {args.output}")
    print(
        f"Skipped {len(games) - len(rows)} games (insufficient prior history "
        f"for at least one side, or league average not yet stable)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
