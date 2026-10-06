"""Tests for E10's same-season, prior-only home/away split inputs."""

from datetime import UTC, datetime
import unittest

from .conftest import completed_game
from mlb_kaizen.training.build_dataset import (
    SITE_SPLIT_FORMULA_VERSION,
    build_point_in_time_rows_with_opponent_strength_recent_form_and_site_splits,
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


class SiteSplitRowsTests(unittest.TestCase):
    def _rows(self, games):
        return build_point_in_time_rows_with_opponent_strength_recent_form_and_site_splits(
            games,
            minimum_prior_games=1,
            minimum_league_games_for_average=2,
            minimum_prior_matchups=1,
            recent_form_window=1,
            minimum_prior_site_games=1,
        )

    def test_emits_site_features_and_versions_contract(self) -> None:
        self.assertEqual(SITE_SPLIT_FORMULA_VERSION, "site_split_formula_v1")
        rows = self._rows([
            _game("mlb:1", 1, "A", "B"),
            _game("mlb:2", 1, "D", "C"),
            _game("mlb:3", 3, "A", "C"),
        ])
        row = {item.game_id: item for item in rows}["mlb:3"]
        self.assertTrue({
            "home_site_offensive_index", "home_site_run_prevention_index",
            "away_site_offensive_index", "away_site_run_prevention_index",
        }.issubset(row.features))

    def test_current_score_never_enters_its_own_site_split(self) -> None:
        games = [
            _game("mlb:1", 1, "A", "B"),
            _game("mlb:2", 1, "D", "C"),
            _game("mlb:3", 3, "A", "C", 99, 1),
            _game("mlb:4", 4, "A", "C"),
        ]
        by_id = {item.game_id: item for item in self._rows(games)}
        self.assertLess(by_id["mlb:3"].features["home_site_offensive_index"], 2.0)
        self.assertGreater(
            by_id["mlb:4"].features["home_site_offensive_index"],
            by_id["mlb:3"].features["home_site_offensive_index"],
        )

    def test_future_score_does_not_change_earlier_site_split(self) -> None:
        prefix = [_game("mlb:1", 1, "A", "B"), _game("mlb:2", 1, "D", "C"), _game("mlb:3", 3, "A", "C")]
        first = {item.game_id: item for item in self._rows(prefix + [_game("mlb:4", 4, "A", "C")])}["mlb:3"]
        second = {item.game_id: item for item in self._rows(prefix + [_game("mlb:4", 4, "A", "C", 200, 200)])}["mlb:3"]
        self.assertEqual(first.features, second.features)

    def test_invalid_site_threshold_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_point_in_time_rows_with_opponent_strength_recent_form_and_site_splits(
                [_game("mlb:1", 1, "A", "B")], minimum_prior_site_games=0
            )


if __name__ == "__main__":
    unittest.main()
