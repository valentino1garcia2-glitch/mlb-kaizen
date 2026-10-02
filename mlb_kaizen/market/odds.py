"""Explicit, tested transformations for betting prices and value.

All calculations use decimal odds internally. For decimal price ``d`` and
probability ``p``, expected value per unit risked is ``p * (d - 1) - (1 - p)``.
"""

from __future__ import annotations

from collections.abc import Mapping


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
