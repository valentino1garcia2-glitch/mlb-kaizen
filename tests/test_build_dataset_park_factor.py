from datetime import UTC, datetime
import unittest

from .conftest import completed_game
from mlb_kaizen.training.build_dataset import canonical_venue_name, build_point_in_time_rows_with_park_factor


class CanonicalVenueNameTests(unittest.TestCase):
    def test_known_sponsorship_renames_map_to_the_same_park(self):
        self.assertEqual(canonical_venue_name("Rate Field"), "Guaranteed Rate Field")
    def test_unmapped_names_pass_through_unchanged(self): self.assertEqual(canonical_venue_name("Wrigley Field"), "Wrigley Field")
    def test_genuine_relocations_are_not_merged(self): self.assertNotEqual(canonical_venue_name("Oakland Coliseum"), canonical_venue_name("Sutter Health Park"))


class BuildPointInTimeRowsWithParkFactorTests(unittest.TestCase):
    def _inputs(self, count=5, venues=None):
        games = [completed_game(game_id=f"mlb:{i}", start_time=datetime(2025, 7, i, tzinfo=UTC), home_runs=4, away_runs=2) for i in range(1, count + 1)]
        mapped = {game.game_id: (venues[i - 1] if venues else "Coors Field") for i, game in enumerate(games)}
        return games, mapped
    def _rows(self, count=5, venues=None):
        games, mapped = self._inputs(count, venues)
        return build_point_in_time_rows_with_park_factor(games, mapped, minimum_prior_games=1, minimum_league_games_for_average=2, minimum_games_at_venue=1)
    def test_row_includes_park_run_factor_once_venue_threshold_is_met(self): self.assertIn("park_run_factor_index", self._rows()[0].features)
    def test_missing_venue_for_a_game_skips_only_that_row(self):
        games, mapped = self._inputs(); mapped.pop("mlb:3"); ids={r.game_id for r in build_point_in_time_rows_with_park_factor(games,mapped,minimum_prior_games=1,minimum_league_games_for_average=2,minimum_games_at_venue=1)}; self.assertNotIn("mlb:3",ids); self.assertIn("mlb:5",ids)
    def test_a_games_own_runs_never_appear_in_its_own_park_factor(self):
        games, mapped = self._inputs(5, ["Other", "Coors Field", "Coors Field", "Coors Field", "Coors Field"]); games[2] = completed_game(game_id="mlb:3", start_time=datetime(2025,7,3,tzinfo=UTC),home_runs=20,away_runs=20); rows=build_point_in_time_rows_with_park_factor(games,mapped,minimum_prior_games=1,minimum_league_games_for_average=2,minimum_games_at_venue=1); by_id={r.game_id:r for r in rows}; self.assertLess(by_id["mlb:3"].features["park_run_factor_index"], by_id["mlb:4"].features["park_run_factor_index"])
    def test_sponsorship_rename_does_not_reset_venue_history(self): self.assertTrue(self._rows(4,["Dodger Stadium","UNIQLO Field at Dodger Stadium","Dodger Stadium","Dodger Stadium"]))
    def test_rejects_non_positive_venue_threshold(self):
        games, mapped=self._inputs()
        with self.assertRaises(ValueError): build_point_in_time_rows_with_park_factor(games,mapped,minimum_games_at_venue=0)
    def test_feature_timestamp_never_exceeds_prediction_timestamp(self):
        for row in self._rows(): self.assertLessEqual(row.feature_timestamp,row.prediction_timestamp)
    def test_venue_history_requires_prior_games(self): self.assertFalse(build_point_in_time_rows_with_park_factor(*self._inputs(1),minimum_prior_games=1,minimum_league_games_for_average=1,minimum_games_at_venue=1))
