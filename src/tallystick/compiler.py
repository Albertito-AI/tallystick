"""Compile a narrow JSON market definition into a signed synthetic-replay record."""
from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from .crypto import canonical_json, verify_signature
from .validation import InputError, exact_keys, integer, now_utc, require, token, utc

MARKET_FIELDS = {"schema_version", "market_id", "event_id", "name", "settlement", "outcomes",
                 "close_at", "correction_deadline", "jurisdiction", "licence_id", "rulepack_id",
                 "consumer", "window_seconds", "participant_scope", "batch_window_ms"}
CERTIFICATE_FIELDS = {"type", "schema_version", "scope", "issued_at", "market", "market_hash",
                      "rulepack_hash", "licence_hash", "rulepack_id", "rulepack_version",
                      "integrity", "harm", "coherence", "rights_check", "supporting_rights_checks"}
SUPPORTING_FACT_TYPES = ("period.closed", "event.abandoned")
DIRECTIVES = re.compile(r"ignore\s+(?:all\s+|any\s+)?(?:previous|prior)|system\s*prompt|"
                        r"execute\s+(?:this|code)|send\s+(?:secrets|credentials)", re.I)


def validate_market(market: dict) -> None:
    exact_keys(market, MARKET_FIELDS)
    require(market["schema_version"] == "0.1", "Unknown market schema")
    for field in ("market_id", "event_id", "jurisdiction", "licence_id", "rulepack_id"):
        token(market[field], field)
    name = market["name"]
    require(type(name) is str and 1 <= len(name) <= 120 and name.isprintable(), "Invalid display name")
    require(not DIRECTIVES.search(name), "Display text contains a disallowed directive", "UNSAFE_DISPLAY_TEXT")
    require(market["outcomes"] == ["over", "under"], "Only complementary count outcomes are supported")
    settlement = market["settlement"]
    exact_keys(settlement, {"fact_type", "period", "threshold", "min_state"})
    require(type(settlement["fact_type"]) is str and settlement["fact_type"] in {"corner.awarded", "goal.scored"},
            "Unknown settlement fact type")
    integer(settlement["period"], "period", 1, 10)
    integer(settlement["threshold"], "threshold", 1, 10000)
    require(type(settlement["min_state"]) is str and settlement["min_state"] in {"official", "final"},
            "Authoritative settlement state is required")
    require(utc(market["close_at"]) < utc(market["correction_deadline"]), "Invalid market dates")
    require(type(market["consumer"]) is bool, "consumer must be boolean")
    integer(market["window_seconds"], "window_seconds", 1, 86400)
    integer(market["batch_window_ms"], "batch_window_ms", 1, 1000)
    require(type(market["participant_scope"]) is str and market["participant_scope"] in {"aggregate", "single_actor"},
            "Unknown participant scope")


