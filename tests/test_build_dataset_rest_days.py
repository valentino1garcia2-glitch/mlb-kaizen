"""Tests for E9's prior-only rest-days features."""

from datetime import UTC, datetime
import unittest

from .conftest import completed_game
from mlb_kaizen.training.build_dataset import (
    REST_DAYS_FORMULA_VERSION,
    build_point_in_time_rows_with_opponent_strength_recent_form_and_rest_days,
)


def _game(game_id: str, day: int, home: str, away: str, home_runs: int = 4, away_runs: int = 4):
    return completed_game(
        game_id=game_id,
        start_time=datetime(2025, 7, day, 18, tzinfo=UTC),
        home_team_id=home,
        away_team_id=away,
        home_runs=home_runs,
        away_runs=away_runs,
    )


class RestDaysRowsTests(unittest.TestCase):
    def _rows(self, games):
        return build_point_in_time_rows_with_opponent_strength_recent_form_and_rest_days(
            games,
            minimum_prior_games=1,
            minimum_league_games_for_average=2,
            minimum_prior_matchups=1,
            recent_form_window=1,
        )

    def test_emits_known_rest_days_and_versions_contract(self) -> None:
        self.assertEqual(REST_DAYS_FORMULA_VERSION, "rest_days_formula_v1")
        rows = self._rows([
            _game("mlb:1", 1, "A", "B"),
            _game("mlb:2", 1, "C", "D"),
            _game("mlb:3", 3, "A", "C"),
        ])
        row = {item.game_id: item for item in rows}["mlb:3"]
        self.assertEqual(row.features["home_rest_days"], 1.0)
        self.assertEqual(row.features["away_rest_days"], 1.0)

    def test_next_day_and_same_day_are_zero_rest(self) -> None:
        rows = self._rows([
            _game("mlb:1", 1, "A", "B"),
            _game("mlb:2", 1, "C", "D"),
            _game("mlb:3", 2, "A", "C"),
        ])
        row = {item.game_id: item for item in rows}["mlb:3"]
        self.assertEqual(row.features["home_rest_days"], 0.0)
        self.assertEqual(row.features["away_rest_days"], 0.0)

    def test_future_game_cannot_change_earlier_rest(self) -> None:
        prefix = [
            _game("mlb:1", 1, "A", "B"),
            _game("mlb:2", 1, "C", "D"),
            _game("mlb:3", 3, "A", "C"),
        ]
        normal = prefix + [_game("mlb:4", 10, "A", "C")]
        changed = prefix + [_game("mlb:4", 20, "A", "C", 200, 200)]
        expected = {item.game_id: item for item in self._rows(normal)}["mlb:3"]
        actual = {item.game_id: item for item in self._rows(changed)}["mlb:3"]
        self.assertEqual(expected.features, actual.features)

    def test_feature_timestamp_never_exceeds_prediction_timestamp(self) -> None:
        rows = self._rows([
            _game("mlb:1", 1, "A", "B"),
            _game("mlb:2", 1, "C", "D"),
            _game("mlb:3", 3, "A", "C"),
        ])
        self.assertTrue(all(row.feature_timestamp <= row.prediction_timestamp for row in rows))


if __name__ == "__main__":
    unittest.main()
