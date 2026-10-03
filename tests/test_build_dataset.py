from datetime import UTC, datetime
import unittest

from .conftest import completed_game
from mlb_kaizen.training.build_dataset import build_point_in_time_rows


class BuildPointInTimeRowsTests(unittest.TestCase):
    def test_first_games_are_skipped_until_minimum_prior_games_is_met(self) -> None:
        games = [
            completed_game(game_id=f"mlb:{i}", start_time=datetime(2025, 7, i, tzinfo=UTC))
            for i in range(1, 6)
        ]
        rows = build_point_in_time_rows(
            games, minimum_prior_games=1, minimum_league_games_for_average=2
        )
        # Game 1: both teams have 0 prior games -> skipped.
        # Game 2 (same two teams again would satisfy prior games, but here
        # every game reuses team ids 10/20, so game 2 has 1 prior game each,
        # and league_games=2 after game 1 satisfies the league threshold.
        self.assertEqual(len(rows), 4)
        self.assertNotIn("mlb:1", [row.game_id for row in rows])

    def test_a_games_own_result_never_appears_in_its_own_features(self) -> None:
        # Team 10 scores a huge, distinctive 99 runs in game 3; if that number
        # leaked into game 3's own offensive_index, the index would be an
        # extreme outlier. It must only affect game 4 and later.
        games = [
            completed_game(game_id="mlb:1", start_time=datetime(2025, 7, 1, tzinfo=UTC), home_runs=4, away_runs=2),
            completed_game(game_id="mlb:2", start_time=datetime(2025, 7, 2, tzinfo=UTC), home_runs=3, away_runs=3),
            completed_game(game_id="mlb:3", start_time=datetime(2025, 7, 3, tzinfo=UTC), home_runs=99, away_runs=1),
            completed_game(game_id="mlb:4", start_time=datetime(2025, 7, 4, tzinfo=UTC), home_runs=5, away_runs=2),
        ]
        rows = build_point_in_time_rows(
            games, minimum_prior_games=1, minimum_league_games_for_average=2
        )
        by_id = {row.game_id: row for row in rows}
        # Game 3's home team (id "10") has only games 1-2 as prior history
        # (avg runs scored (4+3)/2 = 3.5), NOT its own 99.
        self.assertIn("mlb:3", by_id)
        self.assertLess(by_id["mlb:3"].features["home_offensive_index"], 2.0)
        # Game 4 DOES see the 99-run game in its prior history, so its
        # home offensive_index should be clearly elevated versus game 3's.
        self.assertGreater(
            by_id["mlb:4"].features["home_offensive_index"],
            by_id["mlb:3"].features["home_offensive_index"],
        )

    def test_league_average_is_point_in_time_not_whole_window(self) -> None:
        # A late blowout (game 4) must not affect the league average used
        # for an earlier eligible row (game 2's).
        games = [
            completed_game(
                game_id="mlb:1", start_time=datetime(2025, 7, 1, tzinfo=UTC),
                home_team_id="10", away_team_id="20", home_runs=4, away_runs=4,
            ),
            completed_game(
                game_id="mlb:2", start_time=datetime(2025, 7, 2, tzinfo=UTC),
                home_team_id="10", away_team_id="20", home_runs=4, away_runs=4,
            ),
            completed_game(
                game_id="mlb:3", start_time=datetime(2025, 7, 3, tzinfo=UTC),
                home_team_id="10", away_team_id="20", home_runs=4, away_runs=4,
            ),
            completed_game(
                game_id="mlb:4", start_time=datetime(2025, 7, 4, tzinfo=UTC),
                home_team_id="10", away_team_id="20", home_runs=50, away_runs=50,
            ),
        ]
        rows = build_point_in_time_rows(
            games, minimum_prior_games=1, minimum_league_games_for_average=2
        )
        by_id = {row.game_id: row for row in rows}
        # Games are all 4-4 until the game 4 blowout; a team scoring its own
        # league average every time should show offensive_index == 1.0
        # exactly for game 3 (average of games 1-2, both 4 runs) -- proving
        # game 4's 50-run blowout was not folded in.
        self.assertAlmostEqual(by_id["mlb:3"].features["home_offensive_index"], 1.0)

    def test_home_advantage_feature_uses_the_supplied_constant(self) -> None:
        games = [
            completed_game(game_id="mlb:1", start_time=datetime(2025, 7, 1, tzinfo=UTC)),
            completed_game(game_id="mlb:2", start_time=datetime(2025, 7, 2, tzinfo=UTC)),
        ]
        rows = build_point_in_time_rows(
            games, minimum_prior_games=1, minimum_league_games_for_average=1, home_advantage=1.05
        )
        self.assertTrue(all(row.features["home_advantage"] == 1.05 for row in rows))

    def test_feature_timestamp_never_exceeds_prediction_timestamp(self) -> None:
        # HistoricalGameRow itself enforces this, but confirm the builder
        # never trips it (e.g. by mistakenly using "now" instead of game time).
        games = [
            completed_game(game_id=f"mlb:{i}", start_time=datetime(2020, 1, i, tzinfo=UTC))
            for i in range(1, 4)
        ]
        rows = build_point_in_time_rows(games, minimum_prior_games=1, minimum_league_games_for_average=1)
        for row in rows:
            self.assertLessEqual(row.feature_timestamp, row.prediction_timestamp)

    def test_rejects_non_positive_thresholds(self) -> None:
        games = [completed_game()]
        with self.assertRaises(ValueError):
            build_point_in_time_rows(games, minimum_prior_games=0)
        with self.assertRaises(ValueError):
            build_point_in_time_rows(games, minimum_league_games_for_average=0)


if __name__ == "__main__":
    unittest.main()
