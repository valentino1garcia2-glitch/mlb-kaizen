from datetime import UTC, date, datetime
import unittest

from mlb_kaizen.data.http import RetrievedJson
from mlb_kaizen.data.mlb_stats import MLBStatsProvider


class MLBStatsTests(unittest.TestCase):
    def test_schedule_payload_is_normalised_to_provider_independent_game(self) -> None:
        response = RetrievedJson(
            payload={
                "dates": [
                    {
                        "date": "2026-09-16",
                        "games": [
                            {
                                "gamePk": 123,
                                "gameDate": "2026-09-16T23:10:00Z",
                                "teams": {
                                    "home": {"team": {"id": 10, "name": "Home"}},
                                    "away": {"team": {"id": 20, "name": "Away"}},
                                },
                                "venue": {"name": "Test Park"},
                            }
                        ],
                    }
                ]
            },
            url="https://example.test/schedule",
            retrieved_at=datetime(2026, 9, 16, 10, tzinfo=UTC),
            from_cache=False,
        )
        games = MLBStatsProvider.parse_schedule(response, expected_date=date(2026, 9, 16))
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].game_id, "mlb:123")
        self.assertEqual(games[0].start_time, datetime(2026, 9, 16, 23, 10, tzinfo=UTC))
