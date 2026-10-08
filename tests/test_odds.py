import unittest
from datetime import UTC, datetime

from mlb_kaizen.market.odds import (
    american_to_decimal,
    decimal_to_implied_probability,
    edge,
    expected_value_per_unit,
    fractional_kelly,
    latest_complete_no_vig_snapshot,
    proportional_no_vig,
)


class OddsTests(unittest.TestCase):
    def test_odds_conversions_and_value_are_explicit(self) -> None:
        self.assertEqual(american_to_decimal(150), 2.5)
        self.assertEqual(american_to_decimal(-200), 1.5)
        self.assertEqual(decimal_to_implied_probability(2.0), 0.5)
        self.assertAlmostEqual(edge(0.55, 0.50), 0.05)
        self.assertAlmostEqual(expected_value_per_unit(0.55, 2.0), 0.10)
        self.assertAlmostEqual(fractional_kelly(0.55, 2.0, 0.25), 0.025)

    def test_proportional_no_vig_normalises_two_sided_market(self) -> None:
        result = proportional_no_vig({"home": 1.8, "away": 2.2})
        self.assertAlmostEqual(sum(result.values()), 1.0)
        self.assertGreater(result["home"], result["away"])

    def test_invalid_odds_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            american_to_decimal(0)
        for odds in (1, -1):
            with self.assertRaises(ValueError):
                decimal_to_implied_probability(odds)

    def test_latest_complete_no_vig_snapshot_never_mixes_quote_times(self) -> None:
        quotes = [
            {"sportsbook": "Playdoit", "market": "moneyline", "selection": "away", "line": None,
             "decimal_odds": 2.2, "captured_at": "2026-10-07T01:25:00+00:00"},
            {"sportsbook": "Playdoit", "market": "moneyline", "selection": "home", "line": None,
             "decimal_odds": 1.6666667, "captured_at": "2026-10-07T01:25:00+00:00"},
            {"sportsbook": "Playdoit", "market": "moneyline", "selection": "away", "line": None,
             "decimal_odds": 2.1, "captured_at": "2026-10-07T01:29:00+00:00"},
        ]

        snapshot = latest_complete_no_vig_snapshot(quotes, market="moneyline")

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.observed_at, datetime(2026, 10, 7, 1, 25, tzinfo=UTC))
        self.assertAlmostEqual(snapshot.probabilities["away"], 0.4310345)
        self.assertAlmostEqual(sum(snapshot.probabilities.values()), 1.0)

    def test_latest_complete_no_vig_snapshot_uses_newest_complete_pair(self) -> None:
        quotes = [
            {"sportsbook": "Playdoit", "market": "total", "selection": "over", "line": 7.5,
             "decimal_odds": 1.91, "captured_at": "2026-10-07T01:25:00+00:00"},
            {"sportsbook": "Playdoit", "market": "total", "selection": "under", "line": 7.5,
             "decimal_odds": 1.87, "captured_at": "2026-10-07T01:25:00+00:00"},
            {"sportsbook": "Playdoit", "market": "total", "selection": "over", "line": 7.5,
             "decimal_odds": 1.8, "captured_at": "2026-10-07T01:29:00+00:00"},
            {"sportsbook": "Playdoit", "market": "total", "selection": "under", "line": 7.5,
             "decimal_odds": 2.1, "captured_at": "2026-10-07T01:29:00+00:00"},
        ]

        snapshot = latest_complete_no_vig_snapshot(quotes, market="total")

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.observed_at, datetime(2026, 10, 7, 1, 29, tzinfo=UTC))
        self.assertEqual(snapshot.line, 7.5)
        self.assertGreater(snapshot.probabilities["over"], snapshot.probabilities["under"])

    def test_latest_complete_no_vig_snapshot_rejects_unknown_market(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported two-sided market"):
            latest_complete_no_vig_snapshot([], market="futures")
