"""Independent synthetic input construction for cross-language comparisons.

These fixtures are invented. They contain no actual sports or licensed feed data.
"""
from __future__ import annotations

from copy import deepcopy
from random import Random

DEADLINE = "2026-11-04T22:00:00Z"
AS_OF = "2026-11-04T10:00:00Z"


def market(event_id: str = "fictional-match-001", threshold: int = 5) -> dict:
    return {
        "schema_version": "0.1",
        "market_id": f"{event_id}-corners",
        "event_id": event_id,
        "settlement": {
            "fact_type": "corner.awarded", "period": 2,
            "threshold": threshold, "min_state": "official",
        },
        "correction_deadline": DEADLINE,
    }


def fact(observation_id: str, *, event_id: str = "fictional-match-001",
         kind: str = "corner.awarded", value: int = 1,
         state: str = "official", period: int = 2,
         received_at: str = "2026-11-03T21:00:00Z") -> dict:
    return {
        "schema_version": "0.1", "fact_id": observation_id + "-v1",
        "observation_id": observation_id, "event_id": event_id,
        "kind": kind, "period": period, "subject": "all",
        "value": value, "state": state,
        "source_ids": ["fictional-official-source"],
        "licence_id": "fictional-test-licence",
        "occurred_at": "2026-11-03T20:50:00Z",
        "received_at": received_at, "supersedes": None, "reason": None,
        "correction_deadline": DEADLINE,
        "metric": "corner.awarded" if kind == "period.closed" else None,
    }


def complete_case(count: int, *, event_id: str = "fictional-match-001",
                  threshold: int = 5) -> dict:
    facts = [fact(f"{event_id}-corner-{i:03d}", event_id=event_id)
             for i in range(count)]
    facts.append(fact(event_id + "-closure", event_id=event_id,
                      kind="period.closed", value=count))
    return {"market": market(event_id, threshold), "facts": facts, "as_of": AS_OF}


def revised(previous: dict, value: int, *, received_at: str,
            state: str | None = None) -> dict:
    update = deepcopy(previous)
    update["fact_id"] = previous["fact_id"] + "-next"
    update["supersedes"] = previous["fact_id"]
    update["value"] = value
    update["received_at"] = received_at
    update["reason"] = "Fictional source correction" if value != previous["value"] else None
    update["state"] = state or previous["state"]
    return update


