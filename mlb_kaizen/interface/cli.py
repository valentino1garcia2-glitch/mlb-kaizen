"""CLI that exposes only operations backed by explicit data contracts."""

from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import logging
from pathlib import Path
from typing import Any

from mlb_kaizen.config.settings import Settings
from mlb_kaizen.data.http import CachedHttpClient, DataProviderError
from mlb_kaizen.data.mlb_stats import MLBStatsProvider
from mlb_kaizen.domain.models import (
    AnalysisContext,
    AvailabilityStatus,
    DataProvenance,
    Game,
    TeamRunProfile,
)
from mlb_kaizen.reporting.text import render_analysis_report
from mlb_kaizen.services.analysis import AnalysisRequest, AnalysisService, MarketInput
from mlb_kaizen.storage.database import KaizenDatabase


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamps must include a UTC offset, for example +00:00")
    return parsed


def _parse_provenance(payload: dict[str, Any]) -> DataProvenance:
    return DataProvenance(
        source=str(payload["source"]),
        retrieved_at=_parse_timestamp(str(payload["retrieved_at"])),
        effective_at=(
            _parse_timestamp(str(payload["effective_at"])) if payload.get("effective_at") else None
        ),
        source_url=str(payload["source_url"]) if payload.get("source_url") else None,
        source_version=str(payload["source_version"]) if payload.get("source_version") else None,
        status=AvailabilityStatus(str(payload["status"])),
    )


def _parse_game(payload: dict[str, Any]) -> Game:
    return Game(
        game_id=str(payload["game_id"]),
        official_date=date.fromisoformat(str(payload["official_date"])),
        home_team_id=str(payload["home_team_id"]),
        home_team_name=str(payload["home_team_name"]),
        away_team_id=str(payload["away_team_id"]),
        away_team_name=str(payload["away_team_name"]),
        provenance=_parse_provenance(payload["provenance"]),
        start_time=_parse_timestamp(str(payload["start_time"])) if payload.get("start_time") else None,
        venue_name=str(payload["venue_name"]) if payload.get("venue_name") else None,
    )


def _parse_profile(payload: dict[str, Any]) -> TeamRunProfile:
    return TeamRunProfile(
        team_id=str(payload["team_id"]),
        team_name=str(payload["team_name"]),
        offensive_index=float(payload["offensive_index"]),
        run_prevention_index=float(payload["run_prevention_index"]),
        sample_size=int(payload["sample_size"]),
        data_quality=float(payload["data_quality"]),
        provenance=_parse_provenance(payload["provenance"]),
    )


def _parse_analysis_request(input_path: Path) -> AnalysisRequest:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("analysis input must be a JSON object")
    context_data = payload["context"]
    statuses = {
        str(name): AvailabilityStatus(str(status))
        for name, status in dict(context_data.get("data_statuses", {})).items()
    }
    market_data = dict(payload.get("market", {}))
    return AnalysisRequest(
        game=_parse_game(payload["game"]),
        home_profile=_parse_profile(payload["home_profile"]),
        away_profile=_parse_profile(payload["away_profile"]),
        context=AnalysisContext(
            prediction_timestamp=_parse_timestamp(str(context_data["prediction_timestamp"])),
            information_state=str(context_data["information_state"]),
            data_statuses=statuses,
        ),
        market=MarketInput(
            home_decimal_odds=(
                float(market_data["home_decimal_odds"])
                if market_data.get("home_decimal_odds") is not None
                else None
            ),
            away_decimal_odds=(
                float(market_data["away_decimal_odds"])
                if market_data.get("away_decimal_odds") is not None
                else None
            ),
            total_line=float(market_data["total_line"]) if market_data.get("total_line") is not None else None,
            home_run_line=(
                float(market_data["home_run_line"])
                if market_data.get("home_run_line") is not None
                else None
            ),
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the command parser without performing any I/O."""

    parser = argparse.ArgumentParser(prog="mlb-kaizen", description="MLB KAIZEN research engine")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("init-db", help="create the local SQLite schema")
    subcommands.add_parser("health", help="show local system configuration")
    schedule = subcommands.add_parser("schedule", help="retrieve and snapshot an MLB schedule")
    schedule.add_argument("--date", required=True, type=date.fromisoformat, help="official date: YYYY-MM-DD")
    analysis = subcommands.add_parser("analyze", help="run an analysis from timestamped, verified JSON input")
    analysis.add_argument("--input", required=True, type=Path, help="path to an analysis input JSON document")
    analysis.add_argument("--persist", action="store_true", help="append snapshot and prediction to SQLite")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run a CLI operation and return a shell-friendly status code."""

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args(argv)
    settings = Settings.from_environment()
    database = KaizenDatabase(settings.database_path)

    if args.command == "init-db":
        database.initialise()
        print(f"SQLite initialized: {settings.database_path}")
        return 0
    if args.command == "health":
        print(
            json.dumps(
                {
                    "database": str(settings.database_path),
                    "cache_dir": str(settings.cache_dir),
                    "simulation_count": settings.simulation_count,
                    "model_status": "baseline_only_uncalibrated",
                },
                indent=2,
            )
        )
        return 0
    if args.command == "schedule":
        client = CachedHttpClient(
            settings.cache_dir,
            timeout_seconds=settings.http_timeout_seconds,
            retries=settings.http_retries,
            cache_ttl_seconds=settings.cache_ttl_seconds,
        )
        try:
            games = MLBStatsProvider(client).games_on(args.date)
        except DataProviderError as exc:
            print(str(exc))
            return 2
        database.initialise()
        for game in games:
            database.store_game_snapshot(game)
            print(f"{game.game_id}: {game.away_team_name} @ {game.home_team_name} ({game.start_time})")
        print(f"Retrieved {len(games)} games; source timestamp: {games[0].provenance.retrieved_at if games else 'n/a'}")
        return 0
    if args.command == "analyze":
        try:
            request = _parse_analysis_request(args.input)
            if args.persist:
                database.initialise()
                database.store_game_snapshot(request.game)
            result = AnalysisService(settings, database=database).analyse(request, persist=args.persist)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            print(f"Input rejected: {exc}")
            return 2
        print(render_analysis_report(result))
        return 0
    raise AssertionError(f"unknown command: {args.command}")
