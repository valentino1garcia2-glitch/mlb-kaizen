from datetime import UTC, datetime
import unittest

from .conftest import completed_game, starter_line
from mlb_kaizen.training.build_dataset import (
    _parse_innings_pitched_to_outs,
    build_point_in_time_rows_with_starters,
)


class ParseInningsPitchedTests(unittest.TestCase):
    def test_whole_innings(self): self.assertEqual(_parse_innings_pitched_to_outs("6.0"), 18)
    def test_one_out_fraction(self): self.assertEqual(_parse_innings_pitched_to_outs("5.1"), 16)
    def test_two_out_fraction(self): self.assertEqual(_parse_innings_pitched_to_outs("5.2"), 17)
    def test_no_fraction_part(self): self.assertEqual(_parse_innings_pitched_to_outs("7"), 21)
    def test_invalid_fraction_raises(self):
        with self.assertRaises(ValueError): _parse_innings_pitched_to_outs("5.3")
    def test_empty_raises(self):
        with self.assertRaises(ValueError): _parse_innings_pitched_to_outs("")


class BuildPointInTimeRowsWithStartersTests(unittest.TestCase):
    def _game_and_starters(self, i, home_pid, away_pid, home_er, away_er):
        game = completed_game(game_id=f"mlb:{i}", start_time=datetime(2025, 7, i, tzinfo=UTC), home_runs=4, away_runs=3)
        return game, starter_line(game_id=game.game_id, pitcher_id=home_pid, side="home", earned_runs=home_er), starter_line(game_id=game.game_id, pitcher_id=away_pid, side="away", earned_runs=away_er)

    def _rows(self, count=4):
        games, starters = [], []
        for i in range(1, count + 1):
            game, home, away = self._game_and_starters(i, "H1", "A1", 2, 2)
            games.append(game); starters += [home, away]
        return build_point_in_time_rows_with_starters(games, starters, minimum_prior_games=1, minimum_league_games_for_average=2, minimum_prior_starts=1, minimum_league_outs_for_average=1)

    def test_row_includes_starter_era_index_features(self):
        rows = self._rows()
        self.assertTrue(rows)
        self.assertIn("home_starter_era_index", rows[0].features)
        self.assertIn("away_starter_era_index", rows[0].features)

    def test_missing_starter_for_a_game_skips_only_that_row(self):
        games, starters = [], []
        for i in range(1, 6):
            game, home, away = self._game_and_starters(i, "H1", "A1", 2, 2); games.append(game)
            if i != 3: starters += [home, away]
        row_ids = {row.game_id for row in build_point_in_time_rows_with_starters(games, starters, minimum_prior_games=1, minimum_league_games_for_average=2, minimum_prior_starts=1, minimum_league_outs_for_average=1)}
        self.assertNotIn("mlb:3", row_ids); self.assertIn("mlb:5", row_ids)

    def test_a_starts_own_earned_runs_never_appear_in_its_own_row(self):
        games, starters = [], []
        for i, earned in zip(range(1, 4), (1, 1, 20)):
            game, home, away = self._game_and_starters(i, "H1", "A1", earned, 1); games.append(game); starters += [home, away]
        game, home, away = self._game_and_starters(4, "H1", "A1", 1, 1); games.append(game); starters += [home, away]
        by_id = {row.game_id: row for row in build_point_in_time_rows_with_starters(games, starters, minimum_prior_games=1, minimum_league_games_for_average=2, minimum_prior_starts=1, minimum_league_outs_for_average=1)}
        self.assertLess(by_id["mlb:3"].features["home_starter_era_index"], 2.0)
        self.assertGreater(by_id["mlb:4"].features["home_starter_era_index"], by_id["mlb:3"].features["home_starter_era_index"])

    def test_feature_timestamp_never_exceeds_prediction_timestamp(self):
        for row in self._rows(3): self.assertLessEqual(row.feature_timestamp, row.prediction_timestamp)

    def test_rejects_non_positive_starter_thresholds(self):
        game, home, away = self._game_and_starters(1, "H1", "A1", 2, 2)
        with self.assertRaises(ValueError): build_point_in_time_rows_with_starters([game], [home, away], minimum_prior_starts=0)
        with self.assertRaises(ValueError): build_point_in_time_rows_with_starters([game], [home, away], minimum_league_outs_for_average=0)
