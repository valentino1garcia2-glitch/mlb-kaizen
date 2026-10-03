#!/usr/bin/env python3
"""Turn the external Colab collector's normalized output into a point-in-time
HistoricalGameRow JSONL dataset -- no network required, everything already
on disk.

Usage:
    python3 scripts/ingest_external_collector.py \
        --input normalized/historical/2022/games.jsonl \
        --input normalized/historical/2023/games.jsonl \
        --input normalized/historical/2024/games.jsonl \
        --input normalized/historical/2025/games.jsonl \
        --input normalized/current/2026/games.jsonl \
        --output data/historical/2022_2026_point_in_time.jsonl
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mlb_kaizen.training.build_dataset import (
    DEFAULT_HOME_ADVANTAGE,
    MINIMUM_LEAGUE_GAMES_FOR_AVERAGE,
    MINIMUM_PRIOR_GAMES,
    build_point_in_time_rows,
)
from mlb_kaizen.training.dataset import save_jsonl
from mlb_kaizen.training.external_collector import load_completed_games_from_collector


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", required=True, type=Path, dest="inputs")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--minimum-prior-games", type=int, default=MINIMUM_PRIOR_GAMES)
    parser.add_argument(
        "--minimum-league-games-for-average", type=int, default=MINIMUM_LEAGUE_GAMES_FOR_AVERAGE
    )
    parser.add_argument("--home-advantage", type=float, default=DEFAULT_HOME_ADVANTAGE)
    args = parser.parse_args(argv)

    missing = [p for p in args.inputs if not p.exists()]
    if missing:
        print(f"Missing input file(s): {', '.join(str(p) for p in missing)}")
        return 2

    games = load_completed_games_from_collector(args.inputs)
    if not games:
        print("No usable Final/scored games found in the given inputs.")
        return 1

    rows = build_point_in_time_rows(
        games,
        minimum_prior_games=args.minimum_prior_games,
        minimum_league_games_for_average=args.minimum_league_games_for_average,
        home_advantage=args.home_advantage,
    )
    if not rows:
        print(f"Loaded {len(games)} games but produced 0 usable point-in-time rows.")
        return 1

    save_jsonl(args.output, rows)

    seasons = sorted({g.official_date.year for g in games})
    teams = {g.home_team_id for g in games} | {g.away_team_id for g in games}
    print(f"Loaded {len(games)} completed games, seasons {seasons}, {len(teams)} teams.")
    print(f"Wrote {len(rows)} point-in-time rows to {args.output}")
    print(f"Skipped {len(games) - len(rows)} games (insufficient prior history).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
