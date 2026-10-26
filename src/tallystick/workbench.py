"""A replay workbench and a separately pinned-key dispute verifier."""
from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path

from .compiler import MarketCompiler, SUPPORTING_FACT_TYPES, verify_certificate
from .crypto import SigningKey, canonical_json, merkle_root, verify_bundle, verify_signature
from .ledger import Ledger
from .rights import RightsRegistry
from .settlement import active_snapshot, evaluate, validate_fact_shape
from .validation import exact_keys, require, utc


def _digest(value):
    return hashlib.sha256(canonical_json(value)).hexdigest()


def settlement_with_rights(market, facts, rights, as_of, rulepacks):
    """Evaluate facts using the declared permissions and policy current at use time."""
    result = evaluate(market, facts, as_of)
    referenced = set(result["fact_ids"])
    licence = rights.licences.get(market["licence_id"])
    sources = licence["source_ids"] if licence else []
    checks = [rights.check(market["licence_id"], "settlement", market["jurisdiction"], kind,
                           sources, as_of)
              for kind in (market["settlement"]["fact_type"], *SUPPORTING_FACT_TYPES)]
    checks.extend(rights.check(f["licence_id"], "settlement", market["jurisdiction"], f["kind"],
                              f["source_ids"], as_of) for f in active_snapshot(facts, as_of)
                  if f["fact_id"] in referenced)
    require(type(rulepacks) is dict, "Validated rule packs are required")
    rule = rulepacks.get(market["rulepack_id"])
    reasons = {reason for check in checks for reason in check["reasons"]}
    if rule is None:
        reasons.add("UNKNOWN_RULEPACK")
    elif not utc(rule["valid_from"]) <= utc(as_of) < utc(rule["valid_until"]):
        reasons.add("RULEPACK_NOT_CURRENT")
    if reasons:
        result.update(status="pending", outcome=None, count=None,
                      reasons=sorted(reasons))
    return result, checks


def run_replay(scenario: dict, database: str | Path = ":memory:", signer=None) -> dict:
    exact_keys(scenario, {"schema_version", "synthetic", "compiled_at", "sources", "licences",
                          "rulepacks", "market", "stages"})
    require(scenario["schema_version"] == "0.1" and scenario["synthetic"] is True,
            "Only synthetic replay scenarios are supported")
    require(type(scenario["stages"]) is list and 1 <= len(scenario["stages"]) <= 256, "Invalid replay stages")
    signer = signer or SigningKey.generate()
    rights = RightsRegistry(scenario["licences"], scenario["sources"])
    compiler = MarketCompiler(rights, scenario["rulepacks"], signer)
    compiled = compiler.compile(scenario["market"], scenario["compiled_at"])
    require(compiled["accepted"], ", ".join(compiled["reasons"]), "MARKET_REJECTED")
    market, certificate = scenario["market"], compiled["certificate"]
    with Ledger(database, signer, scenario["sources"]) as ledger:
        ledger.append("market-certificate", certificate, "certificate:" + market["market_id"], scenario["compiled_at"])
        stages = []
        previous_time = utc(scenario["compiled_at"])
        for number, stage in enumerate(scenario["stages"]):
            exact_keys(stage, {"name", "as_of", "facts"})
            require(type(stage["name"]) is str and 0 < len(stage["name"]) <= 200, "Invalid stage name")
            require(utc(stage["as_of"]) >= previous_time, "Replay time moved backwards")
            previous_time = utc(stage["as_of"])
            require(type(stage["facts"]) is list and len(stage["facts"]) <= 1000, "Replay fact batch exceeds limit")
            for fact in stage["facts"]:
                validate_fact_shape(fact)
                rights.require(licence_id=fact["licence_id"], use="settlement", territory=market["jurisdiction"],
                               fact_type=fact["kind"], source_ids=fact["source_ids"], as_of=fact["received_at"])
                ledger.append_fact(fact, "fact:" + fact["fact_id"], stage["as_of"])
            result, rights_checks = settlement_with_rights(market, ledger.facts(), rights, stage["as_of"], compiler.rulepacks)
            decision = {"market_hash": certificate["payload"]["market_hash"], "as_of": stage["as_of"],
                        "result": result, "rights_checks": rights_checks}
            entry = ledger.append("settlement-decision", decision, f"decision:{market['market_id']}:{number}", stage["as_of"])
            stages.append({"name": stage["name"], "as_of": stage["as_of"], "sequence": entry["sequence"], **result})
        entries = ledger.entries()
        verification = ledger.verify(signer.public_key_hex)
        body = {"type": "tallystick.dispute-bundle", "schema_version": "0.1", "synthetic": True,
                "scope": "local_recorder_evidence_only", "sources": deepcopy(scenario["sources"]),
                "licences": deepcopy(scenario["licences"]), "rulepacks": deepcopy(scenario["rulepacks"]),
                "market": deepcopy(market), "certificate": certificate,
                "as_of": stages[-1]["as_of"], "decision_sequence": stages[-1]["sequence"],
                "decision": stages[-1], "entries": entries, "checkpoint": ledger.checkpoint(),
                "proofs": [ledger.inclusion_proof(e["sequence"])["proof"] for e in entries]}
        manifest = {"domain": "tallystick.dispute-manifest.v1", "bundle_sha256": _digest(body)}
        bundle = {"body": body, "manifest": manifest, "signature": signer.sign(manifest)}
    return {"stages": stages, "certificate": certificate, "bundle": bundle,
            "public_key": signer.public_key_hex, "ledger_verification": verification,
            "entry_count": len(entries), "synthetic": True}


