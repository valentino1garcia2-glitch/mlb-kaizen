import unittest

from mlb_kaizen.market.odds import (
    american_to_decimal,
    decimal_to_implied_probability,
    edge,
    expected_value_per_unit,
    fractional_kelly,
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
