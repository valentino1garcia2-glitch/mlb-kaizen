"""Render a concise Spanish report without overstating a model estimate."""

from __future__ import annotations

from mlb_kaizen.services.analysis import AnalysisResult


def _percentage(value: float | None) -> str:
    return "DATA NOT VERIFIED" if value is None else f"{value:.2%}"


def render_analysis_report(result: AnalysisResult) -> str:
    """Create a text report that explicitly labels estimates and unavailable data."""

    projection = result.projection
    simulation = result.simulation
    market = result.market
    warnings = "\n".join(f"- {warning}" for warning in result.warnings)
    return f"""KAIZEN MLB QUANT ENGINE
=======================
MODEL: {result.model_version}
FEATURE SET: {result.feature_version}
DATA TIMESTAMP: {result.data_timestamp.isoformat()}

MODEL ESTIMATE (baseline, not calibrated)
Home expected runs: {projection.home_expected_runs:.3f}
Away expected runs: {projection.away_expected_runs:.3f}
Projected total: {projection.expected_total_runs:.3f}
Home win probability: {result.raw_probability:.2%}
Monte Carlo sampling error: ±{result.uncertainty:.2%}
Regulation tie proxy: {simulation.regulation_tie_probability:.2%}
Simulations / seed: {simulation.simulation_count:,} / {simulation.random_seed}

MARKET
Home implied probability: {_percentage(market.market_implied_home_probability)}
Home no-vig probability (proportional): {_percentage(market.no_vig_home_probability)}
Raw model edge: {_percentage(market.raw_model_edge)}
Preliminary EV using raw probability: {_percentage(market.preliminary_raw_ev)}

FINAL STATUS: {result.quality.status.value.upper()}
DATA QUALITY: {result.quality.data_quality:.0%}
WARNINGS
{warnings}
"""
