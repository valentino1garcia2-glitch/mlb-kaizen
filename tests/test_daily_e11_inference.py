"""End-to-end unit test for the live-capture -> snapshot -> E11 bridge."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from mlb_kaizen.domain.models import AvailabilityStatus, DataProvenance, Game
from mlb_kaizen.interface.cli import _run_daily_e11_inference
from mlb_kaizen.storage.database import KaizenDatabase

from .conftest import completed_game


class _Provider:
    def __init__(self, game, history):
        self.game = game
        self.history = history

    def games_on(self, game_date):
        return [self.game]

    def completed_games(self, start_date, end_date):
        return self.history

    def completed_games_batched(self, start_date, end_date):
        return self.history


class DailyE11InferenceTests(unittest.TestCase):
    def _inputs(self):
        start = datetime(2026, 10, 20, 20, tzinfo=UTC)
        provenance = DataProvenance(
            source="test schedule", retrieved_at=start - timedelta(hours=1),
            status=AvailabilityStatus.AVAILABLE,
        )
        game = Game(
            game_id="mlb:target", official_date=start.date(), start_time=start,
            home_team_id="H", home_team_name="Home", away_team_id="A", away_team_name="Away",
            provenance=provenance,
        )
        history = []
        for index in range(16):
            day = start - timedelta(days=40 - index)
            history.append(completed_game(f"mlb:h{index}", day, "H", "B", 4 + index % 2, 2))
            history.append(completed_game(f"mlb:a{index}", day + timedelta(hours=1), "A", "C", 3, 2 + index % 2))
        return game, history, start - timedelta(minutes=30)

    def test_live_capture_persists_snapshot_and_calibrated_prediction(self) -> None:
        game, history, prediction_timestamp = self._inputs()
        fake_prediction = SimpleNamespace(
            raw_home_win_probability=0.51,
            calibrated_home_win_probability=0.53,
            run_prediction=SimpleNamespace(home_expected_runs=4.3, away_expected_runs=3.9),
        )
        fake_artifact = SimpleNamespace(predict=lambda features: fake_prediction)
        fake_metadata = SimpleNamespace(model_version="test-e11", experiment_id="E3+E7+E8+E11")
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = KaizenDatabase(Path(temporary_directory) / "kaizen.sqlite3")
            with patch("mlb_kaizen.interface.cli.load_e11_inference_artifact", return_value=(fake_artifact, fake_metadata)):
                result = _run_daily_e11_inference(
                    provider=_Provider(game, history), database=database,
                    game_date=date(2026, 10, 20), game_id="mlb:target",
                    history_start=date(2022, 3, 1), artifact_path=Path("trusted/e11"),
                    prediction_timestamp=prediction_timestamp,
                )
            self.assertEqual(database.inference_feature_snapshot_count(), 1)
            self.assertEqual(database.prediction_count(), 1)
        self.assertEqual(result["status"], "EXPERIMENTAL_PREGAME_PREDICTION_SAVED")
        self.assertEqual(result["calibrated_home_win_probability"], 0.53)

    def test_rejects_a_game_not_in_the_live_schedule(self) -> None:
        game, history, prediction_timestamp = self._inputs()
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = KaizenDatabase(Path(temporary_directory) / "kaizen.sqlite3")
            with self.assertRaisesRegex(ValueError, "not present"):
                _run_daily_e11_inference(
                    provider=_Provider(game, history), database=database,
                    game_date=date(2026, 10, 20), game_id="mlb:missing",
                    history_start=date(2022, 3, 1), artifact_path=Path("trusted/e11"),
                    prediction_timestamp=prediction_timestamp,
                )

    def test_default_prediction_time_is_captured_after_sources(self) -> None:
        now = datetime.now(UTC)
        start = now + timedelta(days=1)
        game = Game(
            game_id="mlb:future", official_date=start.date(), start_time=start,
            home_team_id="H", home_team_name="Home", away_team_id="A", away_team_name="Away",
            provenance=DataProvenance(
                source="test schedule", retrieved_at=now - timedelta(minutes=2),
                status=AvailabilityStatus.AVAILABLE,
            ),
        )
        _, history, _ = self._inputs()
        fake_prediction = SimpleNamespace(
            raw_home_win_probability=0.51, calibrated_home_win_probability=0.53,
            run_prediction=SimpleNamespace(home_expected_runs=4.3, away_expected_runs=3.9),
        )
        artifact = SimpleNamespace(predict=lambda features: fake_prediction)
        metadata = SimpleNamespace(model_version="test-e11", experiment_id="E3+E7+E8+E11")
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = KaizenDatabase(Path(temporary_directory) / "kaizen.sqlite3")
            with patch("mlb_kaizen.interface.cli.load_e11_inference_artifact", return_value=(artifact, metadata)):
                result = _run_daily_e11_inference(
                    provider=_Provider(game, history), database=database,
                    game_date=start.date(), game_id="mlb:future", history_start=date(2022, 3, 1),
                    artifact_path=Path("trusted/e11"),
                )
        self.assertEqual(result["status"], "EXPERIMENTAL_PREGAME_PREDICTION_SAVED")
