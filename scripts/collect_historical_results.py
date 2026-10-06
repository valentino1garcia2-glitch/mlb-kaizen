#!/usr/bin/env python3
"""Collect an immutable, official MLB final-results file with game type.

Example:
  python scripts/collect_historical_results.py --start-date 2012-03-01 \
      --end-date 2025-12-31 --output data/external/mlb_results_2012_2025.jsonl

The output contains both regular-season and playoff results.  It is a source
archive for later point-in-time experiments, not itself a pregame feature
dataset and not evidence that the results were known before a game started.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mlb_kaizen.config.settings import Settings
from mlb_kaizen.data.historical_results import save_completed_game_results
from mlb_kaizen.data.http import CachedHttpClient, DataProviderError
from mlb_kaizen.data.mlb_stats import MLBStatsProvider


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-days-per-request", type=int, default=180)
    args = parser.parse_args(argv)
    if args.end_date < args.start_date:
        parser.error("--end-date must not be before --start-date")
    if args.output.exists():
        parser.error(f"refusing to overwrite existing collection: {args.output}")

    settings = Settings.from_environment()
    provider = MLBStatsProvider(CachedHttpClient(
        settings.cache_dir, timeout_seconds=settings.http_timeout_seconds,
        retries=settings.http_retries, cache_ttl_seconds=settings.cache_ttl_seconds,
    ))
    try:
        results = provider.completed_games_batched(
            args.start_date, args.end_date, max_days_per_request=args.max_days_per_request,
        )
    except DataProviderError as exc:
        print(f"DATA NOT VERIFIED: {exc}")
        return 2
    if not results:
        print("No final scored games found in the requested interval.")
        return 1

    written = save_completed_game_results(args.output, results)
    types = {result.game_type or "UNKNOWN" for result in results}
    print(f"Saved {written} official final results to {args.output}.")
    print(f"Game types present: {', '.join(sorted(types))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
