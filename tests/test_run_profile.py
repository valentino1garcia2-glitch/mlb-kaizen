import unittest
from dataclasses import replace

from .conftest import team_season_stats
from mlb_kaizen.features.run_profile import (
    FORMULA_VERSION,
    GAMES_FOR_FULL_CONFIDENCE,
    compute_team_run_profile,
)


class ComputeTeamRunProfileTests(unittest.TestCase):
    def test_indices_are_ratios_to_the_supplied_league_average(self) -> None:
        stats = team_season_stats()  # games_played=150, runs_scored=720, runs_allowed=620
        profile = compute_team_run_profile(stats, league_average_runs_per_game=4.40)

        expected_offensive = (720 / 150) / 4.40
        expected_prevention = (620 / 150) / 4.40
        self.assertAlmostEqual(profile.offensive_index, expected_offensive)
        self.assertAlmostEqual(profile.run_prevention_index, expected_prevention)
        self.assertEqual(profile.team_id, stats.team_id)
        self.assertEqual(profile.sample_size, 150)

    def test_run_prevention_uses_total_runs_allowed_not_earned_runs_only(self) -> None:
        stats = team_season_stats()
        self.assertNotEqual(stats.runs_allowed, stats.earned_runs)  # fixture sanity check
        profile = compute_team_run_profile(stats, league_average_runs_per_game=4.40)
        # If this had used earned_runs instead, the index would be lower.
        understated = (stats.earned_runs / stats.games_played) / 4.40
        self.assertGreater(profile.run_prevention_index, understated)

    def test_data_quality_scales_with_games_played_and_caps_at_one(self) -> None:
        full_season = compute_team_run_profile(team_season_stats(), league_average_runs_per_game=4.40)
        self.assertEqual(full_season.data_quality, 1.0)  # 150 >= GAMES_FOR_FULL_CONFIDENCE

        low_sample_stats = replace(team_season_stats(), games_played=10)
        low_sample_profile = compute_team_run_profile(low_sample_stats, league_average_runs_per_game=4.40)
        self.assertAlmostEqual(low_sample_profile.data_quality, 10 / GAMES_FOR_FULL_CONFIDENCE)

    def test_zero_games_played_raises_rather_than_faking_average(self) -> None:
        zero_games_stats = replace(team_season_stats(), games_played=0)
        with self.assertRaises(ValueError):
            compute_team_run_profile(zero_games_stats, league_average_runs_per_game=4.40)

    def test_non_positive_league_average_raises(self) -> None:
        stats = team_season_stats()
        with self.assertRaises(ValueError):
            compute_team_run_profile(stats, league_average_runs_per_game=0)

    def test_provenance_inherits_source_data_retrieved_at_not_compute_time(self) -> None:
        stats = team_season_stats()
        profile = compute_team_run_profile(stats, league_average_runs_per_game=4.40)
        self.assertEqual(profile.provenance.retrieved_at, stats.provenance.retrieved_at)
        self.assertEqual(profile.provenance.source_version, FORMULA_VERSION)


if __name__ == "__main__":
    unittest.main()
