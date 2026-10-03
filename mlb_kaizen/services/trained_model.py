"""Adapter that makes a trusted trained run model usable by Analyst Mode."""

from __future__ import annotations

from mlb_kaizen.models.baseline import RunProjection
from mlb_kaizen.training.baseline import PoissonRunModel
from mlb_kaizen.training.dataset import HistoricalGameRow, MODEL_FEATURES
from mlb_kaizen.training.artifacts import ModelArtifactMetadata, load_model_artifact


class TrainedPoissonAnalysisModel:
    """Bridge current TeamRunProfiles to the E3 Poisson feature contract."""

    def __init__(self, model: PoissonRunModel, *, home_advantage: float = 1.035, dispersion: float = 4.0) -> None:
        if tuple(model.feature_names) != MODEL_FEATURES:
            raise ValueError("trained Analyst Mode currently supports only the E3 team feature contract")
        if home_advantage <= 0 or dispersion <= 0:
            raise ValueError("analysis assumptions must be positive")
        self.model, self.home_advantage, self.dispersion = model, home_advantage, dispersion

    @classmethod
    def from_artifact(cls, path):
        """Load only a trusted local Poisson artifact and retain its metadata."""
        model, metadata = load_model_artifact(path)
        if not isinstance(model, PoissonRunModel):
            raise ValueError("artifact is not a supported trained Poisson run model")
        return cls(model), metadata

    def project_analysis(self, request) -> RunProjection:
        timestamp = request.context.prediction_timestamp
        row = HistoricalGameRow(
            game_id=request.game.game_id, official_date=request.game.official_date,
            prediction_timestamp=timestamp, feature_timestamp=timestamp,
            features={
                "home_offensive_index": request.home_profile.offensive_index,
                "away_offensive_index": request.away_profile.offensive_index,
                "home_run_prevention_index": request.home_profile.run_prevention_index,
                "away_run_prevention_index": request.away_profile.run_prevention_index,
                "home_advantage": self.home_advantage,
            }, home_runs=0, away_runs=0,
        )
        prediction = self.model.predict(row)
        return RunProjection(request.game.game_id, prediction.home_expected_runs, prediction.away_expected_runs,
                             self.dispersion, self.dispersion, self.model.model_version, self.model.feature_version)
