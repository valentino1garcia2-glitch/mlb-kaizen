"""Versioned JSONL persistence for official, post-game MLB results.

These records are retrospective outcomes.  Their retrieval timestamp is kept
for provenance, but is never evidence that an outcome was known before the
game.  Feature builders must still use only results strictly prior to each
prediction timestamp.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Iterable

from mlb_kaizen.domain.models import AvailabilityStatus, CompletedGameResult, DataProvenance


SCHEMA_VERSION = "1.0"
RECORD_TYPE = "completed_game_result"


def save_completed_game_results(path: Path, results: Iterable[CompletedGameResult]) -> int:
    """Write one immutable, schema-versioned capture of final game results.

    A pre-existing target is rejected rather than silently overwritten.  This
    makes a later audit able to distinguish separate historical collections.
    """

    records = sorted(results, key=lambda result: (result.start_time, result.game_id))
    seen_ids: set[str] = set()
    lines: list[str] = []
    for result in records:
        if result.game_id in seen_ids:
            raise ValueError(f"duplicate completed-game id: {result.game_id}")
        seen_ids.add(result.game_id)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "record_type": RECORD_TYPE,
            "game_id": result.game_id,
            "official_date": result.official_date.isoformat(),
            "start_time": result.start_time.isoformat(),
            "game_type": result.game_type,
            "home_team": {"id": result.home_team_id, "name": result.home_team_name},
            "away_team": {"id": result.away_team_id, "name": result.away_team_name},
            "score": {"home": result.home_runs, "away": result.away_runs},
            "provenance": {
                "source": result.provenance.source,
                "retrieved_at": result.provenance.retrieved_at.isoformat(),
                "source_url": result.provenance.source_url,
            },
        }
        lines.append(json.dumps(payload, sort_keys=True, separators=(",", ":")))

    if not lines:
        raise ValueError("cannot save an empty completed-game collection")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return len(records)


def load_completed_game_results(path: Path) -> tuple[CompletedGameResult, ...]:
    """Load a collection strictly, rejecting incompatible or ambiguous rows."""

    results: list[CompletedGameResult] = []
    seen_ids: set[str] = set()
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
            if row.get("schema_version") != SCHEMA_VERSION or row.get("record_type") != RECORD_TYPE:
                raise ValueError("unsupported completed-game result schema")
            home, away, score, provenance = row["home_team"], row["away_team"], row["score"], row["provenance"]
            if not all(isinstance(value, dict) for value in (home, away, score, provenance)):
                raise ValueError("team, score and provenance must be objects")
            result = CompletedGameResult(
                game_id=str(row["game_id"]),
                official_date=datetime.fromisoformat(str(row["official_date"])).date(),
                start_time=_parse_timestamp(row["start_time"]),
                home_team_id=str(home["id"]), home_team_name=str(home["name"]),
                away_team_id=str(away["id"]), away_team_name=str(away["name"]),
                home_runs=int(score["home"]), away_runs=int(score["away"]),
                game_type=str(row["game_type"]) if row.get("game_type") is not None else None,
                provenance=DataProvenance(
                    source=str(provenance["source"]),
                    retrieved_at=_parse_timestamp(provenance["retrieved_at"]),
                    source_url=str(provenance["source_url"]) if provenance.get("source_url") else None,
                    status=AvailabilityStatus.AVAILABLE,
                ),
            )
            if result.game_id in seen_ids:
                raise ValueError(f"duplicate completed-game id: {result.game_id}")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"{path}:{line_number}: invalid completed-game result: {exc}") from exc
        seen_ids.add(result.game_id)
        results.append(result)
    if not results:
        raise ValueError(f"{path}: completed-game collection is empty")
    return tuple(sorted(results, key=lambda result: (result.start_time, result.game_id)))


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return parsed
