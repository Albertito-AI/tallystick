"""Batch simulations emphasize feed completeness and bounded authority."""

import unittest
from unittest.mock import patch

from tallystick.gateway import BatchSimulator, GatewayError


def mandate(name="m1", family="family-a", **changes):
    data = {"mandate_id": name, "agent_id": "agent-" + name, "model_family": family,
            "market_ids": ["corners", "goals"], "max_stake_units": 600, "budget_units": 1000,
            "valid_from_ms": 0, "valid_until_ms": 10_000, "revoked": False, "consumer": False}
    return {**data, **changes}


def intent(name="r1", authority="m1", units=100, **changes):
    return {"request_id": name, "market_id": "corners", "mandate_id": authority,
            "stake_units": units, "min_decimal_odds": "2.0", **changes}


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.sim = BatchSimulator()
        self.sim.register_mandate(mandate())

    def test_window_open_then_missing_watermark_then_close(self):
        self.sim.submit(intent(), 100)
        self.assertEqual(self.sim.close_batch(250, {"corners": "2.5"}, 249)["reason"], "WINDOW_OPEN")
        pending = self.sim.close_batch(250, {"corners": "2.5"}, 250)
        self.assertEqual(pending["status"], "PENDING")
        self.assertEqual(pending["waiting_for_sources"], ["demo-official"])
        self.sim.advance_watermark("demo-official", 250)
        final = self.sim.close_batch(250, {"corners": "2.5"}, 251)
        self.assertEqual(final["status"], "CLOSED")
        self.assertEqual(final["decisions"][0]["status"], "ACCEPTED")

    def test_delayed_625ms_feed_defeats_simple_250ms_timer(self):
        sim = BatchSimulator(required_sources=["feed-a", "feed-b"])
        sim.register_mandate(mandate())
        sim.submit(intent(), 100)
        sim.advance_watermark("feed-a", 250)
        sim.advance_watermark("feed-b", 249)
        self.assertEqual(sim.close_batch(250, {"corners": "2.5"}, 250)["status"], "PENDING")
        self.assertEqual(sim.close_batch(250, {"corners": "2.5"}, 724)["status"], "PENDING")
        sim.advance_watermark("feed-b", 250)
        closed = sim.close_batch(250, {"corners": "2.5"}, 725)
        self.assertEqual(closed["decisions"][0]["accepted_at_ms"], 725)

    def test_uniform_closing_price_and_minimum_quote(self):
        self.sim.submit(intent("r1", min_decimal_odds="2.0"), 100)
        self.sim.submit(intent("r2", min_decimal_odds="2.4"), 110)
        self.sim.submit(intent("r3", min_decimal_odds="2.6"), 120)
        self.sim.advance_watermark("demo-official", 250)
        result = self.sim.close_batch(250, {"corners": "2.5"}, 250)
        decisions = {x["request_id"]: x for x in result["decisions"]}
        self.assertEqual(decisions["r1"]["decimal_odds"], "2.5")
        self.assertEqual(decisions["r2"]["decimal_odds"], "2.5")
        self.assertEqual(decisions["r3"]["reason"], "PRICE_LIMIT")
        self.assertIsNone(decisions["r3"]["decimal_odds"])
        self.assertEqual(self.sim.exposure()["market_units"]["corners"], 200)

    def test_idempotent_submissions_do_not_double_reserve(self):
        data = intent()
        first = self.sim.submit(data, 100)
        self.assertEqual(self.sim.submit(data, 100), first)
        self.assertEqual(self.sim.exposure()["market_units"]["corners"], 100)
        self.sim.advance_watermark("demo-official", 250)
        self.sim.close_batch(250, {"corners": "2.5"}, 250)
        self.assertEqual(self.sim.submit(data, 100), first)
        self.assertEqual(self.sim.get_request("r1")["status"], "ACCEPTED")
        self.assertEqual(self.sim.exposure()["market_units"]["corners"], 100)

    def test_request_identifier_reuse_rejected(self):
        self.sim.submit(intent(), 100)
        for payload, at in ((intent(units=101), 100), (intent(), 101), (intent(min_decimal_odds="2.00"), 100)):
            with self.assertRaises(GatewayError) as context:
                self.sim.submit(payload, at)
            self.assertEqual(context.exception.code, "IDEMPOTENCY_CONFLICT")

    def test_received_at_boundary_goes_to_next_batch(self):
        self.assertEqual(self.sim.submit(intent("r1"), 249)["batch_end_ms"], 250)
        self.assertEqual(self.sim.submit(intent("r2"), 250)["batch_end_ms"], 500)
        self.sim.advance_watermark("demo-official", 500)
        self.assertEqual(self.sim.close_batch(500, {"corners": "2.5"}, 500)["reason"], "EARLIER_BATCH_PENDING")
        first = self.sim.close_batch(250, {"corners": "2.5"}, 500)
        second = self.sim.close_batch(500, {"corners": "2.5"}, 500)
        self.assertEqual([x["request_id"] for x in first["decisions"]], ["r1"])
        self.assertEqual([x["request_id"] for x in second["decisions"]], ["r2"])

    def test_split_accounts_share_model_family_cap(self):
        self.sim.register_mandate(mandate("m2"))
        self.assertEqual(self.sim.submit(intent("r1", "m1", 400), 100)["status"], "QUEUED")
        second = self.sim.submit(intent("r2", "m2", 300, market_id="goals"), 101)
        self.assertEqual(second["reason"], "FAMILY_CAP")
        self.assertEqual(self.sim.exposure()["family_units"]["family-a"], 400)

    def test_market_cap_across_different_model_families(self):
        self.sim.register_mandate(mandate("m2", "family-b"))
        self.sim.submit(intent("r1", "m1", 600), 100)
        second = self.sim.submit(intent("r2", "m2", 500), 101)
        self.assertEqual(second["reason"], "MARKET_CAP")
        self.assertEqual(self.sim.exposure()["market_units"]["corners"], 600)

    def test_budget_and_single_request_limits(self):
        self.sim.register_mandate(mandate("small", "small-family", budget_units=150, max_stake_units=100))
        self.assertEqual(self.sim.submit(intent("large", "small", 101), 10)["reason"], "STAKE_LIMIT")
        self.assertEqual(self.sim.submit(intent("within", "small", 100), 20)["status"], "QUEUED")
        self.assertEqual(self.sim.submit(intent("over", "small", 51), 30)["reason"], "MANDATE_BUDGET")

    def test_revocation_before_close_releases_reservation(self):
        self.sim.submit(intent(), 100)
        self.sim.revoke("m1")
        self.sim.advance_watermark("demo-official", 250)
        result = self.sim.close_batch(250, {"corners": "2.5"}, 250)
        self.assertEqual(result["decisions"][0]["reason"], "MANDATE_REVOKED")
        self.assertEqual(self.sim.exposure()["market_units"]["corners"], 0)
        self.assertEqual(self.sim.exposure()["family_units"]["family-a"], 0)
        self.assertEqual(self.sim.exposure()["mandate_units"]["m1"], 0)
        with self.assertRaises(GatewayError):
            self.sim.register_mandate(mandate())

    def test_expiry_checked_at_actual_delayed_close(self):
        self.sim.register_mandate(mandate("expiring", "expiring-family", valid_until_ms=400))
        self.sim.submit(intent(authority="expiring"), 100)
        self.sim.advance_watermark("demo-official", 250)
        result = self.sim.close_batch(250, {"corners": "2.5"}, 725)
        self.assertEqual(result["decisions"][0]["reason"], "MANDATE_NOT_CURRENT")
        self.assertEqual(self.sim.exposure()["mandate_units"]["expiring"], 0)

    def test_unknown_and_forbidden_mandates(self):
        self.assertEqual(self.sim.submit(intent("unknown", "absent"), 100)["reason"], "UNKNOWN_MANDATE")
        self.assertEqual(self.sim.submit(intent("wrong-market", market_id="tennis"), 101)["reason"], "MARKET_NOT_PERMITTED")
        self.sim.register_mandate(mandate("future", "future-family", valid_from_ms=500))
        self.assertEqual(self.sim.submit(intent("too-soon", "future"), 102)["reason"], "MANDATE_NOT_CURRENT")

    def test_missing_quote_rejects_and_releases(self):
        self.sim.submit(intent(), 100)
        self.sim.advance_watermark("demo-official", 250)
        result = self.sim.close_batch(250, {}, 250)
        self.assertEqual(result["decisions"][0]["reason"], "MISSING_QUOTE")
        self.assertEqual(self.sim.exposure()["market_units"]["corners"], 0)

    def test_close_retry_cannot_reprice(self):
        self.sim.submit(intent(), 100)
        self.sim.advance_watermark("demo-official", 250)
        first = self.sim.close_batch(250, {"corners": "2.5"}, 250)
        self.assertEqual(self.sim.close_batch(250, {"corners": "2.5"}, 500), first)
        with self.assertRaises(GatewayError) as context:
            self.sim.close_batch(250, {"corners": "3.0"}, 500)
        self.assertEqual(context.exception.code, "BATCH_CONFLICT")

    def test_late_fact_halts_future_acceptance_without_erasing_records(self):
        self.sim.submit(intent(), 100)
        self.sim.advance_watermark("demo-official", 250)
        self.sim.close_batch(250, {"corners": "2.5"}, 250)
        incident = self.sim.observe_late("demo-official", 120)
        self.assertEqual(incident["status"], "HALTED")
        self.assertEqual(self.sim.get_request("r1")["status"], "ACCEPTED")
        self.assertEqual(self.sim.submit(intent("r2"), 300)["reason"], "GLOBAL_HALT")
        self.assertEqual(self.sim.close_batch(500, {"corners": "2.5"}, 500)["status"], "HALTED")
        self.assertEqual(self.sim.exposure()["market_units"]["corners"], 100)

    def test_late_fact_with_no_closed_batch_is_recorded(self):
        self.assertEqual(self.sim.observe_late("demo-official", 0)["status"], "RECORDED")
        self.assertFalse(self.sim.halted)

    def test_returned_records_cannot_mutate_simulator(self):
        original = mandate("new", "new-family")
        copied = self.sim.register_mandate(original)
        original["budget_units"] = 100000
        copied["revoked"] = True
        received = self.sim.submit(intent(authority="new"), 100)
        received["status"] = "ACCEPTED"
        self.assertEqual(self.sim.get_request("r1")["status"], "QUEUED")
        exposure = self.sim.exposure()
        exposure["market_units"]["corners"] = 0
        self.assertEqual(self.sim.exposure()["market_units"]["corners"], 100)

    def test_closed_batch_order_cannot_move_backwards(self):
        self.sim.advance_watermark("demo-official", 500)
        self.sim.close_batch(500, {}, 500)
        with self.assertRaises(GatewayError) as context:
            self.sim.close_batch(250, {}, 600)
        self.assertEqual(context.exception.code, "BATCH_ORDER")

    def test_replay_order_is_deterministic(self):
        def replay():
            sim = BatchSimulator()
            sim.register_mandate(mandate())
            for i in range(4):
                sim.submit(intent("r" + str(i)), 100 + i)
            sim.advance_watermark("demo-official", 250)
            return sim.close_batch(250, {"corners": "2.5"}, 250)
        self.assertEqual(replay(), replay())

    def test_ordering_preserves_identifier_boundaries(self):
        requests = [intent("a:b", market_id="c"), intent("a", market_id="b:c")]

        def order(payloads):
            sim = BatchSimulator()
            sim.register_mandate(mandate(market_ids=["c", "b:c"]))
            for payload in payloads:
                sim.submit(payload, 100)
            sim.advance_watermark("demo-official", 250)
            closed = sim.close_batch(250, {"c": "2.5", "b:c": "2.5"}, 250)
            return [record["request_id"] for record in closed["decisions"]]

        self.assertEqual(order(requests), order(list(reversed(requests))))

    def test_empty_batch_history_is_bounded(self):
        with patch("tallystick.gateway._MAX_REQUESTS", 1):
            self.sim.advance_watermark("demo-official", 500)
            self.sim.close_batch(250, {}, 250)
            with self.assertRaises(GatewayError) as context:
                self.sim.close_batch(500, {}, 500)
            self.assertEqual(context.exception.code, "CAPACITY_REACHED")


