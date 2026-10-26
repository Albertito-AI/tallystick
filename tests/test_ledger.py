from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from tallystick.crypto import (SigningKey, canonical_json, inclusion_proof,
                              merkle_root, verify_bundle, verify_inclusion,
                              verify_signature)
from tallystick.ledger import Ledger, LedgerError
from fixtures_core import DEADLINE, TIME, fact, revision, sources


class CryptoTests(unittest.TestCase):
    def test_signatures_require_the_pinned_key_and_unchanged_payload(self):
        key = SigningKey.generate()
        message = {"a": 1, "label": "fictional"}
        signature = key.sign(message)
        self.assertTrue(verify_signature(message, signature, key.public_key_hex))
        self.assertFalse(verify_signature(dict(message, a=2), signature, key.public_key_hex))
        self.assertFalse(verify_signature(message, signature, SigningKey.generate().public_key_hex))
        self.assertFalse(verify_signature(message, "00" * 64, key.public_key_hex))

    def test_merkle_all_positions_in_unbalanced_and_balanced_trees(self):
        for size in range(1, 40):
            leaves = [f"fixture-{i}".encode() for i in range(size)]
            root = merkle_root(leaves)
            for index in range(size):
                with self.subTest(size=size, index=index):
                    proof = inclusion_proof(leaves, index)
                    self.assertTrue(verify_inclusion(leaves[index], proof, root))
                    self.assertFalse(verify_inclusion(b"changed", proof, root))
                    changed_size = copy.deepcopy(proof)
                    changed_size["tree_size"] = 0
                    self.assertFalse(verify_inclusion(leaves[index], changed_size, root))

    def test_merkle_path_and_position_are_bound(self):
        leaves = [b"a", b"b", b"c"]
        proof = inclusion_proof(leaves, 1)
        proof["index"] = 0
        self.assertFalse(verify_inclusion(b"b", proof, merkle_root(leaves)))
        proof = inclusion_proof(leaves, 1)
        proof["audit_path"].append({"side": "right", "hash": "00" * 32})
        self.assertFalse(verify_inclusion(b"b", proof, merkle_root(leaves)))

    def test_noncanonical_or_unbounded_json_is_rejected(self):
        for value in ({1: "x"}, {"x": float("nan")}, {"x": float("inf")}, 2**60, object()):
            with self.assertRaises(ValueError):
                canonical_json(value)
        self.assertEqual(canonical_json({"b": 1, "a": "x"}), b'{"a":"x","b":1}')


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.key = SigningKey.generate()
        self.ledger = Ledger(":memory:", self.key, sources())

    def tearDown(self):
        self.ledger.close()

    def append(self, item, key=None):
        return self.ledger.append_fact(item, key or item["fact_id"], recorded_at=item["received_at"])

    def test_fact_receipt_has_valid_signature_and_inclusion_proof(self):
        entry = self.append(fact())
        self.assertEqual(entry["sequence"], 1)
        self.assertTrue(self.ledger.verify(self.key.public_key_hex)["valid"])
        bundle = self.ledger.inclusion_proof(1)
        self.assertTrue(verify_bundle(bundle, self.key.public_key_hex))
        self.assertFalse(verify_bundle(bundle, SigningKey.generate().public_key_hex))
        bundle["entry"]["payload"]["value"] = 0
        self.assertFalse(verify_bundle(bundle, self.key.public_key_hex))

    def test_checkpoint_key_cannot_replace_external_trust(self):
        self.append(fact())
        bundle = self.ledger.inclusion_proof(1)
        impostor = SigningKey.generate()
        bundle["checkpoint"]["public_key"] = impostor.public_key_hex
        self.assertFalse(verify_bundle(bundle, self.key.public_key_hex))

    def test_malformed_inclusion_bundles_fail_without_raising(self):
        self.append(fact())
        original = self.ledger.inclusion_proof(1)
        for field in ("entry", "proof", "checkpoint"):
            for invalid in (None, [], "not-an-object", 3):
                bundle = copy.deepcopy(original)
                bundle[field] = invalid
                with self.subTest(field=field, invalid=invalid):
                    self.assertFalse(verify_bundle(bundle, self.key.public_key_hex))

    def test_retry_is_exactly_once_and_changed_retry_is_a_conflict(self):
        original = self.append(fact(), "request-1")
        retry = self.ledger.append_fact(fact(), "request-1", recorded_at="2026-10-26T22:00:00Z")
        self.assertEqual(original, retry)
        with self.assertRaises(LedgerError) as raised:
            self.append(fact(value=0), "request-1")
        self.assertEqual(raised.exception.code, "IDEMPOTENCY_CONFLICT")
        self.assertEqual(len(self.ledger.entries()), 1)

    def test_concurrent_retries_share_one_record(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.append(fact(), "same-request"), range(24)))
        self.assertEqual({record["sequence"] for record in results}, {1})
        self.assertEqual(len(self.ledger.entries()), 1)
        self.assertTrue(self.ledger.verify(self.key.public_key_hex)["valid"])

    def test_source_authority_and_independence_are_enforced(self):
        cases = [fact(source_ids=["missing"]), fact(source_ids=["feed-a"]),
                 fact(state="corroborated", source_ids=["feed-a", "feed-a-copy"])]
        for item in cases:
            with self.assertRaises(LedgerError):
                self.append(item)
        self.append(fact(state="corroborated", source_ids=["feed-a", "feed-b"]))
        self.assertEqual(len(self.ledger.entries()), 1)

    def test_corrected_fact_preserves_history_and_updates_only_current_head(self):
        original = fact()
        self.append(original)
        corrected = revision(original, value=0, reason="Fictional reclassification")
        self.append(corrected)
        self.assertEqual(len(self.ledger.facts()), 2)
        self.assertEqual(self.ledger.active_facts()[0]["value"], 0)
        self.assertTrue(self.ledger.verify(self.key.public_key_hex)["valid"])
        branch = revision(original, suffix="branch", value=0, reason="Another correction")
        with self.assertRaises(LedgerError):
            self.append(branch)
        self.assertEqual(len(self.ledger.entries()), 2)

    def test_correction_needs_reason_and_cannot_move_identity_or_deadline(self):
        original = fact()
        self.append(original)
        cases = [revision(original, value=0),
                 revision(original, event_id="another-match"),
                 revision(original, correction_deadline="2027-01-01T00:00:00Z"),
                 revision(original, licence_id="different-licence"),
                 revision(original, period=1),
                 revision(original, occurred_at="2026-10-26T19:00:00Z")]
        for item in cases:
            with self.subTest(item=item), self.assertRaises(LedgerError):
                self.append(item)
        self.assertEqual(len(self.ledger.entries()), 1)

    def test_late_correction_and_premature_finality_fail(self):
        original = fact()
        self.append(original)
        with self.assertRaises(LedgerError):
            self.append(revision(original, value=0, reason="Too late", received_at=DEADLINE))
        with self.assertRaises(LedgerError):
            self.append(revision(original, state="final"))
        final = revision(original, state="final", received_at=DEADLINE)
        self.append(final)
        with self.assertRaises(LedgerError):
            self.append(revision(final, suffix="v3", received_at="2026-10-27T00:00:00Z"))
        self.assertEqual(len(self.ledger.entries()), 2)

    def test_backdated_receipt_does_not_reopen_a_closed_correction_window(self):
        original = fact()
        self.append(original)
        correction = revision(original, value=0, reason="Late arrival with an earlier receipt claim")
        with self.assertRaises(LedgerError):
            self.ledger.append_fact(correction, "late-recording", recorded_at=DEADLINE)
        self.assertEqual(len(self.ledger.entries()), 1)

    def test_unchanged_state_regression_fails_but_correction_reopens_review(self):
        original = fact()
        self.append(original)
        with self.assertRaises(LedgerError):
            self.append(revision(original, state="provisional", source_ids=["feed-a"]))
        self.append(revision(original, state="provisional", source_ids=["feed-a"],
                             value=0, reason="Fictional disputed reclassification"))
        self.assertEqual(self.ledger.active_facts()[0]["state"], "provisional")

    def test_time_order_and_strict_schema_are_enforced(self):
        bad = [fact(value=True), fact(period=True), fact(extra="unexpected"),
               fact(received_at="2026-10-26T19:00:00Z"),
               fact(received_at="2026-W44-1T20:30:00Z")]
        for item in bad:
            with self.assertRaises(LedgerError):
                self.append(item)
        with self.assertRaises(LedgerError):
            self.ledger.append_fact(fact(), "early", recorded_at="2026-10-26T20:00:00Z")
        self.append(fact())
        with self.assertRaises(LedgerError):
            self.ledger.append("audit", {}, "backwards", recorded_at="2026-10-26T19:00:00Z")

    def test_duplicate_fact_under_another_request_cannot_double_count(self):
        self.append(fact(), "first")
        with self.assertRaises(LedgerError):
            self.append(fact(), "second")
        self.assertEqual(len(self.ledger.entries()), 1)

    def test_sql_update_and_delete_are_blocked(self):
        self.append(fact())
        for sql in ("DELETE FROM entries", "UPDATE entries SET entry_hash='modified'"):
            with self.assertRaises(sqlite3.IntegrityError):
                self.ledger._conn.execute(sql)

    def test_audit_detects_owner_tampering_even_when_trigger_is_removed(self):
        self.append(fact())
        self.ledger._conn.execute("DROP TRIGGER no_entry_update")
        changed = self.ledger.entries()[0]
        changed["payload"]["value"] = 0
        self.ledger._conn.execute("UPDATE entries SET body=?", (json.dumps(changed),))
        audit = self.ledger.verify(self.key.public_key_hex)
        self.assertFalse(audit["valid"])
        self.assertIn("signature:1", audit["errors"])

    def test_reopen_requires_same_key_and_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            with Ledger(path, self.key, sources()) as ledger:
                ledger.append_fact(fact(), "one", recorded_at=TIME)
            with Ledger(path, self.key, sources()) as ledger:
                self.assertEqual(len(ledger.entries()), 1)
                self.assertTrue(ledger.verify(self.key.public_key_hex)["valid"])
            with self.assertRaises(LedgerError):
                Ledger(path, SigningKey.generate(), sources())
            with self.assertRaises(LedgerError):
                Ledger(path, self.key, {})


if __name__ == "__main__":
    unittest.main()
