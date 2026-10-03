"""Optional ML model evaluated only with the same time-aware feature contract."""

from __future__ import annotations

from dataclasses import dataclass

from mlb_kaizen.training.dataset import HistoricalGameRow, MODEL_FEATURES

try:
    from sklearn.ensemble import RandomForestRegressor
except ImportError as exc:  # pragma: no cover
    RandomForestRegressor = None
    _SKLEARN_ERROR = exc
else:
    _SKLEARN_ERROR = None


@dataclass(frozen=True, slots=True)
class MLRunPrediction:
    home_expected_runs: float
    away_expected_runs: float


class GradientTreeRunModel:
    """Random-forest run model used as a deliberately simple ML challenger."""

    model_version = "MLB-KAIZEN-RF-RUNS-0.1.0"
    feature_version = "DATASET-RUN-FEATURES-1"

    def __init__(self, home_model, away_model, feature_names=MODEL_FEATURES) -> None:
        self.home_model = home_model
        self.away_model = away_model
        self.feature_names = tuple(feature_names)

    def predict(self, row: HistoricalGameRow) -> MLRunPrediction:
        vector = [[float(row.features[name]) for name in self.feature_names]]
        return MLRunPrediction(
            home_expected_runs=max(1e-6, float(self.home_model.predict(vector)[0])),
            away_expected_runs=max(1e-6, float(self.away_model.predict(vector)[0])),
        )


def fit_gradient_tree_model(
    rows: list[HistoricalGameRow] | tuple[HistoricalGameRow, ...],
    random_seed: int = 20260918,
    feature_names=MODEL_FEATURES,
) -> GradientTreeRunModel:
    """Fit a non-linear challenger; callers must still compare it to baseline out-of-sample."""

    if RandomForestRegressor is None:
        raise RuntimeError("scikit-learn is required for Fase 7") from _SKLEARN_ERROR
    if len(rows) < 4:
        raise ValueError("at least four training rows are required")
    feature_names = tuple(feature_names)
    x = [[float(row.features[name]) for name in feature_names] for row in rows]
    home = [row.home_runs for row in rows]
    away = [row.away_runs for row in rows]
    kwargs = dict(n_estimators=200, min_samples_leaf=3, random_state=random_seed, n_jobs=1)
    home_model = RandomForestRegressor(**kwargs).fit(x, home)
    away_model = RandomForestRegressor(**kwargs).fit(x, away)
    return GradientTreeRunModel(home_model, away_model, feature_names)
