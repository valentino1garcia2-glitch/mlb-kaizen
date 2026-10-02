"""Provider contracts that prevent external response formats leaking inward."""

from __future__ import annotations

from datetime import date
from typing import Protocol, Sequence

from mlb_kaizen.domain.models import Game


class ScheduleProvider(Protocol):
    """A source capable of retrieving an MLB schedule for one official date."""

    def games_on(self, game_date: date) -> Sequence[Game]:
        """Return provider-identified games or raise a verified provider error."""


class OddsProvider(Protocol):
    """Reserved contract for a licensed odds implementation."""

    def get_market_quotes(self, game_id: str) -> Sequence[object]:
        """Retrieve timestamped market quotes for a provider game identity."""
