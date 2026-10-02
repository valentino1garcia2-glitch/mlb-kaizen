"""Negative-Binomial Monte Carlo simulation for modelled game runs."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

from mlb_kaizen.models.baseline import RunProjection


@dataclass(frozen=True, slots=True)
class SimulationSummary:
    """Distribution summaries and Monte Carlo sampling uncertainty."""

    simulation_count: int
    random_seed: int
    home_win_probability: float
    away_win_probability: float
    regulation_tie_probability: float
    home_mean_runs: float
    away_mean_runs: float
    total_mean_runs: float
    home_win_standard_error: float
    over_probability: float | None = None
    under_probability: float | None = None
    total_push_probability: float | None = None
    home_run_line_cover_probability: float | None = None
    home_run_line_push_probability: float | None = None


class MonteCarloEngine:
    """Simulate overdispersed runs from a Gamma-Poisson mixture.

    A Negative Binomial model uses mean ``mu`` and dispersion ``k``. Conditional
    on a Gamma draw with mean ``mu``, runs are Poisson. Higher ``k`` approaches a
    Poisson distribution; it does not by itself improve predictive quality.
    """

    def __init__(self, simulation_count: int = 100_000, random_seed: int = 20_260_916) -> None:
        if simulation_count < 1:
            raise ValueError("simulation_count must be positive")
        self.simulation_count = simulation_count
        self.random_seed = random_seed

    def run(
        self,
        projection: RunProjection,
        total_line: float | None = None,
        home_run_line: float | None = None,
    ) -> SimulationSummary:
        """Generate game states and optional total/run-line probabilities.

        MLB games cannot finish tied. In this first model, a regulation tie is
        resolved with a fair random extra-inning proxy. Its frequency is reported
        explicitly so it cannot be mistaken for a validated extra-inning model.
        """

        if total_line is not None and total_line < 0:
            raise ValueError("total line cannot be negative")
        rng = random.Random(self.random_seed)
        home_wins = regulation_ties = over = under = total_push = 0
        cover = run_line_push = 0
        home_run_sum = away_run_sum = 0

        for _ in range(self.simulation_count):
            home_runs = self._negative_binomial(rng, projection.home_expected_runs, projection.home_dispersion)
            away_runs = self._negative_binomial(rng, projection.away_expected_runs, projection.away_dispersion)
            home_run_sum += home_runs
            away_run_sum += away_runs

            if home_runs == away_runs:
                regulation_ties += 1
                home_wins += int(rng.random() < 0.5)
            elif home_runs > away_runs:
                home_wins += 1

            if total_line is not None:
                total = home_runs + away_runs
                if total > total_line:
                    over += 1
                elif total < total_line:
                    under += 1
                else:
                    total_push += 1

            if home_run_line is not None:
                adjusted_home = home_runs + home_run_line
                if adjusted_home > away_runs:
                    cover += 1
                elif adjusted_home == away_runs:
                    run_line_push += 1

        home_probability = home_wins / self.simulation_count
        return SimulationSummary(
            simulation_count=self.simulation_count,
            random_seed=self.random_seed,
            home_win_probability=home_probability,
            away_win_probability=1 - home_probability,
            regulation_tie_probability=regulation_ties / self.simulation_count,
            home_mean_runs=home_run_sum / self.simulation_count,
            away_mean_runs=away_run_sum / self.simulation_count,
            total_mean_runs=(home_run_sum + away_run_sum) / self.simulation_count,
            home_win_standard_error=math.sqrt(home_probability * (1 - home_probability) / self.simulation_count),
            over_probability=over / self.simulation_count if total_line is not None else None,
            under_probability=under / self.simulation_count if total_line is not None else None,
            total_push_probability=total_push / self.simulation_count if total_line is not None else None,
            home_run_line_cover_probability=cover / self.simulation_count if home_run_line is not None else None,
            home_run_line_push_probability=run_line_push / self.simulation_count if home_run_line is not None else None,
        )

    @staticmethod
    def _negative_binomial(rng: random.Random, mean: float, dispersion: float) -> int:
        if mean <= 0 or dispersion <= 0:
            raise ValueError("mean and dispersion must be positive")
        poisson_rate = rng.gammavariate(dispersion, mean / dispersion)
        return MonteCarloEngine._poisson(rng, poisson_rate)

    @staticmethod
    def _poisson(rng: random.Random, rate: float) -> int:
        threshold = math.exp(-rate)
        product = 1.0
        count = 0
        while product > threshold:
            count += 1
            product *= rng.random()
        return count - 1
