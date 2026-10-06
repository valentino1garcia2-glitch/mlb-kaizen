"""Tests for append-only, point-in-time daily E3+E7+E8 feature vectors."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
import tempfile
import unittest

from mlb_kaizen.domain.models import AvailabilityStatus, DataProvenance, Game
from mlb_kaizen.features.e8_daily_snapshot import build_e8_daily_feature_snapshot
from mlb_kaizen.storage.database import KaizenDatabase
from mlb_kaizen.training.build_dataset import build_point_in_time_rows_with_opponent_strength_and_recent_form
from mlb_kaizen.training.inference_artifact import E8_FEATURE_NAMES

from .conftest import completed_game


class DailyE8SnapshotTests(unittest.TestCase):
    def _target_game(self, start: datetime) -> Game:
        return Game(
            game_id="mlb:target", official_date=start.date(),
            home_team_id="H", home_team_name="Home", away_team_id="A", away_team_name="Away",
            start_time=start,
            provenance=DataProvenance(
                source="test schedule", retrieved_at=start - timedelta(hours=1),
                status=AvailabilityStatus.AVAILABLE,
            ),
        )

    def _history(self, start: datetime):
        return [
            completed_game("mlb:1", start - timedelta(days=4), "H", "B", 5, 2),
            completed_game("mlb:2", start - timedelta(days=3), "A", "C", 1, 4),
            completed_game("mlb:3", start - timedelta(days=2), "B", "D", 3, 2),
            completed_game("mlb:4", start - timedelta(days=1), "C", "D", 2, 6),
        ]

    def test_daily_vector_matches_the_e8_training_formula_and_order(self) -> None:
        start = datetime(2026, 10, 1, 20, tzinfo=UTC)
        target = self._target_game(start)
        history = self._history(start)
        target_result = completed_game("mlb:target", start, "H", "A", 4, 3)
        expected = build_point_in_time_rows_with_opponent_strength_and_recent_form(
            [*history, target_result], minimum_prior_games=1,
            minimum_league_games_for_average=1, minimum_prior_matchups=1, recent_form_window=1,
        )[-1]

        actual = build_e8_daily_feature_snapshot(
            target, history, prediction_timestamp=start - timedelta(minutes=30),
            minimum_prior_games=1, minimum_league_games_for_average=1,
            minimum_prior_matchups=1, recent_form_window=1,
        )

        self.assertEqual(tuple(actual.features), E8_FEATURE_NAMES)
        for name in E8_FEATURE_NAMES:
            self.assertAlmostEqual(actual.features[name], expected.features[name])

    def test_rejects_post_prediction_source_and_target_result(self) -> None:
        start = datetime(2026, 10, 1, 20, tzinfo=UTC)
        target = self._target_game(start)
        history = self._history(start)
        late = history[0]
        late_provenance = DataProvenance(
            source="late", retrieved_at=start, status=AvailabilityStatus.AVAILABLE,
        )
        history[0] = replace(late, provenance=late_provenance)
        with self.assertRaisesRegex(ValueError, "retrieved after"):
            build_e8_daily_feature_snapshot(target, history, prediction_timestamp=start - timedelta(minutes=30), recent_form_window=1)
        with self.assertRaisesRegex(ValueError, "target game result"):
            build_e8_daily_feature_snapshot(
                target, [*self._history(start), completed_game("mlb:target", start - timedelta(hours=2), "H", "A")],
                prediction_timestamp=start - timedelta(minutes=30), recent_form_window=1,
            )

    def test_rejects_prediction_at_or_after_start(self) -> None:
        start = datetime(2026, 10, 1, 20, tzinfo=UTC)
        with self.assertRaisesRegex(ValueError, "before game start_time"):
            build_e8_daily_feature_snapshot(self._target_game(start), self._history(start), prediction_timestamp=start)

    def test_snapshot_is_stored_append_only(self) -> None:
        start = datetime(2026, 10, 1, 20, tzinfo=UTC)
        snapshot = build_e8_daily_feature_snapshot(
            self._target_game(start), self._history(start), prediction_timestamp=start - timedelta(minutes=30),
            minimum_prior_games=1, minimum_league_games_for_average=1,
            minimum_prior_matchups=1, recent_form_window=1,
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = KaizenDatabase(Path(temporary_directory) / "kaizen.sqlite3")
            database.initialise()
            database.store_inference_feature_snapshot(snapshot)
            database.store_inference_feature_snapshot(snapshot)
            self.assertEqual(database.inference_feature_snapshot_count(), 2)

