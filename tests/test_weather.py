from datetime import UTC, datetime
import unittest

from mlb_kaizen.data.http import RetrievedJson
from mlb_kaizen.data.weather import NWSWeatherProvider
from mlb_kaizen.domain.models import AvailabilityStatus


class NWSWeatherTests(unittest.TestCase):
    def test_forecast_picks_the_period_covering_target_time(self) -> None:
        response = RetrievedJson(
            payload={
                "properties": {
                    "periods": [
                        {
                            "number": 1,
                            "startTime": "2026-09-17T06:00:00-04:00",
                            "endTime": "2026-09-17T18:00:00-04:00",
                            "temperature": 68,
                            "windSpeed": "5 mph",
                            "windDirection": "NW",
                            "shortForecast": "Sunny",
                        },
                        {
                            "number": 2,
                            "startTime": "2026-09-17T18:00:00-04:00",
                            "endTime": "2026-09-18T06:00:00-04:00",
                            "temperature": 61,
                            "windSpeed": "8 mph",
                            "windDirection": "N",
                            "shortForecast": "Clear",
                        },
                    ]
                }
            },
            url="https://api.weather.gov/gridpoints/OKX/33,36/forecast",
            retrieved_at=datetime(2026, 9, 17, 12, tzinfo=UTC),
            from_cache=False,
        )
        target = datetime.fromisoformat("2026-09-17T19:10:00-04:00")
        weather = NWSWeatherProvider.parse_forecast(response, game_id="mlb:123", target_time=target)
        self.assertEqual(weather.status, AvailabilityStatus.AVAILABLE)
        self.assertEqual(weather.temperature_fahrenheit, 61.0)
        self.assertEqual(weather.short_forecast, "Clear")
        self.assertEqual(weather.wind_direction, "N")

    def test_forecast_is_not_available_when_periods_are_missing(self) -> None:
        response = RetrievedJson(
            payload={"properties": {}},
            url="https://api.weather.gov/gridpoints/XXX/0,0/forecast",
            retrieved_at=datetime(2026, 9, 17, 12, tzinfo=UTC),
            from_cache=False,
        )
        target = datetime.fromisoformat("2026-09-17T19:10:00-04:00")
        weather = NWSWeatherProvider.parse_forecast(response, game_id="mlb:123", target_time=target)
        self.assertEqual(weather.status, AvailabilityStatus.NOT_AVAILABLE)
        self.assertIsNone(weather.temperature_fahrenheit)

    def test_extract_forecast_url_matches_documented_points_response_shape(self) -> None:
        """Fixture from a real api.weather.gov /points response shown in NWS's
        own gridpoint documentation (weather-gov.github.io/api/gridpoints,
        checked 2026-09-17): gridId "LOX", gridX 142, gridY 16. This session
        could not get a literal live fetch of api.weather.gov past the tool's
        URL-allowlist restriction (only URLs that are themselves a search
        result's link can be fetched, and a raw JSON API endpoint rarely is
        one) — this is a documented real response, not a fetch performed this
        session. Confirms properties.forecast is the field parse_forecast's
        caller (forecast_for) must follow next."""

        response = RetrievedJson(
            payload={
                "properties": {
                    "gridId": "LOX",
                    "gridX": 142,
                    "gridY": 16,
                    "forecast": "https://api.weather.gov/gridpoints/LOX/142,16/forecast",
                    "forecastHourly": "https://api.weather.gov/gridpoints/LOX/142,16/forecast/hourly",
                }
            },
            url="https://api.weather.gov/points/34.0522,-118.2437",
            retrieved_at=datetime(2026, 9, 17, 12, tzinfo=UTC),
            from_cache=False,
        )
        forecast_url = NWSWeatherProvider._extract_forecast_url(response)
        self.assertEqual(forecast_url, "https://api.weather.gov/gridpoints/LOX/142,16/forecast")


if __name__ == "__main__":
    unittest.main()
