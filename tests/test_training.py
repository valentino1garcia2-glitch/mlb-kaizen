import unittest
from datetime import UTC, date, datetime, timedelta
import tempfile
from pathlib import Path

from mlb_kaizen.training.dataset import HistoricalGameRow, MODEL_FEATURES, load_jsonl, save_jsonl
from mlb_kaizen.training.trainers import PoissonTrainer, RandomForestTrainer


def rows(count=40):
    base = datetime(2026, 4, 1, 18, tzinfo=UTC)
    out = []
    for i in range(count):
        features = {
            "home_offensive_index": 0.90 + (i % 5) * 0.05,
            "away_offensive_index": 0.90 + ((i + 1) % 5) * 0.05,
            "home_run_prevention_index": 0.92 + ((i + 2) % 4) * 0.04,
            "away_run_prevention_index": 0.92 + ((i + 3) % 4) * 0.04,
            "home_advantage": 1.0,
        }
        out.append(HistoricalGameRow(
            game_id=f"g{i}", official_date=(date(2026,4,1)+timedelta(days=i//2)),
            prediction_timestamp=base + timedelta(days=i),
            feature_timestamp=base + timedelta(days=i, hours=-1),
            features=features, home_runs=4 + i % 4, away_runs=3 + (i+1)%3,
        ))
    return out


class TrainingTests(unittest.TestCase):
    def test_future_feature_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            HistoricalGameRow(
                "g", date(2026, 4, 1), datetime(2026,4,1,18,tzinfo=UTC), datetime(2026,4,1,19,tzinfo=UTC),
                {name: 1.0 for name in MODEL_FEATURES}, 4, 3,
            )

    def test_jsonl_roundtrip_is_deterministic(self):
        dataset = rows(5)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/"dataset.jsonl"
            save_jsonl(path, dataset)
            loaded = load_jsonl(path)
        self.assertEqual(tuple(dataset), loaded)

    def test_poisson_trainer_fits_and_predicts_positive_runs(self):
        model = PoissonTrainer(alpha=0.5).fit(rows(40))
        prediction = model.predict(rows(1)[0])
        self.assertGreater(prediction.home_expected_runs, 0)
        self.assertGreater(prediction.away_expected_runs, 0)

    def test_random_forest_trainer_fits_and_predicts(self):
        model = RandomForestTrainer(random_seed=7).fit(rows(40))
        prediction = model.predict(rows(1)[0])
        self.assertGreater(prediction.home_expected_runs, 0)
        self.assertGreater(prediction.away_expected_runs, 0)

    def test_poisson_trainer_uses_a_custom_feature_set_when_given_one(self) -> None:
        base_rows = rows()
        extended = []
        for i, row in enumerate(base_rows):
            features = dict(row.features)
            features["extra_signal"] = float(i % 3)
            extended.append(HistoricalGameRow(
                game_id=row.game_id, official_date=row.official_date,
                prediction_timestamp=row.prediction_timestamp, feature_timestamp=row.feature_timestamp,
                features=features, home_runs=row.home_runs, away_runs=row.away_runs,
            ))
        extended_features = MODEL_FEATURES + ("extra_signal",)
        trainer = PoissonTrainer(feature_names=extended_features).fit(extended)
        self.assertEqual(trainer.model.feature_names, extended_features)
        self.assertGreater(trainer.predict(extended[0]).home_expected_runs, 0)

    def test_default_feature_names_still_match_model_features(self) -> None:
        trainer = PoissonTrainer()
        self.assertEqual(trainer.feature_names, MODEL_FEATURES)
        trainer.fit(rows())
        self.assertEqual(trainer.model.feature_names, MODEL_FEATURES)