class MarketCompiler:
    def __init__(self, rights, rulepacks: list[dict], signer):
        self.rights = rights
        self.rulepacks = {}
        require(type(rulepacks) is list and 0 < len(rulepacks) <= 128, "Invalid rule-pack registry")
        for rule in rulepacks:
            exact_keys(rule, {"schema_version", "rulepack_id", "version", "jurisdiction", "basis",
                             "reviewer", "reviewed_at", "valid_from", "valid_until", "allow_consumer",
                             "min_window_seconds", "allowed_fact_types", "required_state"})
            require(rule["schema_version"] == "0.1", "Unknown rule-pack schema")
            token(rule["rulepack_id"], "rulepack_id")
            token(rule["version"], "rulepack version")
            require(rule["rulepack_id"] not in self.rulepacks, "Duplicate rule pack")
            require(rule["basis"] == "synthetic" and rule["jurisdiction"] == "TEST",
                    "This build contains only synthetic TEST policy packs", "LIVE_POLICY_DISABLED")
            require(type(rule["reviewer"]) is str and 0 < len(rule["reviewer"]) <= 200
                    and rule["reviewer"].isprintable() and bool(rule["reviewer"].strip()), "Reviewer is required")
            require(utc(rule["reviewed_at"]) <= utc(rule["valid_from"]) < utc(rule["valid_until"]), "Invalid rule dates")
            require(rule["allow_consumer"] is False, "Consumer flows are outside this build")
            integer(rule["min_window_seconds"], "min_window_seconds", 1, 86400)
            require(type(rule["required_state"]) is str and rule["required_state"] in {"official", "final"},
                    "Invalid state policy")
            allowed = rule["allowed_fact_types"]
            require(type(allowed) is list and 0 < len(allowed) <= 2, "Fact types required")
            for fact_type in allowed:
                token(fact_type, "allowed fact type")
            require(len(set(allowed)) == len(allowed) and set(allowed) <= {"corner.awarded", "goal.scored"},
                    "Unknown or duplicate policy fact type")
            self.rulepacks[rule["rulepack_id"]] = deepcopy(rule)
        self.signer = signer

    def compile(self, market: dict, as_of: str | None = None) -> dict:
        as_of = now_utc() if as_of is None else as_of
        when = utc(as_of)
        validate_market(market)
        reasons = []
        rule = self.rulepacks.get(market["rulepack_id"])
        if market["jurisdiction"] != "TEST":
            reasons.append("LIVE_JURISDICTION_UNAVAILABLE")
        if market["consumer"]:
            reasons.append("CONSUMER_FLOW_DISABLED")
        if when >= utc(market["close_at"]):
            reasons.append("MARKET_ALREADY_CLOSED")
        if rule is None:
            reasons.append("UNKNOWN_RULEPACK")
        else:
            if rule["jurisdiction"] != market["jurisdiction"]:
                reasons.append("JURISDICTION_MISMATCH")
            if not utc(rule["valid_from"]) <= when < utc(rule["valid_until"]):
                reasons.append("RULEPACK_NOT_CURRENT")
            if utc(market["correction_deadline"]) >= utc(rule["valid_until"]):
                reasons.append("RULEPACK_EXPIRES_BEFORE_MARKET")
            if market["window_seconds"] < rule["min_window_seconds"]:
                reasons.append("DURATION_BELOW_POLICY")
            if market["settlement"]["fact_type"] not in rule["allowed_fact_types"]:
                reasons.append("FACT_TYPE_NOT_ALLOWED")
            if rule["required_state"] == "final" and market["settlement"]["min_state"] != "final":
                reasons.append("STATE_BELOW_POLICY")
        licence = self.rights.licences.get(market["licence_id"])
        source_ids = licence["source_ids"] if licence else []
        right = self.rights.check(market["licence_id"], "settlement", market["jurisdiction"],
                                  market["settlement"]["fact_type"], source_ids, as_of)
        reasons.extend(right["reasons"])
        supporting_checks = [{"fact_type": kind,
                              "check": self.rights.check(market["licence_id"], "settlement", market["jurisdiction"],
                                                         kind, source_ids, as_of)}
                             for kind in SUPPORTING_FACT_TYPES]
        for check in supporting_checks:
            reasons.extend(check["check"]["reasons"])
        if licence and utc(market["correction_deadline"]) >= utc(licence["valid_until"]):
            reasons.append("LICENCE_EXPIRES_BEFORE_MARKET")
        if not any(market["settlement"]["fact_type"] in self.rights.sources[s].get("official_kinds", [])
                   for s in source_ids):
            reasons.append("NO_DESIGNATED_OFFICIAL_SOURCE")
        for kind, failure in (("period.closed", "NO_DESIGNATED_CLOSURE_SOURCE"),
                              ("event.abandoned", "NO_DESIGNATED_ABANDONMENT_SOURCE")):
            if not any(kind in self.rights.sources[source]["official_kinds"] for source in source_ids):
                reasons.append(failure)
        if market["participant_scope"] == "single_actor":
            reasons.append("SINGLE_ACTOR_MARKET_DISABLED")
        reasons = list(dict.fromkeys(reasons))
        result = {"accepted": not reasons, "reasons": reasons, "certificate": None}
        if reasons:
            return result
        payload = {"type": "tallystick.market-certificate", "schema_version": "0.1",
                   "scope": "synthetic_replay_only", "issued_at": as_of, "market": deepcopy(market),
                   "market_hash": hashlib.sha256(canonical_json(market)).hexdigest(),
                   "rulepack_hash": hashlib.sha256(canonical_json(rule)).hexdigest(),
                   "licence_hash": hashlib.sha256(canonical_json(licence)).hexdigest(),
                   "rulepack_id": rule["rulepack_id"], "rulepack_version": rule["version"],
                   "integrity": "aggregate_requires_contextual_review", "harm": "simulation_only",
                   "coherence": "NOT_ASSESSED", "rights_check": right,
                   "supporting_rights_checks": supporting_checks}
        result["certificate"] = {"payload": payload, "signature": self.signer.sign(payload)}
        return result


def verify_certificate(certificate: dict, trusted_public_key_hex: str) -> bool:
    try:
        exact_keys(certificate, {"payload", "signature"})
        p = certificate["payload"]
        exact_keys(p, CERTIFICATE_FIELDS)
        if (p["type"] != "tallystick.market-certificate" or p["schema_version"] != "0.1"
                or p["scope"] != "synthetic_replay_only"
                or p["integrity"] != "aggregate_requires_contextual_review"
                or p["harm"] != "simulation_only" or p["coherence"] != "NOT_ASSESSED"):
            return False
        validate_market(p["market"])
        require(utc(p["issued_at"]) < utc(p["market"]["close_at"]), "Certificate was issued after market close")
        token(p["rulepack_version"], "rulepack version")
        require(p["rulepack_id"] == p["market"]["rulepack_id"], "Certificate rule pack mismatch")
        for field in ("market_hash", "rulepack_hash", "licence_hash"):
            require(type(p[field]) is str and re.fullmatch(r"[0-9a-f]{64}", p[field]) is not None,
                    "Invalid certificate digest")
        require(type(p["rights_check"]) is dict and p["rights_check"].get("allowed") is True,
                "Certificate does not assert permission")
        require(type(p["supporting_rights_checks"]) is list and len(p["supporting_rights_checks"]) == 2,
                "Certificate omits supporting permissions")
        for kind, check in zip(SUPPORTING_FACT_TYPES, p["supporting_rights_checks"]):
            exact_keys(check, {"fact_type", "check"})
            require(check["fact_type"] == kind and type(check["check"]) is dict
                    and check["check"].get("allowed") is True, "Invalid supporting permission")
        return (hashlib.sha256(canonical_json(p["market"])).hexdigest() == p["market_hash"]
                and verify_signature(p, certificate["signature"], trusted_public_key_hex))
    except (ValueError, TypeError, KeyError):
        return False
