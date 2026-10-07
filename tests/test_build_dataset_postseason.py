"""E12 tests: only playoff targets, and every input is strictly pregame."""

from datetime import UTC, datetime
import unittest

from .conftest import completed_game
from mlb_kaizen.training.build_dataset import (
    POSTSEASON_FORMULA_VERSION,
    build_postseason_point_in_time_rows,
)


def _game(
    game_id: str, day: int, home: str, away: str, home_runs: int = 4,
    away_runs: int = 4, game_type: str = "R", year: int = 2025, hour: int = 18,
):
    return completed_game(
        game_id=game_id, start_time=datetime(year, 10, day, hour, tzinfo=UTC),
        home_team_id=home, away_team_id=away, home_runs=home_runs,
        away_runs=away_runs, game_type=game_type,
    )


class PostseasonRowsTests(unittest.TestCase):
    def _rows(self, games):
        return build_postseason_point_in_time_rows(
            games, minimum_prior_games=1, minimum_league_games_for_average=2,
            minimum_prior_matchups=1, recent_form_window=1,
        )

    @staticmethod
    def _history():
        return [
            _game("mlb:1", 1, "A", "B", 5, 3),
            _game("mlb:2", 2, "C", "D", 4, 4),
            _game("mlb:3", 3, "A", "C", 2, 1),
            _game("mlb:4", 4, "B", "D", 3, 3),
        ]

    def test_emits_only_playoff_targets_with_all_thirteen_features(self) -> None:
        rows = self._rows(self._history() + [
            _game("mlb:5", 5, "A", "C", game_type="D"),
            _game("mlb:6", 6, "A", "C", game_type="S"),
        ])
        self.assertEqual([row.game_id for row in rows], ["mlb:5"])
        self.assertEqual(len(rows[0].features), 13)
        self.assertEqual(POSTSEASON_FORMULA_VERSION, "postseason_e3_e7_e8_formula_v1")

    def test_targets_own_score_never_enters_its_own_features(self) -> None:
        games = self._history() + [
            _game("mlb:5", 5, "A", "C", 99, 1, "D"),
            _game("mlb:6", 6, "A", "C", 4, 4, "L"),
        ]
        rows = {row.game_id: row for row in self._rows(games)}
        self.assertLess(rows["mlb:5"].features["home_recent_offensive_index"], 2.0)
        self.assertGreater(
            rows["mlb:6"].features["home_recent_offensive_index"],
            rows["mlb:5"].features["home_recent_offensive_index"],
        )

    def test_future_score_cannot_change_an_earlier_playoff_row(self) -> None:
        normal = self._history() + [
            _game("mlb:5", 5, "A", "C", 4, 4, "D"),
            _game("mlb:6", 6, "A", "C", 4, 4, "L"),
        ]
        changed = normal[:-1] + [_game("mlb:6", 6, "A", "C", 200, 200, "L")]
        self.assertEqual(
            {row.game_id: row for row in self._rows(normal)}["mlb:5"].features,
            {row.game_id: row for row in self._rows(changed)}["mlb:5"].features,
        )

    def test_simultaneous_final_cannot_enter_a_playoff_rows_features(self) -> None:
        normal = self._history() + [
            _game("mlb:5", 5, "A", "C", 4, 4, "D"),
            _game("mlb:6", 5, "A", "C", 1, 1, "R"),
        ]
        changed = normal[:-1] + [_game("mlb:6", 5, "A", "C", 200, 200, "R")]
        self.assertEqual(
            {row.game_id: row for row in self._rows(normal)}["mlb:5"].features,
            {row.game_id: row for row in self._rows(changed)}["mlb:5"].features,
        )

    def test_excluded_game_types_never_enter_history(self) -> None:
        normal = self._history() + [
            _game("mlb:x", 5, "A", "C", 1, 1, "E"),
            _game("mlb:5", 6, "A", "C", 4, 4, "D"),
        ]
        changed = normal[:-2] + [
            _game("mlb:x", 5, "A", "C", 200, 200, "E"),
            _game("mlb:5", 6, "A", "C", 4, 4, "D"),
        ]
        self.assertEqual(self._rows(normal)[0].features, self._rows(changed)[0].features)

    def test_all_accumulators_reset_between_seasons(self) -> None:
        games = self._history() + [
            _game("mlb:5", 5, "A", "C", 4, 4, "D"),
            _game("mlb:6", 1, "A", "C", 4, 4, "D", year=2026),
        ]
        self.assertEqual([row.game_id for row in self._rows(games)], ["mlb:5"])

    def test_invalid_thresholds_and_timestamps_are_rejected_or_safe(self) -> None:
        with self.assertRaises(ValueError):
            build_postseason_point_in_time_rows(self._history(), recent_form_window=0)
        rows = self._rows(self._history() + [_game("mlb:5", 5, "A", "C", game_type="D")])
        self.assertTrue(all(row.feature_timestamp <= row.prediction_timestamp for row in rows))

