from datetime import UTC, datetime
from pathlib import Path
import tempfile
import unittest

from mlb_kaizen.config.settings import Settings
from mlb_kaizen.domain.models import AnalysisContext, AvailabilityStatus, SignalStatus
from mlb_kaizen.reporting.text import render_analysis_report
from mlb_kaizen.services.analysis import AnalysisRequest, AnalysisService, MarketInput
from mlb_kaizen.services.trained_model import TrainedPoissonAnalysisModel
from mlb_kaizen.training.baseline import fit_poisson_baseline
from mlb_kaizen.evaluation.calibration import PlattCalibrator
from mlb_kaizen.training.dataset import HistoricalGameRow, MODEL_FEATURES
from mlb_kaizen.training.artifacts import ModelArtifactMetadata, save_model_artifact
from mlb_kaizen.storage.database import KaizenDatabase

from .conftest import away_profile, game, home_profile


class AnalysisServiceTests(unittest.TestCase):
    def test_trained_analysis_model_loads_only_a_poisson_artifact(self) -> None:
        rows = [HistoricalGameRow(f"g{i}", datetime(2025, 1, 1, tzinfo=UTC).date(), datetime(2025, 1, 1, 12, tzinfo=UTC), datetime(2025, 1, 1, 12, tzinfo=UTC), {name: 1.0 for name in MODEL_FEATURES}, 3 + i % 2, 2) for i in range(4)]
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "e3"
            save_model_artifact(fit_poisson_baseline(rows), path, ModelArtifactMetadata("test", "features", 4, "2025-01-01T12:00:00+00:00", "scikit-learn"))
            model, metadata = TrainedPoissonAnalysisModel.from_artifact(path)
        self.assertEqual(model.model.model_version, "MLB-KAIZEN-POISSON-RUNS-0.2.0")
        self.assertEqual(metadata.training_rows, 4)
    def test_trained_model_and_calibrator_are_used_without_claiming_validation(self) -> None:
        rows = [HistoricalGameRow(f"g{i}", datetime(2025, 1, 1, tzinfo=UTC).date(), datetime(2025, 1, 1, 12, tzinfo=UTC), datetime(2025, 1, 1, 12, tzinfo=UTC), {name: 1.0 for name in MODEL_FEATURES}, 3 + i % 2, 2) for i in range(4)]
        trained = TrainedPoissonAnalysisModel(fit_poisson_baseline(rows))
        calibrator = PlattCalibrator.fit([0.3, 0.4, 0.6, 0.7], [0, 0, 1, 1])
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings = Settings(Path(temporary_directory)/"db.sqlite3", Path(temporary_directory)/"cache", simulation_count=200, random_seed=3)
            request = AnalysisRequest(game(), home_profile(), away_profile(), AnalysisContext(datetime(2026, 9, 16, 12, tzinfo=UTC), "T-1H"), 4.40)
            result = AnalysisService(settings, run_model=trained, calibrator=calibrator).analyse(request)
        self.assertEqual(result.model_version, "MLB-KAIZEN-POISSON-RUNS-0.2.0")
        self.assertIsNotNone(result.calibrated_probability)
        self.assertEqual(result.model_validation_status.value, "experimental")
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
                league_runs_per_team=4.40,
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
