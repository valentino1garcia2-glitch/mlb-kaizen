from datetime import UTC, datetime
import json
from pathlib import Path
import tempfile
import unittest

from mlb_kaizen.data.historical_results import load_completed_game_results, save_completed_game_results
from tests.conftest import completed_game


class HistoricalResultsTests(unittest.TestCase):
    def _postseason_result(self):
        base = completed_game(game_id="mlb:900", start_time=datetime(2025, 10, 4, 20, tzinfo=UTC))
        return type(base)(
            game_id=base.game_id, official_date=base.official_date, start_time=base.start_time,
            home_team_id=base.home_team_id, home_team_name=base.home_team_name,
            away_team_id=base.away_team_id, away_team_name=base.away_team_name,
            home_runs=base.home_runs, away_runs=base.away_runs, provenance=base.provenance,
            game_type="D",
        )

    def test_round_trip_preserves_game_type_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "official_results.jsonl"
            result = self._postseason_result()
            self.assertEqual(save_completed_game_results(output, [result]), 1)
            loaded = load_completed_game_results(output)
        self.assertEqual(loaded, (result,))
        self.assertEqual(loaded[0].game_type, "D")

    def test_refuses_to_overwrite_a_previous_collection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "official_results.jsonl"
            save_completed_game_results(output, [self._postseason_result()])
            with self.assertRaises(FileExistsError):
                save_completed_game_results(output, [self._postseason_result()])

    def test_rejects_an_incompatible_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "official_results.jsonl"
            output.write_text(json.dumps({"schema_version": "999", "record_type": "completed_game_result"}) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported completed-game result schema"):
                load_completed_game_results(output)

    def test_rejects_duplicate_game_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "official_results.jsonl"
            result = self._postseason_result()
            with self.assertRaisesRegex(ValueError, "duplicate completed-game id"):
                save_completed_game_results(output, [result, result])
