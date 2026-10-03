"""Small self-contained HTML reports for the analyst workflow."""

from __future__ import annotations

import html

from mlb_kaizen.services.analysis import AnalysisResult
from mlb_kaizen.tracking.human_machine import leaderboard


def render_analysis_html(result: AnalysisResult) -> str:
    p = result.projection
    m = result.market
    pick = result.machine_pick
    candidates = "".join(
        f"<tr><td>{html.escape(c.market)}</td><td>{html.escape(c.selection)}</td><td>{'' if c.line is None else c.line}</td>"
        f"<td>{c.model_probability:.2%}</td><td>{c.market_probability:.2%}</td><td>{c.edge:.2%}</td><td>{c.expected_value:.2%}</td></tr>"
        for c in m.candidates
    )
    machine = "NO BET / SIN MERCADO VÁLIDO" if pick is None else (
        f"{html.escape(pick.market)} — {html.escape(pick.selection)}"
        + (f" {pick.line:+g}" if pick.line is not None else "")
    )
    return f"""<!doctype html>
<html lang="es"><meta charset="utf-8"><title>MLB KAIZEN Analysis</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem}}table{{border-collapse:collapse;width:100%}}th,td{{padding:.45rem;border:1px solid #ddd;text-align:right}}th:first-child,td:first-child,td:nth-child(2){{text-align:left}}.status{{padding:.2rem .5rem;border:1px solid #aaa;border-radius:.3rem}}</style>
<h1>MLB KAIZEN — Análisis</h1>
<p><b>Modelo:</b> {html.escape(result.model_version)} &nbsp; <b>Features:</b> {html.escape(result.feature_version)}</p>
<p><b>Cálculo:</b> {result.calculation_status.value} &nbsp; <b>Datos:</b> {result.data_quality_status.value} &nbsp; <b>Modelo:</b> {result.model_validation_status.value}</p>
<h2>Proyección</h2>
<p>Home: {p.home_expected_runs:.3f} &nbsp; Away: {p.away_expected_runs:.3f} &nbsp; Total: {p.expected_total_runs:.3f}</p>
<p>Home win: {result.raw_probability:.2%} &nbsp; Error Monte Carlo: ±{result.uncertainty:.2%}</p>
<h2>Mercado vs modelo</h2>
<table><tr><th>Mercado</th><th>Selección</th><th>Línea</th><th>Modelo</th><th>Mercado</th><th>Edge</th><th>EV</th></tr>{candidates}</table>
<h2>Máquina</h2><p class="status">{machine}</p>
<p><b>Estado:</b> {"preliminary / experimental" if pick else "sin oportunidad que supere los umbrales"}</p>
<h2>Advertencias</h2><ul>{''.join(f'<li>{html.escape(w)}</li>' for w in result.warnings)}</ul>
</html>"""


def render_leaderboard_html(rows: list[dict]) -> str:
    summary = leaderboard(rows)
    def pct(value): return "DATA NOT VERIFIED" if value is None else f"{value:.2%}"
    body = "".join(
        f"<tr><td>{html.escape(str(row['game_id']))}</td><td>{html.escape(str(row.get('input_mode','')))}</td>"
        f"<td>{html.escape(str(row['machine_outcome']['status']))}</td><td>{row['machine_outcome']['correct']}</td>"
        f"<td>{html.escape(str(row['human_outcome']['status']))}</td><td>{row['human_outcome']['correct']}</td></tr>"
        for row in summary['rows']
    )
    machine_width = 0 if summary['machine_accuracy'] is None else summary['machine_accuracy'] * 100
    human_width = 0 if summary['human_accuracy'] is None else summary['human_accuracy'] * 100
    return f"""<!doctype html><html lang='es'><meta charset='utf-8'><title>MLB KAIZEN Human vs Machine</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:.4rem}}.bar{{height:1.2rem;background:#ddd;margin:.3rem 0}}.fill{{height:100%;background:#555}}</style>
<h1>Human vs Machine</h1>
<p>Máquina: {summary['machine_correct']}/{summary['machine_settled']} ({pct(summary['machine_accuracy'])})</p>
<div class='bar'><div class='fill' style='width:{machine_width:.1f}%'></div></div>
<p>Humano: {summary['human_correct']}/{summary['human_settled']} ({pct(summary['human_accuracy'])}) &nbsp; PnL realizado (con cuotas disponibles): {('DATA NOT VERIFIED' if summary['human_pnl'] is None else f"{summary['human_pnl']:.2f}u")}</p>
<div class='bar'><div class='fill' style='width:{human_width:.1f}%'></div></div>
<table><tr><th>Juego</th><th>Modo</th><th>Máquina estado</th><th>Máquina acierto</th><th>Humano estado</th><th>Humano acierto</th></tr>{body}</table></html>"""
