"""Tests for E8's same-season, prior-only recent-form features."""

from datetime import UTC, datetime
import unittest

from .conftest import completed_game
from mlb_kaizen.training.build_dataset import (
    RECENT_FORM_FORMULA_VERSION,
    build_point_in_time_rows_with_opponent_strength_and_recent_form,
)


def _game(game_id: str, year: int, day: int, home: str, away: str, home_runs: int = 4, away_runs: int = 4):
    return completed_game(
        game_id=game_id,
        start_time=datetime(year, 7, day, 18, tzinfo=UTC),
        home_team_id=home,
        away_team_id=away,
        home_runs=home_runs,
        away_runs=away_runs,
    )


class RecentFormRowsTests(unittest.TestCase):
    def _rows(self, games):
        return build_point_in_time_rows_with_opponent_strength_and_recent_form(
            games,
            minimum_prior_games=1,
            minimum_league_games_for_average=2,
            minimum_prior_matchups=1,
            recent_form_window=2,
        )

    @staticmethod
    def _five_games():
        return [
            _game("mlb:1", 2025, 1, "A", "B"),
            _game("mlb:2", 2025, 2, "C", "D"),
            _game("mlb:3", 2025, 3, "A", "C"),
            _game("mlb:4", 2025, 4, "B", "D"),
            _game("mlb:5", 2025, 5, "A", "C"),
        ]

    def test_emits_four_recent_features_and_versions_the_contract(self) -> None:
        self.assertEqual(RECENT_FORM_FORMULA_VERSION, "recent_form_formula_v1")
        rows = self._rows(self._five_games())
        row = {item.game_id: item for item in rows}["mlb:5"]
        self.assertTrue({
            "home_recent_offensive_index",
            "home_recent_run_prevention_index",
            "away_recent_offensive_index",
            "away_recent_run_prevention_index",
        }.issubset(row.features))

    def test_current_score_never_enters_its_own_recent_form(self) -> None:
        games = self._five_games() + [
            _game("mlb:6", 2025, 6, "B", "D"),
            _game("mlb:7", 2025, 7, "A", "C", home_runs=99, away_runs=1),
            _game("mlb:8", 2025, 8, "A", "C"),
        ]
        by_id = {item.game_id: item for item in self._rows(games)}
        self.assertLess(by_id["mlb:7"].features["home_recent_offensive_index"], 2.0)
        self.assertGreater(
            by_id["mlb:8"].features["home_recent_offensive_index"],
            by_id["mlb:7"].features["home_recent_offensive_index"],
        )

    def test_future_score_does_not_change_an_earlier_recent_form(self) -> None:
        normal = self._five_games() + [_game("mlb:6", 2025, 6, "B", "D")]
        blowout = normal[:-1] + [_game("mlb:6", 2025, 6, "B", "D", 200, 200)]
        earlier_normal = {item.game_id: item for item in self._rows(normal)}["mlb:5"]
        earlier_blowout = {item.game_id: item for item in self._rows(blowout)}["mlb:5"]
        self.assertEqual(earlier_normal.features, earlier_blowout.features)

    def test_recent_window_resets_when_a_new_season_starts(self) -> None:
        games = self._five_games() + [
            _game("mlb:6", 2026, 1, "A", "B"),
            _game("mlb:7", 2026, 2, "C", "D"),
            _game("mlb:8", 2026, 3, "A", "C"),
        ]
        row_ids = {item.game_id for item in self._rows(games)}
        self.assertNotIn("mlb:8", row_ids)

    def test_invalid_recent_window_is_rejected_and_timestamps_are_safe(self) -> None:
        with self.assertRaises(ValueError):
            build_point_in_time_rows_with_opponent_strength_and_recent_form(
                self._five_games(), recent_form_window=0
            )
        self.assertTrue(all(
            item.feature_timestamp <= item.prediction_timestamp
            for item in self._rows(self._five_games())
        ))


if __name__ == "__main__":
    unittest.main()
