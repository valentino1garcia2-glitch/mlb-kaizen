from datetime import UTC, date, datetime
import unittest

from mlb_kaizen.domain.models import (
    AnalysisMode,
    AvailabilityStatus,
    CompletedGameResult,
    DataProvenance,
    GameLineups,
    GameWeather,
    LineupSlot,
    PitcherGameLine,
    ProbablePitcher,
    TeamSeasonStats,
    VenueLocation,
)


def provenance() -> DataProvenance:
    return DataProvenance(
        source="recovery fixture",
        retrieved_at=datetime(2026, 9, 19, 12, tzinfo=UTC),
        status=AvailabilityStatus.AVAILABLE,
    )


class RecoveredDomainRecordTests(unittest.TestCase):
    def test_completed_result_and_pitcher_line_enforce_final_game_invariants(self) -> None:
        result = CompletedGameResult(
            game_id="mlb:1",
            official_date=date(2026, 9, 19),
            start_time=datetime(2026, 9, 19, 18, tzinfo=UTC),
            home_team_id="10",
            home_team_name="Home",
            away_team_id="20",
            away_team_name="Away",
            home_runs=4,
            away_runs=2,
            provenance=provenance(),
        )
        self.assertEqual(result.home_runs, 4)
        with self.assertRaises(ValueError):
            PitcherGameLine(
                "mlb:1", "p1", "Pitcher", "home", True, "5.0", 1, 2, 0, 4, 3, 0, provenance()
            )

    def test_probable_pitcher_and_lineups_retain_availability_meaning(self) -> None:
        with self.assertRaises(ValueError):
            ProbablePitcher("mlb:1", "10", AvailabilityStatus.CONFIRMED, provenance())
        not_published = ProbablePitcher(
            "mlb:1", "10", AvailabilityStatus.NOT_YET_PUBLISHED, provenance()
        )
        self.assertIs(not_published.status, AvailabilityStatus.NOT_YET_PUBLISHED)
        slot = LineupSlot("mlb:1", "10", 1, "p1", "Batter", "CF", provenance())
        with self.assertRaises(ValueError):
            GameLineups("mlb:1", AvailabilityStatus.AVAILABLE, provenance(), (slot,), ())

    def test_weather_venue_and_season_stats_validate_raw_inputs(self) -> None:
        venue = VenueLocation("v1", 29.0, -95.0, provenance())
        self.assertEqual(venue.venue_id, "v1")
        weather = GameWeather(
            "mlb:1", AvailabilityStatus.AVAILABLE, provenance(), temperature_fahrenheit=75.0
        )
        self.assertEqual(weather.temperature_fahrenheit, 75.0)
        with self.assertRaises(ValueError):
            TeamSeasonStats(
                "10", "Home", "2026", 1, 0.25, 0.32, 0.40, 4, 35, 3.5, 1.2, "9.0", 3, 2,
                provenance(),
            )

    def test_analysis_mode_is_explicit(self) -> None:
        self.assertEqual(AnalysisMode.SNAPSHOT.value, "snapshot")

