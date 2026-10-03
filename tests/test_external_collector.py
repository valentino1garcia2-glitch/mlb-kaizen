from pathlib import Path
import tempfile
import unittest

from mlb_kaizen.training.external_collector import load_completed_games_from_collector

# Two real lines taken verbatim from the user's Colab-collected dataset
# (normalized/historical/2022/games.jsonl), audited in HANDOFF.md section 21.
REAL_LINE_1 = (
    '{"record_type":"mlb_game","schema_version":"1.0","game_id":"663178","season":2022,'
    '"game_type":"R","official_date":"2022-04-07","game_datetime":"2022-04-07T18:20:00Z",'
    '"status":"Final","status_code":"F","home_team":{"id":112,"name":"Chicago Cubs","abbreviation":"CHC"},'
    '"away_team":{"id":158,"name":"Milwaukee Brewers","abbreviation":"MIL"},"score":{"home":5,"away":4},'
    '"probable_pitchers":{"home":{"id":543294,"full_name":"Kyle Hendricks"},'
    '"away":{"id":669203,"full_name":"Corbin Burnes"}},"venue":{"id":17,"name":"Wrigley Field"},'
    '"linescore_present":true,"collection":{"query_start":"2022-04-01","query_end":"2022-04-30",'
    '"source":"MLB_STATS_API","retrieved_at":"2026-09-19T09:01:01.907668+00:00",'
    '"request_url":"https://statsapi.mlb.com/api/v1/schedule?sportId=1\\u0026startDate=2022-04-01'
    '\\u0026endDate=2022-04-30\\u0026gameType=R\\u0026hydrate=team%2Clinescore%2CprobablePitcher",'
    '"raw_sha256":"f2a0538cb668f52713d0d878434f4d8345e8724fc30302fe0357628cd977ed3e"}}'
)
REAL_LINE_PREVIEW = (
    '{"record_type":"mlb_game","schema_version":"1.0","game_id":"999001","season":2026,'
    '"game_type":"R","official_date":"2026-09-20","game_datetime":"2026-09-20T23:05:00Z",'
    '"status":"Preview","status_code":"S","home_team":{"id":112,"name":"Chicago Cubs","abbreviation":"CHC"},'
    '"away_team":{"id":158,"name":"Milwaukee Brewers","abbreviation":"MIL"},"score":{"home":null,"away":null},'
    '"probable_pitchers":{"home":{},"away":{}},"venue":{"id":17,"name":"Wrigley Field"},'
    '"linescore_present":false,"collection":{"query_start":"2026-09-01","query_end":"2026-09-19",'
    '"source":"MLB_STATS_API","retrieved_at":"2026-09-19T09:01:01.907668+00:00",'
    '"request_url":"https://example.test","raw_sha256":"deadbeef"}}'
)
REAL_LINE_FINAL_NO_SCORE = (
    '{"record_type":"mlb_game","schema_version":"1.0","game_id":"999002","season":2022,'
    '"game_type":"R","official_date":"2022-04-07","game_datetime":"2022-04-07T18:20:00Z",'
    '"status":"Final","status_code":"DI","home_team":{"id":112,"name":"Chicago Cubs","abbreviation":"CHC"},'
    '"away_team":{"id":158,"name":"Milwaukee Brewers","abbreviation":"MIL"},"score":{"home":null,"away":null},'
    '"probable_pitchers":{"home":{},"away":{}},"venue":{"id":17,"name":"Wrigley Field"},'
    '"linescore_present":false,"collection":{"query_start":"2022-04-01","query_end":"2022-04-30",'
    '"source":"MLB_STATS_API","retrieved_at":"2026-09-19T09:01:01.907668+00:00",'
    '"request_url":"https://example.test","raw_sha256":"deadbeef"}}'
)


class ExternalCollectorLoaderTests(unittest.TestCase):
    def test_real_final_scored_row_is_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "games.jsonl"
            path.write_text(REAL_LINE_1 + "\n", encoding="utf-8")
            games = load_completed_games_from_collector([path])
        self.assertEqual(len(games), 1)
        game = games[0]
        self.assertEqual(game.game_id, "mlb:663178")
        self.assertEqual(game.home_team_id, "112")
        self.assertEqual(game.away_team_id, "158")
        self.assertEqual(game.home_runs, 5)
        self.assertEqual(game.away_runs, 4)
        self.assertEqual(game.official_date.isoformat(), "2022-04-07")

    def test_preview_status_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "games.jsonl"
            path.write_text(REAL_LINE_PREVIEW + "\n", encoding="utf-8")
            games = load_completed_games_from_collector([path])
        self.assertEqual(games, [])

    def test_final_status_without_score_is_excluded_not_guessed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "games.jsonl"
            path.write_text(REAL_LINE_FINAL_NO_SCORE + "\n", encoding="utf-8")
            games = load_completed_games_from_collector([path])
        self.assertEqual(games, [])

    def test_multiple_files_are_combined(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path_a = Path(tmp) / "a.jsonl"
            path_b = Path(tmp) / "b.jsonl"
            path_a.write_text(REAL_LINE_1 + "\n", encoding="utf-8")
            path_b.write_text(REAL_LINE_PREVIEW + "\n" + REAL_LINE_FINAL_NO_SCORE + "\n", encoding="utf-8")
            games = load_completed_games_from_collector([path_a, path_b])
        self.assertEqual(len(games), 1)

    def test_unexpected_schema_version_raises(self) -> None:
        bad = REAL_LINE_1.replace('"schema_version":"1.0"', '"schema_version":"2.0"')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "games.jsonl"
            path.write_text(bad + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_completed_games_from_collector([path])

    def test_duplicate_game_id_across_files_is_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path_a = Path(tmp) / "a.jsonl"
            path_b = Path(tmp) / "b.jsonl"
            path_a.write_text(REAL_LINE_1 + "\n", encoding="utf-8")
            path_b.write_text(REAL_LINE_1 + "\n", encoding="utf-8")
            games = load_completed_games_from_collector([path_a, path_b])
        self.assertEqual(len(games), 1)


if __name__ == "__main__":
    unittest.main()
