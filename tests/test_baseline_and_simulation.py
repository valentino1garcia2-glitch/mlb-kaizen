import unittest

from mlb_kaizen.models.baseline import BaselineRunModel
from mlb_kaizen.simulation.monte_carlo import MonteCarloEngine

from .conftest import away_profile, game, home_profile


class BaselineAndSimulationTests(unittest.TestCase):
    def test_baseline_formula_is_reproducible(self) -> None:
        projection = BaselineRunModel().project(game(), home_profile(), away_profile())
        self.assertAlmostEqual(projection.home_expected_runs, 4.40 * 1.10 * 1.05 * 1.035)
        self.assertAlmostEqual(projection.away_expected_runs, 4.40 * 0.95 * 0.90)

    def test_simulation_is_reproducible_and_reports_requested_markets(self) -> None:
        projection = BaselineRunModel().project(game(), home_profile(), away_profile())
        first = MonteCarloEngine(simulation_count=2_000, random_seed=7).run(
            projection, total_line=8.5, home_run_line=-1.5
        )
        second = MonteCarloEngine(simulation_count=2_000, random_seed=7).run(
            projection, total_line=8.5, home_run_line=-1.5
        )
        self.assertEqual(first, second)
        self.assertGreaterEqual(first.home_win_probability, 0)
        self.assertLessEqual(first.home_win_probability, 1)
        self.assertIsNotNone(first.over_probability)
        self.assertIsNotNone(first.home_run_line_cover_probability)
