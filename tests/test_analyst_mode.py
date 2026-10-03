import unittest
from datetime import UTC, datetime
from pathlib import Path
import tempfile

from mlb_kaizen.config.settings import Settings
from mlb_kaizen.domain.models import AnalysisContext, AnalysisMode, AvailabilityStatus
from mlb_kaizen.services.analysis import AnalysisRequest, AnalysisService, MarketInput
from mlb_kaizen.reporting.text import render_analysis_report

from .conftest import away_profile, game, home_profile


class AnalystModeTests(unittest.TestCase):
    def request(self, mode=AnalysisMode.MANUAL):
        return AnalysisRequest(
            game=game(),
            home_profile=home_profile(),
            away_profile=away_profile(),
            context=AnalysisContext(
                prediction_timestamp=datetime(2026, 9, 16, 12, tzinfo=UTC),
                information_state="T-3H",
                data_statuses={
                    "starting_pitchers": AvailabilityStatus.PROJECTED,
                    "lineups": AvailabilityStatus.NOT_YET_PUBLISHED,
                    "odds": AvailabilityStatus.AVAILABLE,
                },
            ),
            league_runs_per_team=4.40,
            mode=mode,
            market=MarketInput(
                home_decimal_odds=2.0,
                away_decimal_odds=2.0,
                total_line=8.5,
                over_decimal_odds=1.91,
                under_decimal_odds=1.91,
                home_run_line=-1.5,
                home_run_line_decimal_odds=2.4,
                away_run_line_decimal_odds=1.58,
            ),
        )

    def test_manual_mode_still_calculates_and_returns_machine_pick(self):
        with tempfile.TemporaryDirectory() as td:
            settings = Settings(Path(td)/"db.sqlite3", Path(td)/"cache", simulation_count=2_000, random_seed=7)
            result = AnalysisService(settings).analyse(self.request())
        self.assertEqual(result.calculation_status.value, "ready")
        self.assertEqual(result.data_quality_status.value, "manual")
        self.assertEqual(result.model_validation_status.value, "experimental")
        self.assertTrue(result.market.candidates)
        self.assertIsNotNone(result.machine_pick)

    def test_report_does_not_hide_experimental_numbers(self):
        with tempfile.TemporaryDirectory() as td:
            settings = Settings(Path(td)/"db.sqlite3", Path(td)/"cache", simulation_count=1_000, random_seed=9)
            report = render_analysis_report(AnalysisService(settings).analyse(self.request()))
        self.assertIn("Calculation: READY", report)
        self.assertIn("Model validation: EXPERIMENTAL", report)
        self.assertIn("Home expected runs:", report)
        self.assertIn("MACHINE OUTPUT", report)