class ValidationTests(unittest.TestCase):
    def test_constructor_caps_and_identifiers(self):
        for kwargs in ({"window_ms": True}, {"window_ms": 0}, {"required_sources": []}, {"required_sources": ["same", "same"]}, {"max_family_units": -1}, {"max_market_units": 1.5}):
            with self.assertRaises(GatewayError):
                BatchSimulator(**kwargs)

    def test_strict_mandate_fields_and_consumer_boundary(self):
        for data in (mandate(extra="unknown"), mandate(consumer=True), mandate(revoked=1), mandate(max_stake_units=True), mandate(valid_until_ms=0), mandate(market_ids=["corners", "corners"])):
            with self.assertRaises(GatewayError):
                BatchSimulator().register_mandate(data)

    def test_strict_request_shape(self):
        sim = BatchSimulator()
        sim.register_mandate(mandate())
        for data, at in ((intent(extra="unknown"), 100), (intent(units=True), 100), (intent(), True), (intent(), -1), (intent(name="has spaces"), 100)):
            with self.assertRaises(GatewayError):
                sim.submit(data, at)

    def test_quotes_and_minimum_odds_require_bounded_decimal_strings(self):
        for value in (2.5, True, "NaN", "Infinity", "1e5", "0.9", "1000000001", "2.1234567890123", "1" * 33):
            sim = BatchSimulator()
            sim.register_mandate(mandate())
            with self.assertRaises(GatewayError):
                sim.submit(intent(min_decimal_odds=value), 100)
            with self.assertRaises(GatewayError):
                sim.close_batch(250, {"corners": value}, 250)

    def test_source_identity_and_monotonic_watermarks(self):
        sim = BatchSimulator()
        with self.assertRaises(GatewayError):
            sim.advance_watermark("unknown", 500)
        sim.advance_watermark("demo-official", 500)
        with self.assertRaises(GatewayError) as context:
            sim.advance_watermark("demo-official", 499)
        self.assertEqual(context.exception.code, "WATERMARK_REGRESSION")
        with self.assertRaises(GatewayError):
            sim.observe_late("unknown", 100)

    def test_arrival_and_close_times_cannot_move_backwards(self):
        sim = BatchSimulator()
        sim.register_mandate(mandate())
        sim.submit(intent(), 100)
        with self.assertRaises(GatewayError):
            sim.submit(intent("r2"), 99)
        with self.assertRaises(GatewayError):
            sim.close_batch(250, {}, 99)
        with self.assertRaises(GatewayError):
            sim.close_batch(251, {}, 251)


if __name__ == "__main__":
    unittest.main()
