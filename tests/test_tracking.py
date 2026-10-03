import unittest
from mlb_kaizen.tracking.human_machine import evaluate_pick, leaderboard


class TrackingTests(unittest.TestCase):
    def test_moneyline_pick_is_scored(self):
        self.assertTrue(evaluate_pick({"market":"moneyline","selection":"home"},5,3).correct)
        self.assertFalse(evaluate_pick({"market":"moneyline","selection":"away"},5,3).correct)

    def test_total_push_is_not_counted_as_correct_or_wrong(self):
        outcome=evaluate_pick({"market":"total","selection":"over","line":8.5},5,4)
        self.assertIsNotNone(outcome.correct)
        push=evaluate_pick({"market":"total","selection":"over","line":9},5,4)
        self.assertIsNone(push.correct)
        self.assertEqual(push.status,"push")

    def test_leaderboard_handles_pending_results(self):
        summary=leaderboard([{
            "game_id":"g1", "human_pick":{"market":"moneyline","selection":"home"},
            "machine_pick":{"market":"moneyline","selection":"away"}, "result":None
        }])
        self.assertEqual(summary["records"],1)
        self.assertIsNone(summary["machine_accuracy"])
