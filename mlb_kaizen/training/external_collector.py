"""Loader for the external MLB_KAIZEN_GAME_COLLECTOR normalized JSONL format.

This is a different shape from MLBStatsProvider.parse_completed_games (which
reads a raw MLB Stats API schedule response directly): it reads the *output*
of a separate batch collector the user ran in Google Colab, documented in
that dataset's own audit/manifest.json. Kept as its own module because the
two are genuinely different contracts that happen to produce the same
CompletedGameResult domain type -- conflating them would hide which format
is actually being read.

Independently audited before use (see HANDOFF.md section 21): 12,045 unique
games, 0 duplicate game_ids, season totals matching the real 30-team/162-game
schedule exactly (2430 = 30*162/2) for 2022-2025, real integer scores,
schema_version "1.0" consistent across every file.
"""

from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
from typing import Sequence

from mlb_kaizen.domain.models import (
    AvailabilityStatus,
    CompletedGameResult,
    DataProvenance,
    PitcherGameLine,
)

#: The only schema_version this loader understands. A file claiming a
#: different version is rejected rather than parsed optimistically -- an
#: unannounced schema change could silently reinterpret fields.
EXPECTED_SCHEMA_VERSION = "1.0"


def load_completed_games_from_collector(paths: Sequence[Path]) -> list[CompletedGameResult]:
    """Read one or more collector games.jsonl files into CompletedGameResult.

    Silently excludes: non-Final games, and Final games with no published
    score (both are legitimate collector outputs, not errors -- the
    collector's own audit already counts them, see manifest.json
    "games_without_score"). Everything else is fail-loud: a missing
    required field or an unrecognised schema_version raises ValueError
    naming the file and line, rather than skipping or guessing.
    """

    games: list[CompletedGameResult] = []
    seen_ids: set[str] = set()
    for path in paths:
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw_line.strip():
                continue
            try:
                row = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc

            schema_version = row.get("schema_version")
            if schema_version != EXPECTED_SCHEMA_VERSION:
                raise ValueError(
                    f"{path}:{line_number}: unexpected schema_version {schema_version!r}, "
                    f"expected {EXPECTED_SCHEMA_VERSION!r}"
                )
            if row.get("status") != "Final":
                continue
            score = row.get("score") or {}
            home_runs, away_runs = score.get("home"), score.get("away")
            if home_runs is None or away_runs is None:
                continue

            try:
                game_id = f"mlb:{row['game_id']}"
                home_team = row["home_team"]
                away_team = row["away_team"]
                collection = row["collection"]
                start_time = _parse_timestamp(row["game_datetime"])
                official_date = date.fromisoformat(str(row["official_date"]))
                provenance = DataProvenance(
                    source=f"external collector: {collection.get('source', 'unknown')}",
                    retrieved_at=_parse_timestamp(collection["retrieved_at"]),
                    status=AvailabilityStatus.AVAILABLE,
                    source_url=collection.get("request_url"),
                )
                game = CompletedGameResult(
                    game_id=game_id,
                    official_date=official_date,
                    start_time=start_time,
                    home_team_id=str(home_team["id"]),
                    home_team_name=str(home_team.get("name", "")),
                    away_team_id=str(away_team["id"]),
                    away_team_name=str(away_team.get("name", "")),
                    home_runs=int(home_runs),
                    away_runs=int(away_runs),
                    provenance=provenance,
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"{path}:{line_number}: invalid row: {exc}") from exc

            if game_id in seen_ids:
                # The collector's own manifest reports duplicates_removed
                # already applied before this file was written; this is a
                # defensive second check, not an expected path.
                continue
            seen_ids.add(game_id)
            games.append(game)
    return games


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_completed_games_v2(paths: Sequence[Path]) -> list[CompletedGameResult]:
    """Read the flat 2026-09-20 collector format.

    This collector intentionally has a separate loader: it uses flat score
    fields rather than the older collector's nested ``score`` object.  Final
    records without a published score are legitimate API records and are
    excluded, never guessed as 0-0.
    """

    games: list[CompletedGameResult] = []
    seen_ids: set[str] = set()
    for path in paths:
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw_line.strip():
                continue
            try:
                row = json.loads(raw_line)
                if row.get("status") != "Final":
                    continue
                home_runs, away_runs = row.get("home_score"), row.get("away_score")
                if home_runs is None or away_runs is None:
                    continue
                game_id = f"mlb:{row['game_id']}"
                if game_id in seen_ids:
                    continue
                game = CompletedGameResult(
                    game_id=game_id,
                    official_date=date.fromisoformat(str(row["date"])),
                    start_time=_parse_timestamp(row["game_datetime"]),
                    home_team_id=str(row["home_team_id"]),
                    home_team_name=str(row["home_team_name"]),
                    away_team_id=str(row["away_team_id"]),
                    away_team_name=str(row["away_team_name"]),
                    home_runs=int(home_runs),
                    away_runs=int(away_runs),
                    provenance=DataProvenance(
                        source=f"external collector v2: {row.get('source', 'unknown')}",
                        retrieved_at=_parse_timestamp(row["retrieved_at"]),
                        status=AvailabilityStatus.AVAILABLE,
                        source_url=row.get("request_url"),
                    ),
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"{path}:{line_number}: invalid v2 game row: {exc}") from exc
            seen_ids.add(game_id)
            games.append(game)
    return games


def load_pitcher_starter_lines(paths: Sequence[Path]) -> list[PitcherGameLine]:
    """Read real pitcher lines and retain only the actual starter per side."""

    lines: list[PitcherGameLine] = []
    seen_game_sides: set[tuple[str, str]] = set()
    for path in paths:
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw_line.strip():
                continue
            try:
                row = json.loads(raw_line)
                if row.get("is_actual_starter") is not True:
                    continue
                game_id = f"mlb:{row['game_id']}"
                side = str(row["side"])
                key = (game_id, side)
                if key in seen_game_sides:
                    raise ValueError("duplicate actual starter for game side")
                line = PitcherGameLine(
                    game_id=game_id,
                    pitcher_id=str(row["pitcher_id"]),
                    pitcher_name=str(row["pitcher_name"]),
                    side=side,
                    innings_pitched=str(row["innings_pitched"]),
                    runs_allowed=int(row["runs"]),
                    earned_runs=int(row["earned_runs"]),
                    is_actual_starter=True,
                    provenance=DataProvenance(
                        source=f"external pitcher collector: {row.get('source', 'unknown')}",
                        retrieved_at=_parse_timestamp(row["retrieved_at"]),
                        status=AvailabilityStatus.AVAILABLE,
                    ),
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"{path}:{line_number}: invalid pitcher row: {exc}") from exc
            seen_game_sides.add(key)
            lines.append(line)
    return lines


def load_game_venues_v2(paths: Sequence[Path]) -> dict[str, str]:
    """Return raw v2 venue names keyed by game id; model rules canonicalise later."""
    venues: dict[str, str] = {}
    for path in paths:
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw_line.strip():
                continue
            try:
                row = json.loads(raw_line)
                venue = row.get("venue")
                if venue:
                    venues[f"mlb:{row['game_id']}"] = str(venue)
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                raise ValueError(f"{path}:{line_number}: invalid v2 venue row: {exc}") from exc
    return venues
