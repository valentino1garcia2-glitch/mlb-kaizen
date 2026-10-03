"""Adapter for the US National Weather Service public forecast API.

api.weather.gov is official and free, requires no key, and its response
shape is documented (https://www.weather.gov/documentation/services-web-api).
Coverage is US-only: a venue outside NWS coverage (e.g. Toronto) must resolve
to NOT_AVAILABLE, never to an invented reading.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from mlb_kaizen.data.http import CachedHttpClient, DataProviderError, RetrievedJson
from mlb_kaizen.domain.models import AvailabilityStatus, DataProvenance, GameWeather, VenueLocation


class NWSWeatherProvider:
    """Retrieve a point-in-time forecast for a venue, or its recorded absence."""

    points_url = "https://api.weather.gov/points"
    source_name = "NWS api.weather.gov public forecast endpoint"

    def __init__(self, client: CachedHttpClient) -> None:
        self.client = client

    def forecast_for(self, game_id: str, venue: VenueLocation, target_time: datetime) -> GameWeather:
        """Get the forecast period covering target_time, or NOT_AVAILABLE.

        Two-step lookup per the NWS API: coordinates resolve to a forecast
        office/grid via /points, which itself gives a forecast URL to fetch.
        """

        if target_time.tzinfo is None or target_time.utcoffset() is None:
            raise ValueError("target_time must be timezone-aware")

        try:
            points_response = self.client.get_json(
                f"{self.points_url}/{venue.latitude:.4f},{venue.longitude:.4f}"
            )
        except DataProviderError:
            return self._not_available(game_id, points_response_url=None)

        forecast_url = self._extract_forecast_url(points_response)
        if forecast_url is None:
            return self._not_available(game_id, points_response_url=points_response.url)

        try:
            forecast_response = self.client.get_json(forecast_url)
        except DataProviderError:
            return self._not_available(game_id, points_response_url=points_response.url)

        return self.parse_forecast(forecast_response, game_id=game_id, target_time=target_time)

    @classmethod
    def parse_forecast(
        cls, response: RetrievedJson, *, game_id: str, target_time: datetime
    ) -> GameWeather:
        properties = response.payload.get("properties")
        periods = properties.get("periods") if isinstance(properties, dict) else None
        if not isinstance(periods, list) or not periods:
            return cls._not_available(game_id, points_response_url=response.url)

        period = cls._matching_period(periods, target_time)
        if period is None:
            return cls._not_available(game_id, points_response_url=response.url)

        provenance = DataProvenance(
            source=cls.source_name,
            retrieved_at=response.retrieved_at,
            status=AvailabilityStatus.AVAILABLE,
            source_url=response.url,
        )
        temperature = period.get("temperature")
        short_forecast = period.get("shortForecast")
        if temperature is None and short_forecast is None:
            return cls._not_available(game_id, points_response_url=response.url)
        return GameWeather(
            game_id=game_id,
            status=AvailabilityStatus.AVAILABLE,
            provenance=provenance,
            temperature_fahrenheit=float(temperature) if temperature is not None else None,
            wind_speed_text=str(period.get("windSpeed")) if period.get("windSpeed") else None,
            wind_direction=str(period.get("windDirection")) if period.get("windDirection") else None,
            short_forecast=str(short_forecast) if short_forecast else None,
            forecast_period_start=datetime.fromisoformat(str(period["startTime"]))
            if period.get("startTime")
            else None,
        )

    @staticmethod
    def _matching_period(periods: list[Any], target_time: datetime) -> dict[str, Any] | None:
        """Return the period whose [startTime, endTime) contains target_time.

        NWS periods are typically 12h (day/night); falls back to the closest
        upcoming period if none exactly contains it (e.g. a game far enough
        out that only broader periods are published yet).
        """

        candidates: list[tuple[datetime, dict[str, Any]]] = []
        for period in periods:
            if not isinstance(period, dict):
                continue
            start_raw, end_raw = period.get("startTime"), period.get("endTime")
            if not start_raw or not end_raw:
                continue
            start = datetime.fromisoformat(str(start_raw))
            end = datetime.fromisoformat(str(end_raw))
            if start <= target_time < end:
                return period
            if start >= target_time:
                candidates.append((start, period))
        if not candidates:
            return None
        candidates.sort(key=lambda pair: pair[0])
        return candidates[0][1]

    @staticmethod
    def _extract_forecast_url(response: RetrievedJson) -> str | None:
        properties = response.payload.get("properties")
        if not isinstance(properties, dict):
            return None
        forecast_url = properties.get("forecast")
        return str(forecast_url) if forecast_url else None

    @classmethod
    def _not_available(cls, game_id: str, *, points_response_url: str | None) -> GameWeather:
        provenance = DataProvenance(
            source=cls.source_name,
            retrieved_at=_now(),
            status=AvailabilityStatus.NOT_AVAILABLE,
            source_url=points_response_url,
        )
        return GameWeather(game_id=game_id, status=AvailabilityStatus.NOT_AVAILABLE, provenance=provenance)


def _now() -> datetime:
    from datetime import UTC, datetime as _dt

    return _dt.now(UTC)
