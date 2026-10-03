import unittest
from datetime import UTC, datetime

from mlb_kaizen.data.odds import parse_sports_game_odds_response


class OddsProviderTests(unittest.TestCase):
    def test_documented_shape_is_normalised_to_market_quotes(self):
        payload = {
            "success": True,
            "data": [{
                "eventID": "evt-1",
                "odds": {
                    "points-home-game-ml-home": {
                        "oddID": "points-home-game-ml-home",
                        "periodID": "game",
                        "betTypeID": "ml",
                        "sideID": "home",
                        "byBookmaker": {
                            "book-a": {"odds": "-135", "available": True, "lastUpdatedAt": "2026-09-18T17:00:00Z"}
                        },
                    },
                    "points-all-game-ou-over": {
                        "oddID": "points-all-game-ou-over",
                        "periodID": "game",
                        "betTypeID": "ou",
                        "sideID": "over",
                        "byBookmaker": {
                            "book-a": {"odds": "-110", "overUnder": "8.5", "available": True}
                        },
                    },
                    "points-home-game-sp-home": {
                        "oddID": "points-home-game-sp-home",
                        "periodID": "game",
                        "betTypeID": "sp",
                        "sideID": "home",
                        "byBookmaker": {
                            "book-a": {"odds": "+120", "spread": "-1.5", "available": True}
                        },
                    },
                },
            }],
        }
        quotes = parse_sports_game_odds_response("evt-1", payload, datetime(2026, 9, 18, 17, tzinfo=UTC))
        self.assertEqual(len(quotes), 3)
        self.assertEqual({quote.market for quote in quotes}, {"moneyline", "total", "run_line"})
        total = next(quote for quote in quotes if quote.market == "total")
        self.assertEqual(total.line, 8.5)
        self.assertAlmostEqual(total.decimal_odds, 1.9090909, places=6)

    def test_failed_response_is_not_silently_treated_as_empty_market(self):
        with self.assertRaises(Exception):
            parse_sports_game_odds_response(
                "evt-1", {"success": False, "error": "unauthorized", "data": []}, datetime(2026, 9, 18, tzinfo=UTC)
            )
