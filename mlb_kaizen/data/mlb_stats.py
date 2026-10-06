"""Adapter for the public MLB Stats API schedule endpoint.

The endpoint is used behind a provider boundary because its public documentation
is community maintained. It must not be treated as proof that unavailable fields
are zero or confirmed.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from mlb_kaizen.data.http import CachedHttpClient, RetrievedJson
from mlb_kaizen.domain.models import (
    AvailabilityStatus,
    CompletedGameResult,
    DataProvenance,
    Game,
    GameLineups,
    LineupSlot,
    ProbablePitcher,
    TeamSeasonStats,
    VenueLocation,
)


def _extract_game_pk(game_id: str) -> str:
    """MLB Stats API identifiers are prefixed 'mlb:' to stay provider-explicit."""

    if not game_id.startswith("mlb:"):
        raise ValueError("game_id must be an MLB Stats API identifier, for example 'mlb:123'")
    return game_id.split(":", 1)[1]


class MLBStatsProvider:
    """Retrieve only normalised, validated schedule records."""

    base_url = "https://statsapi.mlb.com/api/v1/schedule"
    game_url = "https://statsapi.mlb.com/api/v1/game"
    venue_url = "https://statsapi.mlb.com/api/v1/venues"
    stats_url = "https://statsapi.mlb.com/api/v1/stats"
    source_name = "MLB Stats API public endpoint"
    #: MLB currently fields 30 teams. A response with fewer distinct team
    #: splits is treated as truncated/malformed, not as a smaller league.
    minimum_expected_teams = 28

    def __init__(self, client: CachedHttpClient) -> None:
        self.client = client

    def games_on(self, game_date: date) -> list[Game]:
        """Get Major League games for a date with source retrieval metadata."""

        query = urlencode({"sportId": 1, "date": game_date.isoformat(), "hydrate": "venue"})
        response = self.client.get_json(f"{self.base_url}?{query}")
        return self.parse_schedule(response, expected_date=game_date)

    def completed_games(self, start_date: date, end_date: date) -> list[CompletedGameResult]:
        """Get every Final game's real final score for a date range.

        One request via startDate/endDate (verified live against
        statsapi.mlb.com on 2026-09-18) instead of one call per date -- this
        is exactly the batch-over-manual-loop rule the project requires for
        building a historical dataset.
        """

        query = urlencode(
            {
                "sportId": 1,
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "hydrate": "team,linescore",
            }
        )
        response = self.client.get_json(f"{self.base_url}?{query}")
        return self.parse_completed_games(response)

    def completed_games_batched(
        self, start_date: date, end_date: date, *, max_days_per_request: int = 180
    ) -> list[CompletedGameResult]:
        """Fetch a long completed-game history without API range truncation.

        The public schedule endpoint may return a partial response for a
        multi-year date range.  Fixed, non-overlapping chunks retain each raw
        response's own retrieval timestamp and avoid silently treating a
        partial history as sufficient for a daily E8 vector.
        """

        if end_date < start_date:
            raise ValueError("end_date cannot be earlier than start_date")
        if max_days_per_request < 1:
            raise ValueError("max_days_per_request must be positive")
        results: list[CompletedGameResult] = []
        cursor = start_date
        while cursor <= end_date:
            chunk_end = min(cursor + timedelta(days=max_days_per_request - 1), end_date)
            results.extend(self.completed_games(cursor, chunk_end))
            cursor = chunk_end + timedelta(days=1)
        # A game can be revised/suspended across source responses. Preserve
        # one identity only; duplicate game IDs would otherwise double-count
        # a team's history. The latest retrieval is the most current final
        # observation and remains point-in-time because it was retrieved
        # before the daily prediction timestamp.
        latest_by_game = {result.game_id: result for result in results}
        return sorted(latest_by_game.values(), key=lambda result: (result.start_time, result.game_id))

    @classmethod
    def parse_completed_games(cls, response: RetrievedJson) -> list[CompletedGameResult]:
        """Normalise a schedule+linescore payload into only the Final games.

        Games that are not yet Final (Scheduled, In Progress, Postponed, ...)
        are silently excluded -- a partial score for a live game must never
        be treated as a final result.
        """

        dates = response.payload.get("dates")
        if not isinstance(dates, list):
            raise ValueError("schedule response lacks a dates array")

        provenance = DataProvenance(
            source=cls.source_name,
            retrieved_at=response.retrieved_at,
            status=AvailabilityStatus.AVAILABLE,
            source_url=response.url,
        )
        results: list[CompletedGameResult] = []
        for schedule_day in dates:
            if not isinstance(schedule_day, dict):
                raise ValueError("schedule date record is invalid")
            for raw_game in schedule_day.get("games", []):
                if not isinstance(raw_game, dict):
                    raise ValueError("game record is invalid")
                status = raw_game.get("status", {})
                if not isinstance(status, dict) or status.get("detailedState") != "Final":
                    continue
                result = cls._parse_completed_game(raw_game, provenance)
                if result is not None:
                    results.append(result)
        return results

    @staticmethod
    def _parse_completed_game(
        raw_game: dict[str, Any], provenance: DataProvenance
    ) -> CompletedGameResult | None:
        teams = raw_game.get("teams")
        if not isinstance(teams, dict):
            raise ValueError("game record lacks teams")
        home = teams.get("home")
        away = teams.get("away")
        if not isinstance(home, dict) or not isinstance(away, dict):
            raise ValueError("game record lacks a valid home/away side")
        home_team = home.get("team")
        away_team = away.get("team")
        if not isinstance(home_team, dict) or not isinstance(away_team, dict):
            raise ValueError("game record lacks valid team identities")
        if home.get("score") is None or away.get("score") is None:
            # Marked Final but no score published yet -- treat as unusable
            # rather than guessing; extremely rare but has been observed for
            # suspended/completed-later games in the raw API.
            return None
        if not raw_game.get("gamePk"):
            raise ValueError("game record lacks gamePk")
        game_date_raw = raw_game.get("gameDate")
        if not game_date_raw:
            raise ValueError("game record lacks gameDate")
        start_time = datetime.fromisoformat(str(game_date_raw).replace("Z", "+00:00"))
        official_date_raw = raw_game.get("officialDate")
        official_date = date.fromisoformat(str(official_date_raw)) if official_date_raw else start_time.date()
        return CompletedGameResult(
            game_id=f"mlb:{raw_game['gamePk']}",
            official_date=official_date,
            start_time=start_time,
            home_team_id=str(home_team["id"]),
            home_team_name=str(home_team.get("name", "")),
            away_team_id=str(away_team["id"]),
            away_team_name=str(away_team.get("name", "")),
            home_runs=int(home["score"]),
            away_runs=int(away["score"]),
            provenance=provenance,
        )

    def probable_pitchers_on(self, game_date: date) -> list[ProbablePitcher]:
        """Get one ProbablePitcher record per team per game for a date.

        Returns an explicit NOT_YET_PUBLISHED record for a team when MLB has
        not posted a probable starter yet; it never omits the team.
        """

        query = urlencode(
            {"sportId": 1, "date": game_date.isoformat(), "hydrate": "probablePitcher"}
        )
        response = self.client.get_json(f"{self.base_url}?{query}")
        return self.parse_probable_pitchers(response)

    def lineups_for(self, game_id: str) -> GameLineups:
        """Get the confirmed batting order for one game, or its absence.

        Before MLB posts the official lineup this returns a GameLineups with
        status NOT_YET_PUBLISHED and empty slots; callers must not treat that
        as a projected or zero-strength lineup.
        """

        game_pk = _extract_game_pk(game_id)
        response = self.client.get_json(f"{self.game_url}/{game_pk}/boxscore")
        return self.parse_boxscore_lineups(response, game_id=game_id)

    def venue_location(self, venue_id: str) -> VenueLocation:
        """Get a venue's fixed coordinates, used to look up its weather."""

        response = self.client.get_json(f"{self.venue_url}/{venue_id}?hydrate=location")
        return self.parse_venue_location(response, venue_id=venue_id)

    def team_season_stats(self, team_id: str, team_name: str, season: str) -> TeamSeasonStats:
        """Get one team's raw season hitting and pitching aggregates.

        Returns raw provider numbers only (batting_avg, runs_scored, era, ...).
        Turning these into a normalised TeamRunProfile (offensive_index,
        run_prevention_index) against a league average is out of scope here —
        that is Fase 4 feature-store work with its own documented formula.
        """

        hitting_query = urlencode(
            {"stats": "season", "group": "hitting", "teamId": team_id, "season": season, "sportId": 1}
        )
        pitching_query = urlencode(
            {"stats": "season", "group": "pitching", "teamId": team_id, "season": season, "sportId": 1}
        )
        hitting_response = self.client.get_json(f"{self.stats_url}?{hitting_query}")
        pitching_response = self.client.get_json(f"{self.stats_url}?{pitching_query}")
        return self.parse_team_season_stats(
            hitting_response,
            pitching_response,
            team_id=team_id,
            team_name=team_name,
            season=season,
        )

    def league_average_runs_per_game(self, season: str) -> float:
        """Get the real league-wide runs-per-team-game rate for a season.

        Feeds mlb_kaizen.features.run_profile.compute_team_run_profile,
        which requires this as an explicit argument rather than a guessed
        constant. Computed as total runs scored by every MLB team divided by
        total team-games played, from one hitting-stats request covering
        every team (no teamId filter) rather than 30 individual calls.
        """

        query = urlencode({"stats": "season", "group": "hitting", "sportId": 1, "season": season, "limit": 30})
        response = self.client.get_json(f"{self.stats_url}?{query}")
        return self.parse_league_average_runs_per_game(response)

    @classmethod
    def parse_venue_location(cls, response: RetrievedJson, venue_id: str) -> VenueLocation:
        venues = response.payload.get("venues")
        if not isinstance(venues, list) or not venues:
            raise ValueError("venue response lacks a venues array")
        venue = venues[0]
        if not isinstance(venue, dict):
            raise ValueError("venue record is invalid")
        location = venue.get("location")
        if not isinstance(location, dict):
            raise ValueError("venue record lacks location")
        coordinates = location.get("defaultCoordinates")
        if not isinstance(coordinates, dict):
            raise ValueError("venue location lacks defaultCoordinates")
        latitude = coordinates.get("latitude")
        longitude = coordinates.get("longitude")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            raise ValueError("venue coordinates are missing or non-numeric")
        provenance = DataProvenance(
            source=cls.source_name,
            retrieved_at=response.retrieved_at,
            status=AvailabilityStatus.AVAILABLE,
            source_url=response.url,
        )
        return VenueLocation(
            venue_id=str(venue_id),
            latitude=float(latitude),
            longitude=float(longitude),
            provenance=provenance,
        )

    @classmethod
    def parse_team_season_stats(
        cls,
        hitting_response: RetrievedJson,
        pitching_response: RetrievedJson,
        *,
        team_id: str,
        team_name: str,
        season: str,
    ) -> TeamSeasonStats:
        hitting_stat = cls._first_stat_split(hitting_response, group="hitting")
        pitching_stat = cls._first_stat_split(pitching_response, group="pitching")
        provenance = DataProvenance(
            source=cls.source_name,
            retrieved_at=hitting_response.retrieved_at,
            status=AvailabilityStatus.AVAILABLE,
            source_url=hitting_response.url,
        )
        try:
            return TeamSeasonStats(
                team_id=str(team_id),
                team_name=team_name,
                season=str(season),
                games_played=int(hitting_stat["gamesPlayed"]),
                batting_avg=float(hitting_stat["avg"]),
                batting_obp=float(hitting_stat["obp"]),
                batting_slg=float(hitting_stat["slg"]),
                runs_scored=int(hitting_stat["runs"]),
                plate_appearances=int(hitting_stat["plateAppearances"]),
                pitching_era=float(pitching_stat["era"]),
                pitching_whip=float(pitching_stat["whip"]),
                innings_pitched=str(pitching_stat["inningsPitched"]),
                earned_runs=int(pitching_stat["earnedRuns"]),
                runs_allowed=int(pitching_stat["runs"]),
                provenance=provenance,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"team season stat response is missing an expected field: {exc}") from exc

    @staticmethod
    def _first_stat_split(response: RetrievedJson, *, group: str) -> dict[str, Any]:
        stats = response.payload.get("stats")
        if not isinstance(stats, list) or not stats:
            raise ValueError(f"{group} stats response lacks a stats array")
        splits = stats[0].get("splits") if isinstance(stats[0], dict) else None
        if not isinstance(splits, list) or not splits:
            raise ValueError(f"{group} stats response has no splits for this team/season")
        stat = splits[0].get("stat")
        if not isinstance(stat, dict):
            raise ValueError(f"{group} split lacks a stat object")
        return stat

    @classmethod
    def parse_league_average_runs_per_game(cls, response: RetrievedJson) -> float:
        """Sum runs and games across every team split into one real rate.

        Requires at least MINIMUM_EXPECTED_TEAMS distinct teams in the
        response rather than hardcoding exactly 30, so this fails loud on an
        obviously-truncated response (e.g. a dropped season filter) without
        breaking the day MLB adds an expansion team.
        """

        stats = response.payload.get("stats")
        if not isinstance(stats, list) or not stats:
            raise ValueError("league stats response lacks a stats array")
        splits = stats[0].get("splits") if isinstance(stats[0], dict) else None
        if not isinstance(splits, list):
            raise ValueError("league stats response has no splits array")
        if len(splits) < cls.minimum_expected_teams:
            raise ValueError(
                f"expected at least {cls.minimum_expected_teams} team splits for a "
                f"league-wide aggregate, got {len(splits)}"
            )

        total_runs = 0
        total_games = 0
        seen_team_ids: set[str] = set()
        for split in splits:
            if not isinstance(split, dict):
                raise ValueError("league split record is invalid")
            team = split.get("team")
            stat = split.get("stat")
            if not isinstance(team, dict) or not team.get("id"):
                raise ValueError("league split is missing a valid team identity")
            if not isinstance(stat, dict):
                raise ValueError("league split lacks a stat object")
            team_id = str(team["id"])
            if team_id in seen_team_ids:
                raise ValueError(
                    "league splits contain a duplicate team id — response is not one row per team"
                )
            seen_team_ids.add(team_id)
            try:
                total_runs += int(stat["runs"])
                total_games += int(stat["gamesPlayed"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"league split is missing an expected field: {exc}") from exc

        if total_games == 0:
            raise ValueError("league totals have zero games played")
        return total_runs / total_games

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

    @classmethod
    def parse_probable_pitchers(cls, response: RetrievedJson) -> list[ProbablePitcher]:
        """Normalise the probablePitcher hydration into one record per team."""

        dates = response.payload.get("dates")
        if not isinstance(dates, list):
            raise ValueError("schedule response lacks a dates array")

        provenance = DataProvenance(
            source=cls.source_name,
            retrieved_at=response.retrieved_at,
            status=AvailabilityStatus.AVAILABLE,
            source_url=response.url,
        )
        pitchers: list[ProbablePitcher] = []
        for schedule_day in dates:
            if not isinstance(schedule_day, dict):
                raise ValueError("schedule date record is invalid")
            for raw_game in schedule_day.get("games", []):
                if not isinstance(raw_game, dict):
                    raise ValueError("game record is invalid")
                teams = raw_game.get("teams")
                if not isinstance(teams, dict):
                    raise ValueError("game record lacks teams")
                game_id = f"mlb:{raw_game['gamePk']}"
                for side in ("home", "away"):
                    pitchers.append(cls._parse_probable_pitcher(teams.get(side), game_id, provenance))
        return pitchers

    @staticmethod
    def _parse_probable_pitcher(
        team_block: Any, game_id: str, provenance: DataProvenance
    ) -> ProbablePitcher:
        if not isinstance(team_block, dict):
            raise ValueError("game record lacks a valid team side")
        team = team_block.get("team")
        if not isinstance(team, dict) or not team.get("id"):
            raise ValueError("game record lacks a valid team identity")
        team_id = str(team["id"])
        probable = team_block.get("probablePitcher")
        if not isinstance(probable, dict) or not probable.get("id"):
            return ProbablePitcher(
                game_id=game_id, team_id=team_id, status=AvailabilityStatus.NOT_YET_PUBLISHED, provenance=provenance
            )
        name = probable.get("fullName")
        if not name:
            raise ValueError("probable pitcher record lacks fullName")
        return ProbablePitcher(
            game_id=game_id,
            team_id=team_id,
            status=AvailabilityStatus.PROJECTED,
            provenance=provenance,
            pitcher_id=str(probable["id"]),
            pitcher_name=str(name),
        )

    @classmethod
    def parse_boxscore_lineups(cls, response: RetrievedJson, game_id: str) -> GameLineups:
        """Normalise a boxscore payload into a confirmed lineup or its absence.

        The 'battingOrder' array MLB publishes at team level lists the nine
        starters in order; it is only present once the official lineup posts,
        which for most games is close to first pitch, not at schedule time.
        """

        teams = response.payload.get("teams")
        if not isinstance(teams, dict):
            raise ValueError("boxscore response lacks teams")

        provenance = DataProvenance(
            source=cls.source_name,
            retrieved_at=response.retrieved_at,
            status=AvailabilityStatus.AVAILABLE,
            source_url=response.url,
        )
        home_slots = cls._parse_lineup_side(teams.get("home"), game_id, provenance)
        away_slots = cls._parse_lineup_side(teams.get("away"), game_id, provenance)
        if home_slots and away_slots:
            return GameLineups(
                game_id=game_id,
                status=AvailabilityStatus.CONFIRMED,
                provenance=provenance,
                home_slots=home_slots,
                away_slots=away_slots,
            )
        return GameLineups(game_id=game_id, status=AvailabilityStatus.NOT_YET_PUBLISHED, provenance=provenance)

    @staticmethod
    def _parse_lineup_side(
        side: Any, game_id: str, provenance: DataProvenance
    ) -> tuple[LineupSlot, ...]:
        if not isinstance(side, dict):
            raise ValueError("boxscore response lacks a valid team side")
        batting_order = side.get("battingOrder")
        if not batting_order:
            return ()
        if not isinstance(batting_order, list):
            raise ValueError("boxscore battingOrder must be a list of player ids")
        players = side.get("players")
        if not isinstance(players, dict):
            raise ValueError("boxscore response lacks players for a posted lineup")
        team = side.get("team")
        team_id = str(team["id"]) if isinstance(team, dict) and team.get("id") else ""
        if not team_id:
            raise ValueError("boxscore response lacks a valid team identity")

        slots: list[LineupSlot] = []
        for order, player_id in enumerate(batting_order, start=1):
            entry = players.get(f"ID{player_id}")
            if not isinstance(entry, dict):
                raise ValueError("boxscore battingOrder references an unknown player")
            person = entry.get("person") or {}
            position = entry.get("position") or {}
            slots.append(
                LineupSlot(
                    game_id=game_id,
                    team_id=team_id,
                    batting_order=order,
                    player_id=str(player_id),
                    player_name=str(person.get("fullName", "")),
                    position=str(position.get("abbreviation", "")),
                    provenance=provenance,
                )
            )
        return tuple(slots)

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
            game_type=str(raw_game["gameType"]) if raw_game.get("gameType") else None,
            provenance=provenance,
        )
