from datetime import UTC, datetime
from pathlib import Path
import tempfile
import unittest

from mlb_kaizen.storage.database import KaizenDatabase

from .conftest import game


class DatabaseTests(unittest.TestCase):
    def test_database_appends_game_and_prediction_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = KaizenDatabase(Path(temporary_directory) / "kaizen.sqlite3")
            database.initialise()
            snapshot_id = database.store_game_snapshot(game())
            prediction_id = database.store_prediction(
                game_id="mlb:1",
                prediction_timestamp=datetime(2026, 9, 16, 12, tzinfo=UTC),
                data_timestamp=datetime(2026, 9, 16, 11, tzinfo=UTC),
                model_version="model-test",
                feature_version="features-test",
                raw_probability=0.52,
                calibrated_probability=None,
                uncertainty=0.02,
                data_quality=0.9,
                model_input={"input": "test"},
                model_output={"output": "test"},
            )
            count = database.prediction_count()
        self.assertTrue(snapshot_id)
        self.assertTrue(prediction_id)
        self.assertEqual(count, 1)
