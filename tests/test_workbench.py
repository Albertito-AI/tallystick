"""Dispute verification tests include internally inconsistent, validly signed logs."""
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest

from tallystick.crypto import SigningKey, canonical_json, inclusion_proof, merkle_root
from tallystick.fixtures import scenario
from tallystick.workbench import run_replay, verify_dispute


class WorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = SigningKey.generate()
        cls.result = run_replay(scenario(), signer=cls.key)

    def bundle(self):
        return deepcopy(self.result["bundle"])

    def resign_manifest(self, bundle):
        bundle["manifest"] = {"domain": "tallystick.dispute-manifest.v1",
                              "bundle_sha256": hashlib.sha256(canonical_json(bundle["body"])).hexdigest()}
        bundle["signature"] = self.key.sign(bundle["manifest"])
        return bundle

    def relog(self, bundle):
        """A malicious recorder can sign data; semantic verification must still reject contradictions."""
        previous = "0" * 64
        for entry in bundle["body"]["entries"]:
            entry["previous_hash"] = previous
            envelope = {k: v for k, v in entry.items() if k not in ("signature", "entry_hash")}
            entry["entry_hash"] = hashlib.sha256(canonical_json(envelope)).hexdigest()
            entry["signature"] = self.key.sign(envelope)
            previous = entry["entry_hash"]
        leaves = [canonical_json(entry) for entry in bundle["body"]["entries"]]
        checkpoint = bundle["body"]["checkpoint"]
        checkpoint["root_hash"] = merkle_root(leaves)
        checkpoint["recorded_at"] = bundle["body"]["entries"][-1]["recorded_at"]
        signed = {k: v for k, v in checkpoint.items() if k not in ("signature", "public_key")}
        checkpoint["signature"] = self.key.sign(signed)
        bundle["body"]["proofs"] = [inclusion_proof(leaves, i) for i in range(len(leaves))]
        return self.resign_manifest(bundle)

    def test_full_replay_reaches_expected_corrections_and_verifies(self):
        observed = [(item["status"], item["outcome"], item["count"]) for item in self.result["stages"]]
        self.assertEqual(observed, [("pending", None, None), ("pending", None, None),
                                   ("settled", "over", 6), ("pending", None, None),
                                   ("settled", "over", 5), ("settled", "under", 4)])
        self.assertTrue(self.result["ledger_verification"]["valid"])
        verified = verify_dispute(self.result["bundle"], self.key.public_key_hex)
        self.assertTrue(verified["valid"], verified)
        self.assertEqual(verified["entries_verified"], self.result["entry_count"])
        self.assertEqual(verified["decisions_verified"], len(self.result["stages"]))

    def test_wrong_pinned_key_and_plain_tampering_are_rejected(self):
        self.assertFalse(verify_dispute(self.bundle(), SigningKey.generate().public_key_hex)["valid"])
        bundle = self.bundle()
        bundle["body"]["decision"]["count"] = 999
        self.assertFalse(verify_dispute(bundle, self.key.public_key_hex)["valid"])

    def test_omitting_log_entry_or_proof_is_rejected(self):
        for field in ("entries", "proofs"):
            bundle = self.bundle()
            bundle["body"][field].pop(2)
            self.resign_manifest(bundle)
            self.assertFalse(verify_dispute(bundle, self.key.public_key_hex)["valid"])

    def test_authenticated_malformed_summary_returns_invalid_without_crashing(self):
        bundle = self.bundle()
        bundle["body"]["decision"] = []
        self.resign_manifest(bundle)
        self.assertFalse(verify_dispute(bundle, self.key.public_key_hex)["valid"])

    def test_authenticated_summary_cannot_change_as_of_or_sequence(self):
        for key, value in (("as_of", "2026-01-01T12:00:00Z"), ("sequence", 1)):
            bundle = self.bundle()
            bundle["body"]["decision"][key] = value
            self.resign_manifest(bundle)
            self.assertFalse(verify_dispute(bundle, self.key.public_key_hex)["valid"])

    def test_authenticated_scope_overclaim_is_rejected(self):
        bundle = self.bundle()
        bundle["body"]["scope"] = "verified_real_world_truth"
        self.resign_manifest(bundle)
        self.assertFalse(verify_dispute(bundle, self.key.public_key_hex)["valid"])

    def test_logged_certificate_must_match_the_bundle_certificate(self):
        bundle = self.bundle()
        bundle["body"]["entries"][0]["payload"] = {"unrelated": "different certificate"}
        self.relog(bundle)
        self.assertFalse(verify_dispute(bundle, self.key.public_key_hex)["valid"])

    def test_signed_log_with_backwards_decision_time_is_rejected(self):
        bundle = self.bundle()
        bundle["body"]["entries"][-1]["recorded_at"] = "2026-01-01T11:00:00Z"
        self.relog(bundle)
        self.assertFalse(verify_dispute(bundle, self.key.public_key_hex)["valid"])

    def test_authenticated_certificate_metadata_must_match_recorded_policies(self):
        for field, value in (("allowed", False), ("checked_at", "2026-01-01T12:00:01Z")):
            bundle = self.bundle()
            certificate = bundle["body"]["certificate"]
            certificate["payload"]["rights_check"][field] = value
            certificate["signature"] = self.key.sign(certificate["payload"])
            bundle["body"]["entries"][0]["payload"] = deepcopy(certificate)
            self.relog(bundle)
            with self.subTest(field=field):
                self.assertFalse(verify_dispute(bundle, self.key.public_key_hex)["valid"])

    def test_earlier_signed_decisions_must_match_their_fact_prefix(self):
        bundle = self.bundle()
        earlier = next(entry for entry in bundle["body"]["entries"] if entry["kind"] == "settlement-decision")
        earlier["payload"]["result"].update(status="settled", outcome="under", count=0, reasons=[])
        self.relog(bundle)
        self.assertFalse(verify_dispute(bundle, self.key.public_key_hex)["valid"])

    def test_duplicate_signed_idempotency_keys_are_rejected(self):
        bundle = self.bundle()
        bundle["body"]["entries"][-1]["idempotency_key"] = bundle["body"]["entries"][0]["idempotency_key"]
        self.relog(bundle)
        self.assertFalse(verify_dispute(bundle, self.key.public_key_hex)["valid"])

    def test_same_database_retry_preserves_the_signed_log(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "recorder.sqlite3"
            first = run_replay(scenario(), database, self.key)
            second = run_replay(scenario(), database, self.key)
            self.assertEqual(first["bundle"], second["bundle"])
            self.assertTrue(verify_dispute(second["bundle"], self.key.public_key_hex)["valid"])

    def test_scope_and_licence_mismatches_stop_replay(self):
        invalid = scenario()
        invalid["stages"][0]["facts"][0]["licence_id"] = "missing-licence"
        with self.assertRaises(ValueError):
            run_replay(invalid)
        invalid = scenario()
        invalid["stages"][0]["facts"][0]["received_at"] = "2026-01-01T14:00:00Z"
        with self.assertRaises(ValueError):
            run_replay(invalid)

    def test_expired_rulepack_prevents_new_settlement_decision(self):
        source = scenario()
        source["rulepacks"][0]["valid_until"] = "2026-01-03T00:00:00Z"
        source["stages"].append({"name": "Policy expired", "as_of": "2026-01-04T00:00:00Z", "facts": []})
        result = run_replay(source)
        self.assertEqual(result["stages"][-1]["status"], "pending")
        self.assertIn("RULEPACK_NOT_CURRENT", result["stages"][-1]["reasons"])
        self.assertTrue(verify_dispute(result["bundle"], result["public_key"])["valid"])

    def test_expired_licence_cannot_be_reused_for_a_new_decision(self):
        source = scenario()
        source["licences"][0]["valid_until"] = "2026-01-03T00:00:00Z"
        source["stages"].append({"name": "Permission expired", "as_of": "2026-01-04T00:00:00Z", "facts": []})
        result = run_replay(source)
        self.assertEqual(result["stages"][-1]["status"], "pending")
        self.assertIn("LICENCE_NOT_CURRENT", result["stages"][-1]["reasons"])
        self.assertTrue(verify_dispute(result["bundle"], result["public_key"])["valid"])


if __name__ == "__main__":
    unittest.main()
