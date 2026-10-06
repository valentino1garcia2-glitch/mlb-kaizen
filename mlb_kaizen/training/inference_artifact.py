"""Versioned, calibrated inference artifacts for the evaluated E3+E7+E8 model.

Training and loading are deliberately separate.  Loading this artifact never
fits a model or calibrator; callers must supply a feature vector in the exact
stored order.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Mapping, Sequence

from mlb_kaizen.evaluation.calibration import PlattCalibrator
from mlb_kaizen.evaluation.walk_forward import home_win_probability_from_runs
from mlb_kaizen.training.artifacts import (
    ModelArtifactMetadata,
    load_model_artifact,
    save_model_artifact,
)
from mlb_kaizen.training.baseline import PoissonRunModel, RunPrediction, fit_poisson_baseline
from mlb_kaizen.training.dataset import HistoricalGameRow, MODEL_FEATURES


INFERENCE_ARTIFACT_SCHEMA_VERSION = "calibrated_poisson_inference_v1"
E8_FEATURE_NAMES = MODEL_FEATURES + (
    "home_opponent_offensive_index",
    "home_opponent_run_prevention_index",
    "away_opponent_offensive_index",
    "away_opponent_run_prevention_index",
    "home_recent_offensive_index",
    "home_recent_run_prevention_index",
    "away_recent_offensive_index",
    "away_recent_run_prevention_index",
)
E8_PREPROCESSING_VERSION = "opponent_strength_formula_v1+recent_form_formula_v1"
E11_EXPERIMENT_ID = "E3+E7+E8+E11"
E11_INFERENCE_MODEL_VERSION = "MLB-KAIZEN-E3-E7-E8-E11-INFERENCE-1.0"


@dataclass(frozen=True, slots=True)
class CalibratedInferencePrediction:
    """Run estimates plus the raw and E11-calibrated home-win probabilities."""

    run_prediction: RunPrediction
    raw_home_win_probability: float
    calibrated_home_win_probability: float


@dataclass(frozen=True, slots=True)
class CalibratedPoissonInferenceArtifact:
    """The exact model/calibrator pair evaluated under E3+E7+E8/E11."""

    model: PoissonRunModel
    calibrator: PlattCalibrator
    feature_names: tuple[str, ...]
    experiment_id: str = E11_EXPERIMENT_ID
    schema_version: str = INFERENCE_ARTIFACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "feature_names", tuple(self.feature_names))
        if self.schema_version != INFERENCE_ARTIFACT_SCHEMA_VERSION:
            raise ValueError(f"unsupported inference schema: {self.schema_version}")
        if self.experiment_id != E11_EXPERIMENT_ID:
            raise ValueError(f"unsupported inference experiment: {self.experiment_id}")
        if not isinstance(self.model, PoissonRunModel):
            raise ValueError("inference artifact requires a PoissonRunModel")
        if not isinstance(self.calibrator, PlattCalibrator):
            raise ValueError("inference artifact requires a PlattCalibrator")
        if not self.feature_names:
            raise ValueError("inference artifact requires feature names")
        if tuple(self.model.feature_names) != self.feature_names:
            raise ValueError("model feature order does not match inference artifact")

    def predict(self, features: Mapping[str, float]) -> CalibratedInferencePrediction:
        """Predict from an exactly ordered, complete E8 feature mapping."""

        actual_names = tuple(features)
        if actual_names != self.feature_names:
            missing = [name for name in self.feature_names if name not in features]
            extra = [name for name in features if name not in self.feature_names]
            if missing or extra:
                raise ValueError(
                    f"inference feature contract mismatch; missing={missing}, extra={extra}"
                )
            raise ValueError("inference feature order does not match artifact")
        try:
            normalised = {name: float(features[name]) for name in self.feature_names}
        except (TypeError, ValueError) as exc:
            raise ValueError("inference features must be numeric") from exc
        runs = self.model.predict(SimpleNamespace(features=normalised))
        raw = home_win_probability_from_runs(runs.home_expected_runs, runs.away_expected_runs)
        return CalibratedInferencePrediction(runs, raw, self.calibrator.transform(raw))


def train_e11_inference_artifact(
    final_training_rows: Sequence[HistoricalGameRow],
    calibration_training_rows: Sequence[HistoricalGameRow],
    calibration_rows: Sequence[HistoricalGameRow],
    *,
    feature_names: Sequence[str] = E8_FEATURE_NAMES,
) -> tuple[CalibratedPoissonInferenceArtifact, ModelArtifactMetadata]:
    """Fit final E8 model and E11 calibrator from temporally separate rows.

    ``calibration_training_rows`` must end before ``calibration_rows`` begins.
    The final model may include the later calibration rows, matching the E11
    protocol: a model retrained through 2025 paired with an OOS-2025 Platt
    calibrator for later inference.
    """

    final_training_rows = tuple(final_training_rows)
    calibration_training_rows = tuple(calibration_training_rows)
    calibration_rows = tuple(calibration_rows)
    names = tuple(feature_names)
    if not final_training_rows or not calibration_training_rows or not calibration_rows:
        raise ValueError("training and calibration row groups must be non-empty")
    if names != E8_FEATURE_NAMES:
        raise ValueError("E11 inference requires the exact E3+E7+E8 feature order")
    _validate_feature_contract(final_training_rows, names)
    _validate_feature_contract(calibration_training_rows, names)
    _validate_feature_contract(calibration_rows, names)
    if max(row.prediction_timestamp for row in calibration_training_rows) >= min(
        row.prediction_timestamp for row in calibration_rows
    ):
        raise ValueError("calibration training rows must be strictly earlier than calibration rows")

    calibration_model = fit_poisson_baseline(
        calibration_training_rows, feature_names=names
    )
    probabilities = []
    outcomes = []
    for row in calibration_rows:
        runs = calibration_model.predict(row)
        probabilities.append(home_win_probability_from_runs(runs.home_expected_runs, runs.away_expected_runs))
        outcomes.append(row.home_win)
    calibrator = PlattCalibrator.fit(probabilities, outcomes)
    final_model = fit_poisson_baseline(final_training_rows, feature_names=names)
    artifact = CalibratedPoissonInferenceArtifact(final_model, calibrator, names)
    metadata = ModelArtifactMetadata(
        model_version=E11_INFERENCE_MODEL_VERSION,
        feature_version=final_model.feature_version,
        training_rows=len(final_training_rows),
        training_max_prediction_timestamp=max(
            row.prediction_timestamp for row in final_training_rows
        ).isoformat(),
        library="scikit-learn",
        artifact_schema_version=INFERENCE_ARTIFACT_SCHEMA_VERSION,
        feature_names=names,
        experiment_id=E11_EXPERIMENT_ID,
        preprocessing_version=E8_PREPROCESSING_VERSION,
    )
    return artifact, metadata


def save_e11_inference_artifact(
    artifact: CalibratedPoissonInferenceArtifact,
    path: Path,
    metadata: ModelArtifactMetadata,
) -> None:
    """Persist a matching E11 artifact and metadata through the shared store."""

    _validate_artifact_metadata_pair(artifact, metadata)
    save_model_artifact(artifact, path, metadata)


def load_e11_inference_artifact(
    path: Path,
) -> tuple[CalibratedPoissonInferenceArtifact, ModelArtifactMetadata]:
    """Load a trusted E11 artifact; never retrain or silently downgrade."""

    loaded, metadata = load_model_artifact(path)
    if not isinstance(loaded, CalibratedPoissonInferenceArtifact):
        raise ValueError("artifact is not a calibrated E11 inference artifact")
    _validate_artifact_metadata_pair(loaded, metadata)
    return loaded, metadata


def _validate_feature_contract(rows: Sequence[HistoricalGameRow], names: tuple[str, ...]) -> None:
    expected = set(names)
    for row in rows:
        actual = set(row.features)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise ValueError(f"training feature contract mismatch; missing={missing}, extra={extra}")


def _validate_artifact_metadata_pair(
    artifact: CalibratedPoissonInferenceArtifact, metadata: ModelArtifactMetadata
) -> None:
    if metadata.artifact_schema_version != INFERENCE_ARTIFACT_SCHEMA_VERSION:
        raise ValueError("artifact metadata schema is incompatible")
    if metadata.experiment_id != E11_EXPERIMENT_ID:
        raise ValueError("artifact metadata experiment is incompatible")
    if tuple(metadata.feature_names) != artifact.feature_names:
        raise ValueError("artifact metadata feature order does not match model")
    if metadata.model_version != E11_INFERENCE_MODEL_VERSION:
        raise ValueError("artifact metadata model version is incompatible")
