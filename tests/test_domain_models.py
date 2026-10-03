import unittest

from .conftest import provenance
from mlb_kaizen.domain.models import (
    AvailabilityStatus,
    GameLineups,
    GameWeather,
    LineupSlot,
    ProbablePitcher,
    VenueLocation,
)


class ProbablePitcherTests(unittest.TestCase):
    def test_projected_status_requires_pitcher_identity(self) -> None:
        with self.assertRaises(ValueError):
            ProbablePitcher(
                game_id="mlb:1",
                team_id="10",
                status=AvailabilityStatus.PROJECTED,
                provenance=provenance(),
            )

    def test_not_yet_published_status_forbids_pitcher_identity(self) -> None:
        with self.assertRaises(ValueError):
            ProbablePitcher(
                game_id="mlb:1",
                team_id="10",
                status=AvailabilityStatus.NOT_YET_PUBLISHED,
                provenance=provenance(),
                pitcher_id="501",
                pitcher_name="Should not be here",
            )

    def test_not_yet_published_status_is_valid_without_identity(self) -> None:
        pitcher = ProbablePitcher(
            game_id="mlb:1",
            team_id="10",
            status=AvailabilityStatus.NOT_YET_PUBLISHED,
            provenance=provenance(),
        )
        self.assertIsNone(pitcher.pitcher_id)


class LineupSlotTests(unittest.TestCase):
    def test_batting_order_must_be_between_one_and_nine(self) -> None:
        with self.assertRaises(ValueError):
            LineupSlot(
                game_id="mlb:1",
                team_id="10",
                batting_order=10,
                player_id="501",
                player_name="Player",
                position="CF",
                provenance=provenance(),
            )


class GameLineupsTests(unittest.TestCase):
    def test_confirmed_status_requires_both_sides_populated(self) -> None:
        with self.assertRaises(ValueError):
            GameLineups(game_id="mlb:1", status=AvailabilityStatus.CONFIRMED, provenance=provenance())

    def test_not_yet_published_status_forbids_slots(self) -> None:
        slot = LineupSlot(
            game_id="mlb:1",
            team_id="10",
            batting_order=1,
            player_id="501",
            player_name="Player",
            position="CF",
            provenance=provenance(),
        )
        with self.assertRaises(ValueError):
            GameLineups(
                game_id="mlb:1",
                status=AvailabilityStatus.NOT_YET_PUBLISHED,
                provenance=provenance(),
                home_slots=(slot,),
            )


class VenueLocationTests(unittest.TestCase):
    def test_latitude_must_be_in_range(self) -> None:
        with self.assertRaises(ValueError):
            VenueLocation(venue_id="22", latitude=95.0, longitude=-118.0, provenance=provenance())

    def test_longitude_must_be_in_range(self) -> None:
        with self.assertRaises(ValueError):
            VenueLocation(venue_id="22", latitude=34.0, longitude=-185.0, provenance=provenance())


class GameWeatherTests(unittest.TestCase):
    def test_available_status_requires_a_forecast_reading(self) -> None:
        with self.assertRaises(ValueError):
            GameWeather(game_id="mlb:1", status=AvailabilityStatus.AVAILABLE, provenance=provenance())

    def test_not_available_status_forbids_forecast_fields(self) -> None:
        with self.assertRaises(ValueError):
            GameWeather(
                game_id="mlb:1",
                status=AvailabilityStatus.NOT_AVAILABLE,
                provenance=provenance(),
                temperature_fahrenheit=68.0,
            )

    def test_available_status_is_valid_with_a_reading(self) -> None:
        weather = GameWeather(
            game_id="mlb:1",
            status=AvailabilityStatus.AVAILABLE,
            provenance=provenance(),
            temperature_fahrenheit=68.0,
        )
        self.assertEqual(weather.temperature_fahrenheit, 68.0)
