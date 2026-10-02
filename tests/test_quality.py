from datetime import UTC, datetime
from pathlib import Path
import tempfile
import unittest

from mlb_kaizen.config.settings import Settings
from mlb_kaizen.domain.models import AnalysisContext, AvailabilityStatus, SignalStatus
from mlb_kaizen.validation.quality import QualityGate

from .conftest import away_profile, home_profile


class QualityTests(unittest.TestCase):
    def test_unknown_critical_data_blocks_a_signal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings = Settings(
                database_path=Path(temporary_directory) / "db.sqlite3",
                cache_dir=Path(temporary_directory) / "cache",
            )
            context = AnalysisContext(
                prediction_timestamp=datetime(2026, 9, 16, 12, tzinfo=UTC),
                information_state="T-6H",
                data_statuses={"starting_pitchers": AvailabilityStatus.UNKNOWN},
            )
            quality = QualityGate(settings).assess(context, [home_profile(), away_profile()], False, 0.01)
        self.assertIs(quality.status, SignalStatus.DATA_INCOMPLETE)
        self.assertTrue(any("starting_pitchers" in item for item in quality.blocking_reasons))
