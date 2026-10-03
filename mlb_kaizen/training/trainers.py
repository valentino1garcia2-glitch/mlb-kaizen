"""Trainer objects used by walk-forward orchestration."""

from __future__ import annotations

from mlb_kaizen.models.ml import fit_gradient_tree_model
from mlb_kaizen.training.baseline import fit_poisson_baseline


class PoissonTrainer:
    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha = alpha
        self.model = None

    def fit(self, rows):
        self.model = fit_poisson_baseline(tuple(rows), alpha=self.alpha)
        return self

    def predict(self, row):
        if self.model is None:
            raise RuntimeError("trainer is not fitted")
        return self.model.predict(row)


class RandomForestTrainer:
    def __init__(self, random_seed: int = 20260918) -> None:
        self.random_seed = random_seed
        self.model = None

    def fit(self, rows):
        self.model = fit_gradient_tree_model(tuple(rows), random_seed=self.random_seed)
        return self

    def predict(self, row):
        if self.model is None:
            raise RuntimeError("trainer is not fitted")
        return self.model.predict(row)
