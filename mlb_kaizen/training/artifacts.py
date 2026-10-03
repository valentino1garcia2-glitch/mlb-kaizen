"""Persist trusted model artifacts with explicit metadata."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
import pickle
from typing import Any


@dataclass(frozen=True, slots=True)
class ModelArtifactMetadata:
    model_version: str
    feature_version: str
    training_rows: int
    training_max_prediction_timestamp: str
    library: str


def save_model_artifact(model: Any, path: Path, metadata: ModelArtifactMetadata) -> None:
    """Save code/model metadata together; pickle files must only be loaded from trusted sources."""

    path.parent.mkdir(parents=True, exist_ok=True)
    model_path = path.with_suffix(path.suffix + ".pkl")
    metadata_path = path.with_suffix(path.suffix + ".json")
    with model_path.open("wb") as handle:
        pickle.dump(model, handle, protocol=pickle.HIGHEST_PROTOCOL)
    metadata_path.write_text(json.dumps(asdict(metadata), indent=2, sort_keys=True), encoding="utf-8")


def load_model_artifact(path: Path) -> tuple[Any, ModelArtifactMetadata]:
    """Load a trusted local artifact; never unpickle arbitrary downloaded files."""

    model_path = path.with_suffix(path.suffix + ".pkl")
    metadata_path = path.with_suffix(path.suffix + ".json")
    metadata = ModelArtifactMetadata(**json.loads(metadata_path.read_text(encoding="utf-8")))
    with model_path.open("rb") as handle:
        model = pickle.load(handle)
    return model, metadata
