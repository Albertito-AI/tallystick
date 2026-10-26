"""Pure reference settlement for a bounded threshold-count market language."""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

STATES = {"provisional": 0, "corroborated": 1, "official": 2, "final": 3}
FACT_FIELDS = frozenset({
    "schema_version", "fact_id", "observation_id", "event_id", "kind", "period",
    "subject", "value", "state", "source_ids", "licence_id", "occurred_at",
    "received_at", "supersedes", "reason", "correction_deadline", "metric",
})
IDENTITY_FIELDS = ("observation_id", "event_id", "kind", "period", "subject",
                   "occurred_at", "correction_deadline", "metric", "licence_id")


def parse_time(value: str) -> datetime:
    if type(value) is not str or not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z", value):
        raise ValueError("Timestamp must be UTC ISO 8601 ending in Z")
    try:
        result = datetime.fromisoformat(value[:-1] + "+00:00")
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid UTC timestamp") from exc
    if result.utcoffset() is None or result.utcoffset().total_seconds() != 0:
        raise ValueError("Timestamp must use UTC")
    return result


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _identifier(value: Any, name: str) -> None:
    if type(value) is not str or not 1 <= len(value) <= 160:
        raise ValueError(f"{name} must be a nonempty identifier of at most 160 characters")
    if any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise ValueError(f"{name} must use printable ASCII without spaces")


def validate_fact_shape(fact: dict) -> None:
    if type(fact) is not dict or set(fact) != FACT_FIELDS:
        raise ValueError("Fact fields do not match schema 0.1")
    if fact["schema_version"] != "0.1":
        raise ValueError("Unsupported fact schema")
    for name in ("fact_id", "observation_id", "event_id", "kind", "subject", "licence_id"):
        _identifier(fact[name], name)
    if fact["kind"] not in ("corner.awarded", "goal.scored", "period.closed", "event.abandoned"):
        raise ValueError("Unsupported fact kind")
    if type(fact["period"]) is not int or not 0 <= fact["period"] <= 20:
        raise ValueError("Invalid fact period")
    if type(fact["value"]) is not int or not 0 <= fact["value"] <= 100_000:
        raise ValueError("Invalid fact value")
    if fact["kind"] != "period.closed" and fact["value"] not in (0, 1):
        raise ValueError("Occurrence facts use a zero or one value")
    if fact["kind"] == "period.closed":
        if fact["metric"] not in ("corner.awarded", "goal.scored"):
            raise ValueError("Closure must name its count metric")
    elif fact["metric"] is not None:
        raise ValueError("Only closures carry a metric")
    if type(fact["state"]) is not str or fact["state"] not in STATES:
        raise ValueError("Invalid fact state")
    sources = fact["source_ids"]
    if type(sources) is not list or not 1 <= len(sources) <= 16:
        raise ValueError("Fact must have one to sixteen source identifiers")
    for source in sources:
        _identifier(source, "source_id")
    if len(set(sources)) != len(sources):
        raise ValueError("Duplicate source identifier")
    if fact["supersedes"] is not None:
        _identifier(fact["supersedes"], "supersedes")
    if fact["reason"] is not None and (type(fact["reason"]) is not str or
                                     not fact["reason"].strip() or len(fact["reason"]) > 2000):
        raise ValueError("Reason must be nonempty text of at most 2000 characters")
    observed, received, deadline = (parse_time(fact[name]) for name in
                                    ("occurred_at", "received_at", "correction_deadline"))
    if observed > received:
        raise ValueError("Occurrence cannot follow receipt")
    if observed > deadline:
        raise ValueError("Occurrence cannot follow the correction deadline")
    if fact["state"] == "final" and received < deadline:
        raise ValueError("A fact cannot be final before its correction deadline")


def validate_revision(fact: dict, previous: dict | None) -> None:
    if previous is None:
        if fact["supersedes"] is not None:
            raise ValueError("Initial fact cannot supersede a missing record")
        return
    if fact["supersedes"] != previous["fact_id"]:
        raise ValueError("Revision must supersede the current observation head")
    if any(fact[name] != previous[name] for name in IDENTITY_FIELDS):
        raise ValueError("Revision cannot change observation identity or deadline")
    if parse_time(fact["received_at"]) < parse_time(previous["received_at"]):
        raise ValueError("Revision receipt predates its predecessor")
    if previous["state"] == "final":
        raise ValueError("Final facts cannot be revised")
    if fact["value"] != previous["value"]:
        if fact["reason"] is None:
            raise ValueError("A correction requires a reason")
        if parse_time(fact["received_at"]) >= parse_time(previous["correction_deadline"]):
            raise ValueError("Correction window has closed")
    elif STATES[fact["state"]] < STATES[previous["state"]]:
        raise ValueError("An unchanged observation cannot lose its confirmed state")