def verify_dispute(bundle: dict, trusted_public_key: str) -> dict:
    """Verify all records and replay every decision; obtain the trusted key separately.

    A valid result establishes consistency with this recorder's signed history
    and declared synthetic configuration. It cannot establish upstream truth or
    discover an alternative history signed by the same recorder.
    """
    reasons = []
    try:
        exact_keys(bundle, {"body", "manifest", "signature"})
        body = bundle["body"]
        exact_keys(body, {"type", "schema_version", "synthetic", "scope", "sources", "licences", "rulepacks",
                          "market", "certificate", "as_of", "decision_sequence", "decision", "entries", "checkpoint", "proofs"})
        require(body["type"] == "tallystick.dispute-bundle" and body["schema_version"] == "0.1"
                and body["synthetic"] is True and body["scope"] == "local_recorder_evidence_only", "Unsupported bundle")
        as_of = utc(body["as_of"])
        require(bundle["manifest"] == {"domain": "tallystick.dispute-manifest.v1", "bundle_sha256": _digest(body)}, "Manifest mismatch")
        require(verify_signature(bundle["manifest"], bundle["signature"], trusted_public_key), "Manifest signature invalid")
        require(verify_certificate(body["certificate"], trusted_public_key), "Certificate signature invalid")
        require(canonical_json(body["market"]) == canonical_json(body["certificate"]["payload"]["market"]),
                "Market differs from certificate")
        entries = body["entries"]
        require(type(entries) is list and 1 <= len(entries) <= 10_000, "Invalid log size")
        exact_keys(body["checkpoint"], {"domain", "log_id", "source_registry_hash", "tree_size",
                                        "root_hash", "recorded_at", "signature", "public_key"})
        require(type(body["proofs"]) is list, "Invalid log proofs")
        require(type(body["checkpoint"]["tree_size"]) is int
                and len(entries) == body["checkpoint"]["tree_size"] == len(body["proofs"]), "Incomplete log")
        require(merkle_root([canonical_json(e) for e in entries]) == body["checkpoint"]["root_hash"], "Log root mismatch")
        previous = "0" * 64
        previous_time = None
        idempotency_keys = set()
        registry_hash = _digest(body["sources"])
        require(body["checkpoint"]["source_registry_hash"] == registry_hash, "Source registry mismatch")
        rights = RightsRegistry(body["licences"], body["sources"])
        certificate = body["certificate"]["payload"]
        # Reproduce all certificate assertions, not only its market or admission verdict.
        compiler = MarketCompiler(rights, body["rulepacks"], SigningKey.generate())
        recompiled = compiler.compile(body["market"], certificate["issued_at"])
        require(recompiled["accepted"], "Recorded compilation fails current implementation")
        require(canonical_json(recompiled["certificate"]["payload"]) == canonical_json(certificate),
                "Certificate assertions differ from the recorded configuration")
        recomputed = None
        checks = None
        decisions_verified = 0
        # Revalidate all ingestion states without having, or needing, the original private key.
        with Ledger(":memory:", SigningKey.generate(), body["sources"]) as validation_ledger:
            for number, (entry, proof) in enumerate(zip(entries, body["proofs"]), start=1):
                exact_keys(entry, {"domain", "log_id", "source_registry_hash", "sequence", "previous_hash",
                                   "recorded_at", "kind", "payload", "idempotency_key", "entry_hash", "signature"})
                require(type(entry["sequence"]) is int and entry["sequence"] == number
                        and entry["previous_hash"] == previous, "Log chain mismatch")
                require(entry["source_registry_hash"] == registry_hash, "Entry source registry mismatch")
                require(verify_bundle({"entry": entry, "proof": proof, "checkpoint": body["checkpoint"]}, trusted_public_key), "Entry proof invalid")
                recorded = utc(entry["recorded_at"])
                require((previous_time is None or recorded >= previous_time) and recorded <= as_of,
                        "Log time is inconsistent with its recorded order or evaluation time")
                previous_time = recorded
                key = entry["idempotency_key"]
                require(type(key) is str and 0 < len(key) <= 200 and key not in idempotency_keys,
                        "Invalid or repeated log idempotency key")
                idempotency_keys.add(key)
                require(type(entry["kind"]) is str and entry["kind"] in {
                        "market-certificate", "fact", "settlement-decision"}, "Unsupported replay log kind")
                previous = entry["entry_hash"]
                if number == 1:
                    require(entry["kind"] == "market-certificate"
                            and canonical_json(entry["payload"]) == canonical_json(body["certificate"])
                            and entry["recorded_at"] == certificate["issued_at"],
                            "The first log record must contain the issued certificate")
                elif entry["kind"] == "market-certificate":
                    require(False, "A replay log must contain exactly one market certificate")
                if entry["kind"] == "fact":
                    fact = entry["payload"]
                    validate_fact_shape(fact)
                    rights.require(licence_id=fact["licence_id"], use="settlement",
                                   territory=body["market"]["jurisdiction"], fact_type=fact["kind"],
                                   source_ids=fact["source_ids"], as_of=fact["received_at"])
                    validation_ledger.append_fact(entry["payload"], entry["idempotency_key"], entry["recorded_at"])
                else:
                    if entry["kind"] == "settlement-decision":
                        recomputed, checks = settlement_with_rights(body["market"], validation_ledger.facts(), rights,
                                                                  entry["recorded_at"], compiler.rulepacks)
                        expected = {"market_hash": certificate["market_hash"], "as_of": entry["recorded_at"],
                                    "result": recomputed, "rights_checks": checks}
                        require(canonical_json(entry["payload"]) == canonical_json(expected),
                                f"Decision at sequence {number} cannot be reproduced from its log prefix")
                        decisions_verified += 1
                    validation_ledger.append(entry["kind"], entry["payload"], key, entry["recorded_at"])
        decision_number = body["decision_sequence"]
        require(type(decision_number) is int and 1 <= decision_number <= len(entries), "Invalid decision sequence")
        decision_entry = entries[decision_number - 1]
        require(decision_entry["kind"] == "settlement-decision" and decision_number == len(entries), "Final decision must be the last record")
        require(decision_entry["recorded_at"] == body["as_of"] == body["checkpoint"]["recorded_at"],
                "Final decision, checkpoint and evaluation timestamps differ")
        exact_keys(body["decision"], {"name", "as_of", "sequence", "market_id", "status", "outcome", "count", "reasons", "fact_ids"})
        require(type(body["decision"]["name"]) is str and 0 < len(body["decision"]["name"]) <= 200,
                "Invalid decision summary name")
        expected_summary = {"name": body["decision"]["name"], "as_of": body["as_of"],
                            "sequence": decision_number, **recomputed}
        require(canonical_json(body["decision"]) == canonical_json(expected_summary), "Summary differs from signed decision")
        return {"valid": True, "reasons": [], "scope": "pinned recorder signature, complete log and reproducible synthetic decision",
                "decision": recomputed, "entries_verified": len(entries), "decisions_verified": decisions_verified}
    except (ValueError, KeyError, TypeError, IndexError, AttributeError, OverflowError, RecursionError) as error:
        reasons.append(str(error))
    return {"valid": False, "reasons": reasons}
