"""Trainable transparent run baseline using time-aware tabular features."""

from __future__ import annotations

from dataclasses import dataclass

from mlb_kaizen.training.dataset import HistoricalGameRow, MODEL_FEATURES

# Selected with train=2022-2024 and validation=2025 only.  The untouched
# 2026 season is reserved for the final out-of-sample check; see DD-015.
DEFAULT_ALPHA = 0.0001

try:
    from sklearn.linear_model import PoissonRegressor
except ImportError as exc:  # pragma: no cover - exercised only in minimal installs
    PoissonRegressor = None
    _SKLEARN_ERROR = exc
else:
    _SKLEARN_ERROR = None


@dataclass(frozen=True, slots=True)
class RunPrediction:
    home_expected_runs: float
    away_expected_runs: float


class PoissonRunModel:
    """Two regularised Poisson regressors, one for each team's run target."""

    model_version = "MLB-KAIZEN-POISSON-RUNS-0.2.0"
    feature_version = "DATASET-RUN-FEATURES-1"

    def __init__(self, home_model, away_model, feature_names=MODEL_FEATURES) -> None:
        self.home_model = home_model
        self.away_model = away_model
        self.feature_names = tuple(feature_names)

    def predict(self, row: HistoricalGameRow) -> RunPrediction:
        vector = [[float(row.features[name]) for name in self.feature_names]]
        return RunPrediction(
            home_expected_runs=max(1e-6, float(self.home_model.predict(vector)[0])),
            away_expected_runs=max(1e-6, float(self.away_model.predict(vector)[0])),
        )


def fit_poisson_baseline(
    rows: list[HistoricalGameRow] | tuple[HistoricalGameRow, ...],
    alpha: float = DEFAULT_ALPHA,
    feature_names=MODEL_FEATURES,
) -> PoissonRunModel:
    """Fit a regularised Poisson model from prior-only rows."""

    if PoissonRegressor is None:
        raise RuntimeError("scikit-learn is required for Fase 5/7 training") from _SKLEARN_ERROR
    if len(rows) < 2:
        raise ValueError("at least two training rows are required")
    if alpha < 0:
        raise ValueError("alpha must be non-negative")
    feature_names = tuple(feature_names)
    x = [[float(row.features[name]) for name in feature_names] for row in rows]
    home = [row.home_runs for row in rows]
    away = [row.away_runs for row in rows]
    home_model = PoissonRegressor(alpha=alpha, max_iter=10_000)
    away_model = PoissonRegressor(alpha=alpha, max_iter=10_000)
    home_model.fit(x, home)
    away_model.fit(x, away)
    return PoissonRunModel(home_model, away_model, feature_names)