def golden_cases() -> list[dict]:
    rows = []

    def add(name: str, case: dict, status: str, outcome: str | None,
            count: int | None, reason: str | None = None) -> None:
        expected = {"status": status, "outcome": outcome, "count": count,
                    "reasons": [] if reason is None else [reason]}
        rows.append({"name": name, "input": case, "expected": expected})

    add("over", complete_case(6), "settled", "over", 6)
    add("under", complete_case(4), "settled", "under", 4)
    add("zero_with_closure", complete_case(0), "settled", "under", 0)
    case = complete_case(0)
    case["facts"] = []
    add("empty_is_pending", case, "pending", None, None, "no_event_facts")
    case = complete_case(5)
    case["facts"].pop()
    add("missing_closure", case, "pending", None, None, "missing_closure")
    case = complete_case(6)
    case["facts"][-1]["value"] = 7
    add("incomplete_feed", case, "pending", None, None, "closure_count_mismatch")
    case = complete_case(6)
    case["facts"][0]["state"] = "provisional"
    add("unconfirmed_occurrence", case, "pending", None, None, "insufficient_fact_state")
    case = complete_case(6)
    case["facts"][-1]["state"] = "provisional"
    add("unconfirmed_closure", case, "pending", None, None, "insufficient_closure_state")
    case = complete_case(6)
    case["facts"].append(fact("abandonment", kind="event.abandoned"))
    add("official_abandonment", case, "void", None, None, "event_abandoned")
    case = complete_case(6)
    case["facts"].append(fact("abandonment", kind="event.abandoned", state="provisional"))
    add("unconfirmed_abandonment", case, "pending", None, None, "unconfirmed_abandonment")
    case = complete_case(6)
    case["facts"].append(fact("second-closure", kind="period.closed", value=6))
    add("conflicting_closure_identity", case, "pending", None, None, "ambiguous_closure")
    case = complete_case(6)
    case["facts"][0]["correction_deadline"] = "2026-11-04T23:00:00Z"
    add("deadline_mismatch", case, "pending", None, None, "correction_deadline_mismatch")
    case = complete_case(5)
    case["facts"][0]["correction_deadline"] = "2026-11-04T22:00:00.000000Z"
    add("equivalent_deadline_instant", case, "settled", "over", 5)
    case = complete_case(5)
    old_closure = case["facts"][-1]
    case["facts"].append(revised(case["facts"][0], 0,
                                  received_at="2026-11-04T08:00:00Z"))
    add("correction_waits_for_closure", deepcopy(case), "pending", None, None,
        "closure_count_mismatch")
    case["facts"].append(revised(old_closure, 4,
                                  received_at="2026-11-04T08:01:00Z"))
    add("correction_changes_outcome", deepcopy(case), "settled", "under", 4)
    case["as_of"] = "2026-11-03T23:00:00Z"
    add("replay_before_correction", deepcopy(case), "settled", "over", 5)
    case["as_of"] = "2026-11-04T08:00:30Z"
    add("replay_between_correction_messages", case, "pending", None, None,
        "closure_count_mismatch")
    case = complete_case(5)
    original_closure = case["facts"][-1]
    withdrawn = fact("previously-withdrawn-corner", value=0)
    case["facts"].insert(-1, withdrawn)
    case["facts"] += [revised(case["facts"][0], 0, received_at="2026-11-04T08:00:00Z"),
                      revised(withdrawn, 1, received_at="2026-11-04T08:00:01Z")]
    add("offsetting_corrections_need_fresh_closure", deepcopy(case), "pending", None, None,
        "stale_closure")
    case["facts"].append(revised(original_closure, 5, received_at="2026-11-04T08:01:00Z"))
    add("refreshed_same_count_closure", case, "settled", "over", 5)
    case = complete_case(5)
    case["facts"].append(revised(case["facts"][0], 1, received_at=DEADLINE, state="final"))
    case["as_of"] = DEADLINE
    add("promotion_alone_keeps_closure", case, "settled", "over", 5)
    case = complete_case(4)
    case["market"]["settlement"]["min_state"] = "final"
    add("final_required", deepcopy(case), "pending", None, None, "insufficient_closure_state")
    case["facts"] += [revised(f, f["value"], received_at=DEADLINE, state="final")
                        for f in list(case["facts"])]
    case["as_of"] = DEADLINE
    add("final_after_deadline", case, "settled", "under", 4)
    case = complete_case(2, threshold=2)
    case["market"]["settlement"]["fact_type"] = "goal.scored"
    for f in case["facts"]:
        if f["kind"] == "corner.awarded":
            f["kind"] = "goal.scored"
        else:
            f["metric"] = "goal.scored"
    add("second_metric", case, "settled", "over", 2)
    return rows


def synthetic_season(matches: int = 380) -> list[dict]:
    """Generate independent fictional matches with reproducible count diversity.

    Every tenth nonempty match also has a correction snapshot. The returned
    expected outcomes follow the generated integers, without calling an evaluator.
    """
    rng = Random(20261026)
    rows = []
    for i in range(matches):
        count, threshold = rng.randrange(0, 15), rng.randrange(1, 12)
        case = complete_case(count, event_id=f"synthetic-season-{i:03d}", threshold=threshold)
        rows.append({"name": f"match-{i:03d}", "input": case,
                     "expected": {"status": "settled", "count": count,
                                  "outcome": "over" if count >= threshold else "under",
                                  "reasons": []}})
        if i % 10 == 0 and count:
            changed = deepcopy(case)
            closure = changed["facts"][-1]
            changed["facts"].append(revised(changed["facts"][0], 0,
                                             received_at="2026-11-04T08:00:00Z"))
            changed["facts"].append(revised(closure, count - 1,
                                             received_at="2026-11-04T08:01:00Z"))
            rows.append({"name": f"match-{i:03d}-corrected", "input": changed,
                         "expected": {"status": "settled", "count": count - 1,
                                      "outcome": "over" if count - 1 >= threshold else "under",
                                      "reasons": []}})
    return rows