def active_snapshot(facts: list[dict], as_of: str | None = None) -> list[dict]:
    """Resolve valid append-order history; return observation heads at receipt cutoff."""
    if type(facts) is not list or len(facts) > 100_000:
        raise ValueError("Fact history must be a bounded list")
    cutoff = parse_time(as_of) if as_of is not None else None
    all_ids: set[str] = set()
    all_heads: dict[str, dict] = {}
    heads: dict[str, dict] = {}
    for fact in facts:
        validate_fact_shape(fact)
        if fact["fact_id"] in all_ids:
            raise ValueError("Fact identifier is not unique")
        all_ids.add(fact["fact_id"])
        previous = all_heads.get(fact["observation_id"])
        validate_revision(fact, previous)
        all_heads[fact["observation_id"]] = fact
        if cutoff is None or parse_time(fact["received_at"]) <= cutoff:
            heads[fact["observation_id"]] = fact
    return list(heads.values())


def _closure_covers_value_changes(occurrences: list[dict], closure: dict, history: list[dict]) -> bool:
    """A matching total must also acknowledge all value corrections it covers."""
    declared_at = parse_time(closure["received_at"])
    by_id = {fact["fact_id"]: fact for fact in history}
    for occurrence in occurrences:
        current = occurrence
        while current["supersedes"] is not None:
            previous = by_id[current["supersedes"]]
            if current["value"] != previous["value"] and parse_time(current["received_at"]) > declared_at:
                return False
            current = previous
    return True


def evaluate(market: dict, facts: list[dict], as_of: str | None = None) -> dict:
    """Evaluate validated ledger facts, requiring an authoritative completeness record.

    Registry authority and rights are verified by ingestion and the compiler. This
    function does not independently authenticate supplied source declarations.
    """
    if type(market) is not dict:
        raise ValueError("Market must be an object")
    for name in ("market_id", "event_id"):
        _identifier(market.get(name), name)
    rule = market.get("settlement")
    if type(rule) is not dict or set(rule) != {"fact_type", "period", "threshold", "min_state"}:
        raise ValueError("Invalid settlement rule fields")
    if rule["fact_type"] not in ("corner.awarded", "goal.scored"):
        raise ValueError("Unsupported count metric")
    if type(rule["period"]) is not int or not 0 <= rule["period"] <= 20:
        raise ValueError("Invalid settlement period")
    if type(rule["threshold"]) is not int or not 1 <= rule["threshold"] <= 100_000:
        raise ValueError("Invalid settlement threshold")
    if rule["min_state"] not in ("official", "final"):
        raise ValueError("Settlement requires official or final facts")
    deadline = parse_time(market.get("correction_deadline"))
    active = [fact for fact in active_snapshot(facts, as_of if as_of is not None else utc_now())
              if fact["event_id"] == market["event_id"]]
    occurrences = [fact for fact in active if fact["kind"] == rule["fact_type"]
                   and fact["period"] == rule["period"]]
    closures = [fact for fact in active if fact["kind"] == "period.closed"
                and fact["period"] == rule["period"] and fact["metric"] == rule["fact_type"]]
    abandonments = [fact for fact in active if fact["kind"] == "event.abandoned"]
    relevant = occurrences + closures + abandonments
    result = {"market_id": market["market_id"], "status": "pending", "outcome": None,
              "count": None, "reasons": [],
              "fact_ids": sorted(fact["fact_id"] for fact in relevant)}
    if not active:
        result["reasons"] = ["no_event_facts"]
    elif any(parse_time(fact["correction_deadline"]) != deadline for fact in relevant):
        result["reasons"] = ["correction_deadline_mismatch"]
    else:
        abandoned = [fact for fact in abandonments if fact["value"] == 1]
        official_abandoned = [fact for fact in abandoned if STATES[fact["state"]] >= STATES["official"]]
        if official_abandoned:
            result.update(status="void", reasons=["event_abandoned"],
                          fact_ids=sorted(fact["fact_id"] for fact in official_abandoned))
        elif abandoned:
            result["reasons"] = ["unconfirmed_abandonment"]
        elif not closures:
            result["reasons"] = ["missing_closure"]
        elif len(closures) > 1:
            result["reasons"] = ["ambiguous_closure"]
        elif STATES[closures[0]["state"]] < STATES[rule["min_state"]]:
            result["reasons"] = ["insufficient_closure_state"]
        elif any(STATES[fact["state"]] < STATES[rule["min_state"]] for fact in occurrences):
            result["reasons"] = ["insufficient_fact_state"]
        else:
            count = sum(fact["value"] for fact in occurrences)
            if count != closures[0]["value"]:
                result["reasons"] = ["closure_count_mismatch"]
            elif not _closure_covers_value_changes(occurrences, closures[0], facts):
                result["reasons"] = ["stale_closure"]
            else:
                result.update(status="settled", count=count,
                              outcome="over" if count >= rule["threshold"] else "under")
    return result
