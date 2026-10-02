from datetime import UTC, datetime
from pathlib import Path
import tempfile
import unittest

from mlb_kaizen.config.settings import Settings
from mlb_kaizen.domain.models import AnalysisContext, AvailabilityStatus, SignalStatus
from mlb_kaizen.reporting.text import render_analysis_report
from mlb_kaizen.services.analysis import AnalysisRequest, AnalysisService, MarketInput
from mlb_kaizen.storage.database import KaizenDatabase

from .conftest import away_profile, game, home_profile


class AnalysisServiceTests(unittest.TestCase):
    def test_model_persists_analysis_but_blocks_uncalibrated_signal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = KaizenDatabase(Path(temporary_directory) / "kaizen.sqlite3")
            settings = Settings(
                database_path=Path(temporary_directory) / "kaizen.sqlite3",
                cache_dir=Path(temporary_directory) / "cache",
                simulation_count=1_000,
                random_seed=3,
            )
            request = AnalysisRequest(
                game=game(),
                home_profile=home_profile(),
                away_profile=away_profile(),
                context=AnalysisContext(
                    prediction_timestamp=datetime(2026, 9, 16, 12, tzinfo=UTC),
                    information_state="T-1H",
                    data_statuses={
                        "starting_pitchers": AvailabilityStatus.CONFIRMED,
                        "lineups": AvailabilityStatus.PROJECTED,
                        "odds": AvailabilityStatus.AVAILABLE,
                    },
                ),
                market=MarketInput(home_decimal_odds=1.90, away_decimal_odds=2.00, total_line=8.5),
            )
            result = AnalysisService(settings, database=database).analyse(request, persist=True)
            report = render_analysis_report(result)
            count = database.prediction_count()
        self.assertIs(result.quality.status, SignalStatus.MODEL_UNCALIBRATED)
        self.assertEqual(count, 1)
        self.assertIn("MODEL_UNCALIBRATED", report)
