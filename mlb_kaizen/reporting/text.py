"""Render practical Spanish reports for Analyst Mode."""

from __future__ import annotations

from mlb_kaizen.services.analysis import AnalysisResult


def _percentage(value: float | None) -> str:
    return "DATA NOT VERIFIED" if value is None else f"{value:.2%}"


def render_analysis_report(result: AnalysisResult) -> str:
    """Show calculation, data and model status independently, then machine-vs-market output."""

    projection = result.projection
    simulation = result.simulation
    market = result.market
    machine = result.machine_pick
    candidates = "\n".join(
        f"  {candidate.market}/{candidate.selection}"
        f" line={candidate.line if candidate.line is not None else '-'}"
        f" model={candidate.model_probability:.2%}"
        f" market={candidate.market_probability:.2%}"
        f" edge={candidate.edge:.2%}"
        f" EV={candidate.expected_value:.2%}"
        for candidate in market.candidates
    ) or "  DATA NOT VERIFIED / no priced market supplied"
    machine_text = (
        "NO QUALIFIED MARKET"
        if machine is None
        else f"{machine.market}/{machine.selection}"
        + (f" {machine.line:+g}" if machine.line is not None else "")
        + f" | edge={machine.edge:.2%} | EV={machine.expected_value:.2%} | status={machine.status}"
    )
    warnings = "\n".join(f"- {warning}" for warning in result.warnings)
    return f"""KAIZEN MLB — ANALYST MODE
==========================
GAME ID: {projection.game_id}
PREDICTION ID: {result.prediction_id or 'not persisted'}
MODEL: {result.model_version}
FEATURE SET: {result.feature_version}
MODE: {result.mode.value}
DATA TIMESTAMP: {result.data_timestamp.isoformat()}

STATUS
Calculation: {result.calculation_status.value.upper()}
Data quality: {result.data_quality_status.value.upper()} ({result.quality.data_quality:.0%})
Model validation: {result.model_validation_status.value.upper()}
Signal status: {result.quality.status.value.upper()}

MODEL PROJECTION
Home expected runs: {projection.home_expected_runs:.3f}
Away expected runs: {projection.away_expected_runs:.3f}
Projected total: {projection.expected_total_runs:.3f}
Home win probability: {result.raw_probability:.2%}
Away win probability: {simulation.away_win_probability:.2%}
Monte Carlo sampling error: ±{result.uncertainty:.2%}
Regulation tie proxy: {simulation.regulation_tie_probability:.2%}
Simulations / seed: {simulation.simulation_count:,} / {simulation.random_seed}

MARKET SNAPSHOT
Home implied probability: {_percentage(market.market_implied_home_probability)}
Home no-vig probability: {_percentage(market.no_vig_home_probability)}
Home raw model edge: {_percentage(market.raw_model_edge)}
Home preliminary EV: {_percentage(market.preliminary_raw_ev)}

MARKET CANDIDATES
{candidates}

MACHINE OUTPUT
{machine_text}

HUMAN INPUT
Registra tu pick con: `mlb-kaizen record-human-pick ...`

WARNINGS
{warnings}
"""
