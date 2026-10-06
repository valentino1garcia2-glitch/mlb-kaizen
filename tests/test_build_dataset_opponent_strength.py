"""Tests for the prior-only opponent-strength dataset builder."""

from datetime import UTC, datetime
import unittest

from .conftest import completed_game
from mlb_kaizen.training.build_dataset import (
    OPPONENT_STRENGTH_FORMULA_VERSION,
    build_point_in_time_rows_with_opponent_strength,
)


def _game(
    game_id: str,
    day: int,
    home: str,
    away: str,
    home_runs: int = 4,
    away_runs: int = 4,
):
    return completed_game(
        game_id=game_id,
        start_time=datetime(2025, 7, day, 18, tzinfo=UTC),
        home_team_id=home,
        away_team_id=away,
        home_runs=home_runs,
        away_runs=away_runs,
    )


class OpponentStrengthRowsTests(unittest.TestCase):
    def test_feature_contract_is_versioned(self) -> None:
        self.assertEqual(OPPONENT_STRENGTH_FORMULA_VERSION, "opponent_strength_formula_v1")

    def _rows(self, games):
        return build_point_in_time_rows_with_opponent_strength(
            games,
            minimum_prior_games=1,
            minimum_league_games_for_average=2,
            minimum_prior_matchups=1,
        )

    def test_emits_all_four_opponent_features_after_prior_matchups(self) -> None:
        rows = self._rows([
            _game("mlb:1", 1, "A", "B"),
            _game("mlb:2", 2, "C", "D"),
            _game("mlb:3", 3, "A", "C"),
        ])
        row = {item.game_id: item for item in rows}["mlb:3"]
        self.assertEqual(
            {
                "home_opponent_offensive_index",
                "home_opponent_run_prevention_index",
                "away_opponent_offensive_index",
                "away_opponent_run_prevention_index",
            },
            set(row.features) - {
                "home_offensive_index",
                "away_offensive_index",
                "home_run_prevention_index",
                "away_run_prevention_index",
                "home_advantage",
            },
        )
        self.assertAlmostEqual(row.features["home_opponent_offensive_index"], 1.0)
        self.assertAlmostEqual(row.features["away_opponent_offensive_index"], 1.0)

    def test_current_games_result_never_enters_its_own_schedule_profile(self) -> None:
        # Team C's distinctive 99-run result occurs in game 3.  A's schedule
        # profile for game 3 only knows its prior opponent B, not C's current
        # score.  The 99 may affect game 4, where it is genuinely historical.
        rows = self._rows([
            _game("mlb:1", 1, "A", "B"),
            _game("mlb:2", 2, "C", "D"),
            _game("mlb:3", 3, "A", "C", home_runs=1, away_runs=99),
            _game("mlb:4", 4, "A", "C"),
        ])
        by_id = {item.game_id: item for item in rows}
        self.assertLess(by_id["mlb:3"].features["home_opponent_offensive_index"], 2.0)
        self.assertGreater(
            by_id["mlb:4"].features["home_opponent_offensive_index"],
            by_id["mlb:3"].features["home_opponent_offensive_index"],
        )

    def test_future_result_does_not_change_an_earlier_schedule_profile(self) -> None:
        before = [
            _game("mlb:1", 1, "A", "B"),
            _game("mlb:2", 2, "C", "D"),
            _game("mlb:3", 3, "A", "C"),
            _game("mlb:4", 4, "A", "C", home_runs=4, away_runs=4),
        ]
        after = before[:-1] + [_game("mlb:4", 4, "A", "C", home_runs=200, away_runs=200)]
        earlier_a = {row.game_id: row for row in self._rows(before)}["mlb:3"]
        earlier_b = {row.game_id: row for row in self._rows(after)}["mlb:3"]
        self.assertEqual(earlier_a.features, earlier_b.features)

    def test_invalid_thresholds_are_rejected(self) -> None:
        games = [_game("mlb:1", 1, "A", "B")]
        with self.assertRaises(ValueError):
            build_point_in_time_rows_with_opponent_strength(games, minimum_prior_games=0)
        with self.assertRaises(ValueError):
            build_point_in_time_rows_with_opponent_strength(
                games, minimum_league_games_for_average=0
            )
        with self.assertRaises(ValueError):
            build_point_in_time_rows_with_opponent_strength(games, minimum_prior_matchups=0)

    def test_feature_timestamp_never_exceeds_prediction_timestamp(self) -> None:
        rows = self._rows([
            _game("mlb:1", 1, "A", "B"),
            _game("mlb:2", 2, "C", "D"),
            _game("mlb:3", 3, "A", "C"),
        ])
        self.assertTrue(all(row.feature_timestamp <= row.prediction_timestamp for row in rows))


if __name__ == "__main__":
    unittest.main()
