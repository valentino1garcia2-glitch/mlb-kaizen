"""Command-line contracts for selecting trusted analysis artifacts."""

from pathlib import Path
import unittest

from mlb_kaizen.interface.cli import build_parser


class AnalyzeCommandTests(unittest.TestCase):
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
