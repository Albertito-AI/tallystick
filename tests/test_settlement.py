from __future__ import annotations

import unittest

from tallystick.settlement import active_snapshot, evaluate
from fixtures_core import DEADLINE, TIME, closure, fact, market, revision


class SettlementTests(unittest.TestCase):
    def evaluate(self, facts, proposal=None, as_of="2026-10-26T22:00:00Z"):
        return evaluate(proposal or market(), facts, as_of=as_of)

    def test_missing_event_and_missing_completeness_do_not_infer_under(self):
        self.assertEqual(self.evaluate([])["reasons"], ["no_event_facts"])
        result = self.evaluate([fact()])
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["reasons"], ["missing_closure"])
        self.assertIsNone(result["outcome"])

    def test_authoritative_zero_closure_can_settle_under(self):
        result = self.evaluate([closure(0)])
        self.assertEqual((result["status"], result["count"], result["outcome"]), ("settled", 0, "under"))

    def test_complete_count_settles_and_records_all_inputs(self):
        facts = [fact(i) for i in range(6)] + [closure(6)]
        result = self.evaluate(facts)
        self.assertEqual((result["status"], result["count"], result["outcome"]), ("settled", 6, "over"))
        self.assertEqual(len(result["fact_ids"]), 7)

    def test_omitted_fact_is_detected_by_closure_count(self):
        result = self.evaluate([fact(i) for i in range(4)] + [closure(5)])
        self.assertEqual(result["reasons"], ["closure_count_mismatch"])

    def test_unofficial_input_and_unofficial_closure_are_pending(self):
        provisional = fact(state="provisional", source_ids=["feed-a"])
        self.assertEqual(self.evaluate([provisional, closure(1)])["reasons"], ["insufficient_fact_state"])
        self.assertEqual(self.evaluate([fact(), closure(1, state="provisional")])["reasons"],
                         ["insufficient_closure_state"])

    def test_multiple_closures_are_ambiguous(self):
        result = self.evaluate([closure(0, "one"), closure(0, "two")])
        self.assertEqual(result["reasons"], ["ambiguous_closure"])

    def test_official_abandonment_voids_and_provisional_one_waits(self):
        abandoned = fact("abandoned", kind="event.abandoned", period=0)
        result = self.evaluate([abandoned])
        self.assertEqual((result["status"], result["outcome"]), ("void", None))
        self.assertEqual(result["reasons"], ["event_abandoned"])
        result = self.evaluate([dict(abandoned, state="provisional")])
        self.assertEqual(result["reasons"], ["unconfirmed_abandonment"])

    def test_correction_waits_for_revised_closure_then_flips_outcome(self):
        original = [fact(i) for i in range(5)]
        closed = closure(5)
        history = original + [closed]
        self.assertEqual(self.evaluate(history)["outcome"], "over")
        corrected = revision(original[0], value=0, reason="Fictional corner rescinded")
        history.append(corrected)
        self.assertEqual(self.evaluate(history)["reasons"], ["closure_count_mismatch"])
        history.append(revision(closed, value=4, reason="Fictional revised authoritative total"))
        result = self.evaluate(history)
        self.assertEqual((result["status"], result["outcome"], result["count"]), ("settled", "under", 4))
        self.assertIn(corrected["fact_id"], result["fact_ids"])
        self.assertNotIn(original[0]["fact_id"], result["fact_ids"])

    def test_as_of_replay_excludes_future_receipts_and_corrections(self):
        original = fact()
        closed = closure(1)
        corrected = revision(original, value=0, reason="Fictional correction")
        history = [original, closed, corrected, revision(closed, value=0, reason="Updated count")]
        before = self.evaluate(history, as_of=TIME)
        after = self.evaluate(history)
        self.assertEqual((before["count"], after["count"]), (1, 0))
        self.assertEqual(self.evaluate(history, as_of="2026-10-26T20:00:00Z")["reasons"], ["no_event_facts"])

    def test_offsetting_corrections_require_a_fresh_closure_even_with_same_count(self):
        first, second, closed = fact("first"), fact("second", value=0), closure(1)
        history = [first, second, closed,
                   revision(first, value=0, reason="Withdraw incorrect occurrence"),
                   revision(second, value=1, reason="Restore a different occurrence")]
        self.assertEqual(self.evaluate(history)["reasons"], ["stale_closure"])
        self.assertEqual(self.evaluate(history, as_of=TIME)["status"], "settled")
        history.append(revision(closed))  # Equal receipt time covers both changes.
        self.assertEqual((self.evaluate(history)["status"], self.evaluate(history)["count"]), ("settled", 1))

    def test_closure_with_same_timestamp_logged_before_corrections_is_stale(self):
        first, second, closed = fact("tie-first"), fact("tie-second", value=0), closure(1)
        early_ack = revision(closed, suffix="tie-ack", received_at="2026-10-26T21:00:00Z")
        withdrawn = revision(first, value=0, reason="Fictional withdrawal")
        restored = revision(second, value=1, reason="Fictional offset")
        history = [first, second, closed, early_ack, withdrawn, restored]
        self.assertEqual(self.evaluate(history)["reasons"], ["stale_closure"])
        history.append(revision(early_ack, suffix="tie-ack-after", received_at="2026-10-26T21:00:00Z"))
        self.assertEqual((self.evaluate(history)["status"], self.evaluate(history)["count"]),
                         ("settled", 1))

    def test_state_promotions_do_not_hide_or_create_value_change_freshness_requirements(self):
        original, closed = fact(), closure(1)
        promoted = revision(original, suffix="confirmed", received_at="2026-10-26T21:10:00Z")
        self.assertEqual(self.evaluate([original, closed, promoted])["status"], "settled")
        withdrawn = revision(original, value=0, reason="Withdraw occurrence")
        restored = revision(withdrawn, suffix="restored", value=1, reason="Restore occurrence",
                            received_at="2026-10-26T21:05:00Z")
        promoted = revision(restored, suffix="confirmed", received_at="2026-10-26T21:10:00Z")
        history = [original, closed, withdrawn, restored, promoted]
        self.assertEqual(self.evaluate(history)["reasons"], ["stale_closure"])
        history.append(revision(closed, received_at="2026-10-26T21:05:00Z"))
        self.assertEqual(self.evaluate(history)["status"], "settled")

    def test_market_and_facts_must_agree_correction_deadline(self):
        result = self.evaluate([closure(0, correction_deadline="2026-10-27T23:00:00Z")])
        self.assertEqual(result["reasons"], ["correction_deadline_mismatch"])

    def test_final_state_requires_explicit_promotions(self):
        proposal = market(settlement={"fact_type": "corner.awarded", "period": 2,
                                      "threshold": 5, "min_state": "final"})
        original, closed = fact(), closure(1)
        history = [original, closed]
        self.assertEqual(self.evaluate(history, proposal, as_of=DEADLINE)["status"], "pending")
        history.extend([revision(original, state="final", received_at=DEADLINE),
                        revision(closed, state="final", received_at=DEADLINE)])
        self.assertEqual(self.evaluate(history, proposal, as_of=DEADLINE)["status"], "settled")

    def test_unrelated_events_periods_and_metrics_do_not_change_count(self):
        history = [closure(0), fact(2, period=1), fact(3, event_id="another"), fact(4, kind="goal.scored")]
        self.assertEqual(self.evaluate(history)["count"], 0)

    def test_malformed_history_and_market_are_rejected(self):
        malformed = [[fact(), fact()], [revision(fact())],
                     [fact(), revision(fact(), period=1)],
                     [fact(), revision(fact(), value=0)]]
        for history in malformed:
            with self.subTest(history=history), self.assertRaises(ValueError):
                self.evaluate(history)
        for field, value in (("threshold", True), ("period", True), ("min_state", "provisional")):
            rule = dict(market()["settlement"], **{field: value})
            with self.assertRaises(ValueError):
                self.evaluate([closure(0)], market(settlement=rule))


if __name__ == "__main__":
    unittest.main()
