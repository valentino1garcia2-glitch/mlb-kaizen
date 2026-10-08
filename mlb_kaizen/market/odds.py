"""Explicit, tested transformations for betting prices and value.

All calculations use decimal odds internally. For decimal price ``d`` and
probability ``p``, expected value per unit risked is ``p * (d - 1) - (1 - p)``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime


_TWO_SIDED_MARKET_SELECTIONS = {
    "moneyline": frozenset(("home", "away")),
    "total": frozenset(("over", "under")),
    "run_line": frozenset(("home", "away")),
}


@dataclass(frozen=True, slots=True)
class NoVigMarketSnapshot:
    """One unambiguous two-sided bookmaker observation with vig removed."""

    sportsbook: str
    market: str
    line: float | None
    observed_at: datetime
    probabilities: Mapping[str, float]


def _validate_probability(probability: float) -> None:
    if not 0 <= probability <= 1:
        raise ValueError("probability must be in [0, 1]")


def american_to_decimal(american_odds: float) -> float:
    """Convert non-zero American odds to decimal odds."""

    if american_odds == 0:
        raise ValueError("American odds cannot be zero")
    return 1 + (american_odds / 100 if american_odds > 0 else 100 / abs(american_odds))


def decimal_to_implied_probability(decimal_odds: float) -> float:
    """Return gross implied probability before removing bookmaker margin."""

    if decimal_odds <= 1:
        raise ValueError("decimal odds must exceed 1 for a positive-return market")
    return 1 / decimal_odds


def proportional_no_vig(decimal_prices: Mapping[str, float]) -> dict[str, float]:
    """Remove vig by proportional normalisation.

    This method assumes each gross implied probability is inflated by the same
    multiplicative factor. The method is labelled because it is not equivalent to
    Shin, power or other devigging methods.
    """

    if len(decimal_prices) < 2:
        raise ValueError("at least two market outcomes are required for no-vig pricing")
    implied = {selection: decimal_to_implied_probability(price) for selection, price in decimal_prices.items()}
    overround = sum(implied.values())
    if overround <= 0:
        raise ValueError("invalid market overround")
    return {selection: probability / overround for selection, probability in implied.items()}


def latest_complete_no_vig_snapshot(
    quotes: list[Mapping[str, object]] | tuple[Mapping[str, object], ...], *, market: str
) -> NoVigMarketSnapshot | None:
    """Return the newest exact-time, two-sided market reference, or ``None``.

    Quotes are intentionally not mixed across observation times, sportsbooks or
    lines.  A complete pair proves only what that bookmaker implied at that
    instant after proportional vig removal; it is not a model prediction.
    """

    expected_selections = _TWO_SIDED_MARKET_SELECTIONS.get(market)
    if expected_selections is None:
        raise ValueError(f"unsupported two-sided market: {market!r}")

    grouped: dict[tuple[str, float | None, datetime], list[Mapping[str, object]]] = {}
    for quote in quotes:
        if quote.get("market") != market:
            continue
        observed_at_raw = quote.get("captured_at")
        if not isinstance(observed_at_raw, str):
            continue
        try:
            observed_at = datetime.fromisoformat(observed_at_raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            continue
        sportsbook = quote.get("sportsbook")
        if not isinstance(sportsbook, str) or not sportsbook:
            continue
        raw_line = quote.get("line")
        try:
            line = float(raw_line) if raw_line is not None else None
        except (TypeError, ValueError):
            continue
        grouped.setdefault((sportsbook, line, observed_at), []).append(quote)

    complete: list[NoVigMarketSnapshot] = []
    for (sportsbook, line, observed_at), group in grouped.items():
        selections = [quote.get("selection") for quote in group]
        if len(group) != len(expected_selections) or frozenset(selections) != expected_selections:
            continue
        try:
            decimal_prices = {
                str(quote["selection"]): float(quote["decimal_odds"])
                for quote in group
            }
            probabilities = proportional_no_vig(decimal_prices)
        except (KeyError, TypeError, ValueError):
            continue
        complete.append(NoVigMarketSnapshot(
            sportsbook=sportsbook,
            market=market,
            line=line,
            observed_at=observed_at,
            probabilities=probabilities,
        ))

    return max(complete, key=lambda snapshot: snapshot.observed_at) if complete else None


def edge(model_probability: float, market_probability: float) -> float:
    """Return model minus market probability, in percentage-point units as a decimal."""

    _validate_probability(model_probability)
    _validate_probability(market_probability)
    return model_probability - market_probability


def expected_value_per_unit(probability: float, decimal_odds: float) -> float:
    """Expected net profit from risking one unit at decimal odds."""

    _validate_probability(probability)
    if decimal_odds <= 1:
        raise ValueError("decimal odds must exceed 1")
    return probability * (decimal_odds - 1) - (1 - probability)


def fractional_kelly(probability: float, decimal_odds: float, fraction: float = 0.25) -> float:
    """Return a non-negative fractional-Kelly bankroll fraction, capped only at 100%."""

    _validate_probability(probability)
    if decimal_odds <= 1:
        raise ValueError("decimal odds must exceed 1")
    if not 0 < fraction <= 1:
        raise ValueError("fraction must be in (0, 1]")
    profit_multiple = decimal_odds - 1
    full_kelly = (probability * profit_multiple - (1 - probability)) / profit_multiple
    return max(0.0, min(1.0, full_kelly * fraction))


def expected_value_per_unit_with_push(
    win_probability: float, push_probability: float, decimal_odds: float
) -> float:
    """Expected net profit per unit when pushes return the stake."""

    _validate_probability(win_probability)
    _validate_probability(push_probability)
    if win_probability + push_probability > 1 + 1e-12:
        raise ValueError("win and push probabilities cannot exceed one")
    if decimal_odds <= 1:
        raise ValueError("decimal odds must exceed 1")
    loss_probability = max(0.0, 1.0 - win_probability - push_probability)
    return win_probability * (decimal_odds - 1) - loss_probability
