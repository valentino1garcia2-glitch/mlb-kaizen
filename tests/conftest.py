from datetime import UTC, date, datetime

from mlb_kaizen.domain.models import (
    AvailabilityStatus,
    CompletedGameResult,
    DataProvenance,
    Game,
    GameLineups,
    GameWeather,
    LineupSlot,
    ProbablePitcher,
    PitcherGameLine,
    TeamRunProfile,
    TeamSeasonStats,
)


def provenance() -> DataProvenance:
    return DataProvenance(
        source="test source",
        retrieved_at=datetime(2026, 9, 16, 12, tzinfo=UTC),
        status=AvailabilityStatus.AVAILABLE,
    )


def game() -> Game:
    return Game(
        game_id="mlb:1",
        official_date=date(2026, 9, 16),
        home_team_id="10",
        home_team_name="Home",
        away_team_id="20",
        away_team_name="Away",
        provenance=provenance(),
    )


def home_profile() -> TeamRunProfile:
    return TeamRunProfile("10", "Home", 1.10, 0.90, 400, 0.90, provenance())


def away_profile() -> TeamRunProfile:
    return TeamRunProfile("20", "Away", 0.95, 1.05, 400, 0.90, provenance())


def probable_pitcher() -> ProbablePitcher:
    return ProbablePitcher(
        game_id="mlb:1",
        team_id="10",
        status=AvailabilityStatus.PROJECTED,
        provenance=provenance(),
        pitcher_id="501",
        pitcher_name="Test Pitcher",
    )


def confirmed_lineups() -> GameLineups:
    home_slot = LineupSlot(
        game_id="mlb:1",
        team_id="10",
        batting_order=1,
        player_id="501",
        player_name="Home Leadoff",
        position="CF",
        provenance=provenance(),
    )
    away_slot = LineupSlot(
        game_id="mlb:1",
        team_id="20",
        batting_order=1,
        player_id="601",
        player_name="Away Leadoff",
        position="SS",
        provenance=provenance(),
    )
    return GameLineups(
        game_id="mlb:1",
        status=AvailabilityStatus.CONFIRMED,
        provenance=provenance(),
        home_slots=(home_slot,),
        away_slots=(away_slot,),
    )


def not_yet_published_lineups() -> GameLineups:
    return GameLineups(game_id="mlb:1", status=AvailabilityStatus.NOT_YET_PUBLISHED, provenance=provenance())


def available_weather() -> GameWeather:
    return GameWeather(
        game_id="mlb:1",
        status=AvailabilityStatus.AVAILABLE,
        provenance=provenance(),
        temperature_fahrenheit=68.0,
        wind_speed_text="5 mph",
        wind_direction="NW",
        short_forecast="Sunny",
    )


def not_available_weather() -> GameWeather:
    return GameWeather(game_id="mlb:1", status=AvailabilityStatus.NOT_AVAILABLE, provenance=provenance())


def team_season_stats() -> TeamSeasonStats:
    return TeamSeasonStats(
        team_id="147",
        team_name="New York Yankees",
        season="2026",
        games_played=150,
        batting_avg=0.251,
        batting_obp=0.330,
        batting_slg=0.420,
        runs_scored=720,
        plate_appearances=5800,
        pitching_era=3.85,
        pitching_whip=1.21,
        innings_pitched="1345.0",
        earned_runs=575,
        runs_allowed=620,
        provenance=provenance(),
    )


def completed_game(
    game_id: str = "mlb:1",
    start_time: datetime | None = None,
    home_team_id: str = "10",
    away_team_id: str = "20",
    home_runs: int = 4,
    away_runs: int = 2,
) -> CompletedGameResult:
    return CompletedGameResult(
        game_id=game_id,
        official_date=(start_time or datetime(2025, 7, 4, 18, tzinfo=UTC)).date(),
        start_time=start_time or datetime(2025, 7, 4, 18, tzinfo=UTC),
        home_team_id=home_team_id,
        home_team_name=f"Home {home_team_id}",
        away_team_id=away_team_id,
        away_team_name=f"Away {away_team_id}",
        home_runs=home_runs,
        away_runs=away_runs,
        provenance=provenance(),
    )


def starter_line(
    game_id: str = "mlb:1",
    pitcher_id: str = "501",
    side: str = "home",
    earned_runs: int = 2,
    runs_allowed: int | None = None,
    innings_pitched: str = "6.0",
) -> PitcherGameLine:
    return PitcherGameLine(
        game_id=game_id,
        pitcher_id=pitcher_id,
        pitcher_name=f"Pitcher {pitcher_id}",
        side=side,
        innings_pitched=innings_pitched,
        runs_allowed=earned_runs if runs_allowed is None else runs_allowed,
        earned_runs=earned_runs,
        is_actual_starter=True,
        provenance=provenance(),
    )
