"""Command-line contracts for selecting trusted analysis artifacts."""

from pathlib import Path
from datetime import date
import unittest

from mlb_kaizen.interface.cli import build_parser


class AnalyzeCommandTests(unittest.TestCase):
    def test_manual_market_quote_requires_observed_timestamp_and_one_price_format(self) -> None:
        args = build_parser().parse_args([
            "record-market-quote", "--game-id", "mlb:123", "--sportsbook", "Playdoit",
            "--market", "moneyline", "--selection", "away", "--american-odds", "+120",
            "--observed-at", "2026-10-07T01:25:00+00:00",
        ])
        self.assertEqual(args.game_id, "mlb:123")
        self.assertEqual(args.american_odds, 120.0)
        self.assertIsNone(args.decimal_odds)

    def test_analyze_accepts_explicit_trained_model_and_calibrator_paths(self) -> None:
        args = build_parser().parse_args(
            [
                "analyze",
                "--input", "game.json",
                "--trained-model", "artifacts/e3",
                "--calibrator", "artifacts/platt",
            ]
        )

        self.assertEqual(args.trained_model, Path("artifacts/e3"))
        self.assertEqual(args.calibrator, Path("artifacts/platt"))

    def test_analyze_leaves_trained_artifacts_optional(self) -> None:
        args = build_parser().parse_args(["analyze", "--input", "game.json"])

        self.assertIsNone(args.trained_model)
        self.assertIsNone(args.calibrator)

    def test_e11_artifact_commands_require_explicit_inputs(self) -> None:
        parser = build_parser()
        train = parser.parse_args([
            "train-e11-inference", "--training-dataset", "all.jsonl",
            "--calibration-training-dataset", "earlier.jsonl",
            "--calibration-dataset", "calibration.jsonl", "--output", "artifact/e11",
        ])
        predict = parser.parse_args([
            "predict-e11-inference", "--artifact", "artifact/e11", "--features", "game.json",
        ])
        self.assertEqual(train.output, Path("artifact/e11"))
        self.assertEqual(predict.features, Path("game.json"))

    def test_daily_e11_inference_requires_live_scope_and_trusted_artifact(self) -> None:
        args = build_parser().parse_args([
            "daily-e11-inference", "--date", "2026-06-01", "--game-id", "mlb:123",
            "--history-start", "2022-03-01", "--artifact", "artifacts/e11",
        ])
        self.assertEqual(args.date, date(2026, 6, 1))
        self.assertEqual(args.history_start, date(2022, 3, 1))
        self.assertEqual(args.artifact, Path("artifacts/e11"))
