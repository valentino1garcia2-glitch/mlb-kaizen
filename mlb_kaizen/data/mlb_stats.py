"""Adapter for the public MLB Stats API schedule endpoint.

The endpoint is used behind a provider boundary because its public documentation
is community maintained. It must not be treated as proof that unavailable fields
are zero or confirmed.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlencode

from mlb_kaizen.data.http import CachedHttpClient, RetrievedJson
from mlb_kaizen.domain.models import AvailabilityStatus, DataProvenance, Game


class MLBStatsProvider:
    """Retrieve only normalised, validated schedule records."""

    base_url = "https://statsapi.mlb.com/api/v1/schedule"
    source_name = "MLB Stats API public endpoint"

    def __init__(self, client: CachedHttpClient) -> None:
        self.client = client

    def games_on(self, game_date: date) -> list[Game]:
        """Get Major League games for a date with source retrieval metadata."""

        query = urlencode({"sportId": 1, "date": game_date.isoformat(), "hydrate": "venue"})
        response = self.client.get_json(f"{self.base_url}?{query}")
        return self.parse_schedule(response, expected_date=game_date)

    @classmethod
    def parse_schedule(cls, response: RetrievedJson, expected_date: date) -> list[Game]:
        """Normalise an MLB schedule payload without silently dropping bad fields."""

        games: list[Game] = []
        dates = response.payload.get("dates")
        if not isinstance(dates, list):
            raise ValueError("schedule response lacks a dates array")

        provenance = DataProvenance(
            source=cls.source_name,
            retrieved_at=response.retrieved_at,
            status=AvailabilityStatus.AVAILABLE,
            source_url=response.url,
        )
        for schedule_day in dates:
            if not isinstance(schedule_day, dict):
                raise ValueError("schedule date record is invalid")
            official_date = date.fromisoformat(str(schedule_day.get("date", expected_date.isoformat())))
            for raw_game in schedule_day.get("games", []):
                games.append(cls._parse_game(raw_game, official_date, provenance))
        return games

    @staticmethod
    def _parse_game(raw_game: Any, official_date: date, provenance: DataProvenance) -> Game:
        if not isinstance(raw_game, dict):
            raise ValueError("game record is invalid")
        teams = raw_game.get("teams")
        if not isinstance(teams, dict):
            raise ValueError("game record lacks teams")
        home = teams.get("home", {}).get("team", {})
        away = teams.get("away", {}).get("team", {})
        if not all(isinstance(value, dict) for value in (home, away)):
            raise ValueError("game record lacks valid teams")

        game_datetime = raw_game.get("gameDate")
        start_time = None
        if isinstance(game_datetime, str):
            start_time = datetime.fromisoformat(game_datetime.replace("Z", "+00:00")).astimezone(UTC)

        venue = raw_game.get("venue") or {}
        return Game(
            game_id=f"mlb:{raw_game['gamePk']}",
            official_date=official_date,
            home_team_id=str(home["id"]),
            home_team_name=str(home["name"]),
            away_team_id=str(away["id"]),
            away_team_name=str(away["name"]),
            start_time=start_time,
            venue_name=str(venue["name"]) if isinstance(venue, dict) and venue.get("name") else None,
            provenance=provenance,
        )
