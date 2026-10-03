"""Expanding-window walk-forward evaluation with point-in-time ordering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Protocol, Sequence
import math

from mlb_kaizen.models.baseline import RunProjection
from mlb_kaizen.simulation.monte_carlo import MonteCarloEngine
from mlb_kaizen.training.dataset import HistoricalGameRow
from mlb_kaizen.evaluation.metrics import brier_score, log_loss, mean_absolute_error, rmse


class RunPredictor(Protocol):
    def predict(self, row: HistoricalGameRow): ...


@dataclass(frozen=True, slots=True)
class EvaluationPrediction:
    game_id: str
    prediction_timestamp: datetime
    model_home_runs: float
    model_away_runs: float
    home_win_probability: float
    home_runs: int
    away_runs: int


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    model_name: str
    sample_size: int
    home_run_mae: float
    away_run_mae: float
    total_run_rmse: float
    brier: float
    log_loss_value: float
    predictions: tuple[EvaluationPrediction, ...]


def home_win_probability_from_runs(
    home_expected: float, away_expected: float, simulation_count: int = 5_000, random_seed: int = 20260918
) -> float:
    """Estimate win probability from the production Negative-Binomial family.

    The evaluation path uses an exact truncated PMF calculation rather than Monte Carlo so large
    historical evaluations are fast and free from avoidable simulation noise. `simulation_count` and
    `random_seed` remain accepted for compatibility with the CLI contract but are not needed by the
    deterministic evaluator. The production simulator remains stochastic and reproducible.
    """
    del simulation_count, random_seed
    home = _negative_binomial_pmf(max(1e-6, home_expected), 4.0)
    away = _negative_binomial_pmf(max(1e-6, away_expected), 4.0)
    home_win = 0.0
    for home_runs, home_probability in enumerate(home):
        home_win += home_probability * sum(away_probability for away_runs, away_probability in enumerate(away) if home_runs > away_runs)
        home_win += home_probability * away[home_runs] * 0.5 if home_runs < len(away) else 0.0
    return min(1.0, max(0.0, home_win))


def _negative_binomial_pmf(mean: float, dispersion: float, max_runs: int = 80) -> tuple[float, ...]:
    """Truncated PMF of the Gamma-Poisson / Negative-Binomial parameterisation used in production."""
    if mean <= 0 or dispersion <= 0:
        raise ValueError("mean and dispersion must be positive")
    p = dispersion / (dispersion + mean)
    q = mean / (dispersion + mean)
    probabilities = [p ** dispersion]
    for k in range(max_runs):
        probabilities.append(probabilities[-1] * q * (k + dispersion) / (k + 1))
    total = sum(probabilities)
    return tuple(value / total for value in probabilities)


def walk_forward_evaluate(
    rows: Sequence[HistoricalGameRow],
    trainer_factory: Callable[[], object],
    model_name: str,
    min_train_size: int = 30,
    test_window: int = 10,
    simulation_count: int = 5_000,
) -> EvaluationSummary:
    """Fit only on earlier rows and score only on later rows."""

    ordered = tuple(sorted(rows, key=lambda row: (row.prediction_timestamp, row.game_id)))
    if min_train_size < 2 or test_window < 1:
        raise ValueError("invalid walk-forward parameters")
    if len(ordered) <= min_train_size:
        raise ValueError("dataset is too small for requested walk-forward split")

    predictions: list[EvaluationPrediction] = []
    start = min_train_size
    fold_number = 0
    while start < len(ordered):
        end = min(len(ordered), start + test_window)
        train = ordered[:start]
        test = ordered[start:end]
        model = trainer_factory()
        model.fit(train)
        for row_index, row in enumerate(test):
            prediction = model.predict(row)
            probability = home_win_probability_from_runs(
                prediction.home_expected_runs,
                prediction.away_expected_runs,
                simulation_count=simulation_count,
                random_seed=20260918 + fold_number * 10_000 + row_index,
            )
            predictions.append(
                EvaluationPrediction(
                    game_id=row.game_id,
                    prediction_timestamp=row.prediction_timestamp,
                    model_home_runs=prediction.home_expected_runs,
                    model_away_runs=prediction.away_expected_runs,
                    home_win_probability=probability,
                    home_runs=row.home_runs,
                    away_runs=row.away_runs,
                )
            )
        start = end
        fold_number += 1

    home_errors = [p.model_home_runs - p.home_runs for p in predictions]
    away_errors = [p.model_away_runs - p.away_runs for p in predictions]
    total_errors = [(p.model_home_runs + p.model_away_runs) - (p.home_runs + p.away_runs) for p in predictions]
    probabilities = [p.home_win_probability for p in predictions]
    outcomes = [int(p.home_runs > p.away_runs) for p in predictions]
    return EvaluationSummary(
        model_name=model_name,
        sample_size=len(predictions),
        home_run_mae=mean_absolute_error(home_errors),
        away_run_mae=mean_absolute_error(away_errors),
        total_run_rmse=rmse(total_errors),
        brier=brier_score(probabilities, outcomes),
        log_loss_value=log_loss(probabilities, outcomes),
        predictions=tuple(predictions),
    )


def prediction_accuracy(summary: EvaluationSummary) -> float:
    if not summary.predictions:
        return math.nan
    return sum(
        int((p.home_win_probability >= 0.5) == (p.home_runs > p.away_runs))
        for p in summary.predictions
    ) / len(summary.predictions)
