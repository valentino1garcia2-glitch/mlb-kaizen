"""SportsGameOdds adapter with a provider-independent market quote shape."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable
from urllib.parse import urlencode

from mlb_kaizen.data.http import CachedHttpClient, DataProviderError
from mlb_kaizen.market.odds import american_to_decimal


@dataclass(frozen=True, slots=True)
class MarketQuote:
    """One bookmaker price observed at a specific time."""

    game_id: str
    sportsbook: str
    market: str
    selection: str
    american_odds: float
    decimal_odds: float
    line: float | None
    captured_at: datetime
    source: str
    provider_event_id: str


class SportsGameOddsProvider:
    """Fetch MLB game markets from SportsGameOdds v2.

    The adapter intentionally normalises only the fields needed by KAIZEN's market
    layer. The API key is supplied by environment/configuration and never logged.
    """

    base_url = "https://api.sportsgameodds.com/v2/events"
    source_name = "sports_game_odds"
    source_version = "v2"

    def __init__(
        self,
        client: CachedHttpClient,
        api_key: str,
        bookmaker_ids: Iterable[str] = (),
    ) -> None:
        if not api_key.strip():
            raise ValueError("SportsGameOdds API key is required")
        self.client = client
        self.api_key = api_key.strip()
        self.bookmaker_ids = tuple(bookmaker_id.strip() for bookmaker_id in bookmaker_ids if bookmaker_id.strip())

    def get_market_quotes(self, game_id: str) -> tuple[MarketQuote, ...]:
        """Retrieve available full-game MLB markets for one provider event ID."""

        if not game_id.strip():
            raise ValueError("game_id is required")
        query = {
            "eventID": game_id,
            "leagueID": "MLB",
            "oddsAvailable": "true",
            "includeAltLines": "true",
            "includeOpposingOdds": "true",
        }
        retrieved = self.client.get_json(
            f"{self.base_url}?{urlencode(query)}",
            headers={"x-api-key": self.api_key},
        )
        return parse_sports_game_odds_response(game_id, retrieved.payload, retrieved.retrieved_at, self.bookmaker_ids)


def parse_sports_game_odds_response(
    game_id: str,
    payload: dict[str, Any],
    retrieved_at: datetime,
    bookmaker_ids: Iterable[str] = (),
) -> tuple[MarketQuote, ...]:
    """Parse a documented-looking SGO `/events` response without network access."""

    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("retrieved_at must be timezone-aware")
    if payload.get("success") is not True:
        raise DataProviderError(f"DATA NOT VERIFIED: provider response was not successful: {payload.get('error', 'unknown error')}")
    events = payload.get("data")
    if not isinstance(events, list):
        raise DataProviderError("DATA NOT VERIFIED: provider response data is not a list")

    selected_event = next((event for event in events if str(event.get("eventID", "")) == game_id), None)
    if selected_event is None:
        raise DataProviderError(f"DATA NOT VERIFIED: event {game_id} was not returned")

    event_odds = selected_event.get("odds")
    if not isinstance(event_odds, dict):
        raise DataProviderError("DATA NOT VERIFIED: event odds object is missing")

    requested_books = {value for value in bookmaker_ids if value}
    quotes: list[MarketQuote] = []
    for odd_id, odd in event_odds.items():
        if not isinstance(odd, dict):
            continue
        if str(odd.get("periodID", "")) != "game":
            continue
        bet_type = str(odd.get("betTypeID", ""))
        side = str(odd.get("sideID", ""))
        if bet_type not in {"ml", "sp", "ou"} or side not in {"home", "away", "over", "under"}:
            continue
        by_bookmaker = odd.get("byBookmaker")
        if not isinstance(by_bookmaker, dict):
            continue
        for sportsbook, book in by_bookmaker.items():
            if requested_books and sportsbook not in requested_books:
                continue
            if not isinstance(book, dict) or book.get("available") is False:
                continue
            odds_value = book.get("odds")
            if odds_value is None:
                continue
            try:
                american = float(str(odds_value).strip())
                decimal = american_to_decimal(american)
            except (TypeError, ValueError):
                continue
            captured_at = _parse_optional_timestamp(book.get("lastUpdatedAt"), retrieved_at)
            line = _line_for_market(bet_type, odd, book)
            market = {"ml": "moneyline", "sp": "run_line", "ou": "total"}[bet_type]
            quotes.append(
                MarketQuote(
                    game_id=game_id,
                    sportsbook=str(sportsbook),
                    market=market,
                    selection=side,
                    american_odds=american,
                    decimal_odds=decimal,
                    line=line,
                    captured_at=captured_at,
                    source="sports_game_odds",
                    provider_event_id=str(selected_event.get("eventID", game_id)),
                )
            )
    if not quotes:
        raise DataProviderError("DATA NOT VERIFIED: no supported available full-game MLB odds were parsed")
    return tuple(sorted(quotes, key=lambda quote: (quote.market, quote.selection, quote.sportsbook, quote.captured_at)))


def _line_for_market(bet_type: str, odd: dict[str, Any], book: dict[str, Any]) -> float | None:
    if bet_type == "ml":
        return None
    candidates = (book.get("spread"), book.get("overUnder"), book.get("total"), odd.get("spread"), odd.get("overUnder"))
    for candidate in candidates:
        if candidate is None or candidate == "":
            continue
        try:
            return float(str(candidate))
        except ValueError:
            continue
    return None


def _parse_optional_timestamp(value: Any, fallback: datetime) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is not None and parsed.utcoffset() is not None:
                return parsed.astimezone(UTC)
        except ValueError:
            pass
    return fallback
