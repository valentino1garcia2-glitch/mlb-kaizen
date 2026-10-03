import unittest
from datetime import UTC, date, datetime, timedelta

from mlb_kaizen.evaluation.calibration import PlattCalibrator, temporal_calibration_report, temporal_platt_calibration_report
from mlb_kaizen.evaluation.metrics import brier_score, log_loss, calibration_bins
from mlb_kaizen.evaluation.walk_forward import walk_forward_evaluate
from mlb_kaizen.training.dataset import HistoricalGameRow, MODEL_FEATURES
from mlb_kaizen.training.trainers import PoissonTrainer


def rows(count=50):
    base=datetime(2026,4,1,18,tzinfo=UTC)
    result=[]
    for i in range(count):
        result.append(HistoricalGameRow(
            game_id=f"g{i}", official_date=date(2026,4,1)+timedelta(days=i),
            prediction_timestamp=base+timedelta(days=i), feature_timestamp=base+timedelta(days=i,hours=-1),
            features={name:(1.0 if name=='home_advantage' else 0.9 + 0.02*((i+len(name))%5)) for name in MODEL_FEATURES},
            home_runs=4+(i%4), away_runs=3+(i%3),
        ))
    return result


class EvaluationTests(unittest.TestCase):
    def test_metrics_are_bounded(self):
        self.assertGreaterEqual(brier_score([0.7,0.2],[1,0]), 0)
        self.assertGreaterEqual(log_loss([0.7,0.2],[1,0]), 0)
        self.assertTrue(calibration_bins([0.1,0.9],[0,1]))

    def test_temporal_calibration_uses_later_evaluation_block(self):
        probabilities=[0.55,0.60,0.65,0.70,0.75,0.80,0.40,0.45,0.50,0.55]
        outcomes=[1,1,1,1,1,1,0,0,0,0]
        report=temporal_calibration_report(probabilities,outcomes,0.6)
        self.assertEqual(report.calibration_size,6)
        self.assertEqual(report.evaluation_size,4)

    def test_platt_calibrator_is_smooth_and_bounded(self):
        calibrator = PlattCalibrator.fit([0.2, 0.3, 0.7, 0.8], [0, 0, 1, 1])
        self.assertGreater(calibrator.transform(0.8), calibrator.transform(0.2))
        self.assertTrue(all(0 <= value <= 1 for value in calibrator.transform_many([0, 0.5, 1])))

    def test_platt_calibrator_rejects_single_class_training_data(self):
        with self.assertRaises(ValueError):
            PlattCalibrator.fit([0.2, 0.3], [1, 1])

    def test_temporal_platt_calibration_keeps_the_later_block_separate(self):
        report = temporal_platt_calibration_report([0.2, 0.3, 0.7, 0.8, 0.25, 0.75], [0, 0, 1, 1, 0, 1], 0.5)
        self.assertEqual(report.calibration_size, 3)
        self.assertEqual(report.evaluation_size, 3)

    def test_walk_forward_produces_only_post_training_predictions(self):
        summary=walk_forward_evaluate(rows(40), lambda: PoissonTrainer(alpha=0.5), "poisson", min_train_size=20, test_window=5, simulation_count=300)
        self.assertEqual(summary.sample_size,20)
        self.assertEqual(len(summary.predictions),20)
        self.assertGreaterEqual(summary.brier,0)
