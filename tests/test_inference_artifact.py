"""Contract tests for the single E3+E7+E8/E11 inference artifact."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
import tempfile
import unittest

from mlb_kaizen.training.artifacts import save_model_artifact
from mlb_kaizen.training.dataset import HistoricalGameRow
from mlb_kaizen.training.inference_artifact import (
    E8_FEATURE_NAMES,
    load_e11_inference_artifact,
    save_e11_inference_artifact,
    train_e11_inference_artifact,
)


def _rows(count: int = 18) -> list[HistoricalGameRow]:
    start = datetime(2022, 4, 1, 18, tzinfo=UTC)
    output = []
    for index in range(count):
        features = {
            name: 0.85 + ((index + offset) % 7) * 0.05
            for offset, name in enumerate(E8_FEATURE_NAMES)
        }
        output.append(HistoricalGameRow(
            game_id=f"game-{index}",
            official_date=date(2022, 4, 1) + timedelta(days=index),
            prediction_timestamp=start + timedelta(days=index),
            feature_timestamp=start + timedelta(days=index, hours=-1),
            features=features,
            home_runs=2 + index % 5,
            away_runs=1 + (index * 2) % 5,
        ))
    return output


class E11InferenceArtifactTests(unittest.TestCase):
    def _trained(self):
        rows = _rows()
        return train_e11_inference_artifact(rows, rows[:8], rows[8:14])

    def test_train_predict_save_load_preserves_calibrated_probability(self) -> None:
        artifact, metadata = self._trained()
        features = _rows(1)[0].features
        before = artifact.predict(features)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "e11-e8"
            save_e11_inference_artifact(artifact, path, metadata)
            loaded, loaded_metadata = load_e11_inference_artifact(path)
            after = loaded.predict(features)
        self.assertEqual(loaded_metadata.feature_names, E8_FEATURE_NAMES)
        self.assertAlmostEqual(before.run_prediction.home_expected_runs, after.run_prediction.home_expected_runs)
        self.assertAlmostEqual(before.run_prediction.away_expected_runs, after.run_prediction.away_expected_runs)
        self.assertAlmostEqual(before.raw_home_win_probability, after.raw_home_win_probability)
        self.assertAlmostEqual(before.calibrated_home_win_probability, after.calibrated_home_win_probability)

    def test_predict_rejects_missing_extra_and_reordered_features(self) -> None:
        artifact, _ = self._trained()
        features = _rows(1)[0].features
        missing = dict(features)
        missing.pop(E8_FEATURE_NAMES[-1])
        with self.assertRaisesRegex(ValueError, "missing"):
            artifact.predict(missing)
        extra = {**features, "unexpected": 1.0}
        with self.assertRaisesRegex(ValueError, "extra"):
            artifact.predict(extra)
        reordered = {name: features[name] for name in reversed(E8_FEATURE_NAMES)}
        with self.assertRaisesRegex(ValueError, "order"):
            artifact.predict(reordered)

    def test_predict_rejects_non_numeric_feature(self) -> None:
        artifact, _ = self._trained()
        features = dict(_rows(1)[0].features)
        features[E8_FEATURE_NAMES[0]] = "not-a-number"
        with self.assertRaisesRegex(ValueError, "numeric"):
            artifact.predict(features)

    def test_training_rejects_non_temporal_calibration_split(self) -> None:
        rows = _rows()
        with self.assertRaisesRegex(ValueError, "strictly earlier"):
            train_e11_inference_artifact(rows, rows[8:14], rows[:8])

    def test_loading_rejects_incompatible_metadata(self) -> None:
        artifact, metadata = self._trained()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad-e11"
            save_model_artifact(artifact, path, replace(metadata, experiment_id="E3-only"))
            with self.assertRaisesRegex(ValueError, "experiment"):
                load_e11_inference_artifact(path)

    def test_loading_rejects_incompatible_schema_and_feature_order(self) -> None:
        artifact, metadata = self._trained()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad-schema"
            save_model_artifact(artifact, path, replace(metadata, artifact_schema_version="other_v1"))
            with self.assertRaisesRegex(ValueError, "schema"):
                load_e11_inference_artifact(path)
            path = Path(directory) / "bad-order"
            save_model_artifact(
                artifact, path, replace(metadata, feature_names=tuple(reversed(E8_FEATURE_NAMES)))
            )
            with self.assertRaisesRegex(ValueError, "feature order"):
                load_e11_inference_artifact(path)

    def test_training_rejects_feature_contract_mismatch(self) -> None:
        rows = _rows()
        bad_features = dict(rows[0].features)
        bad_features.pop(E8_FEATURE_NAMES[-1])
        rows[0] = replace(rows[0], features=bad_features)
        with self.assertRaisesRegex(ValueError, "feature contract"):
            train_e11_inference_artifact(rows, rows[1:8], rows[8:14])


if __name__ == "__main__":
    unittest.main()
