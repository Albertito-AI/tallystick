"""Explicitly fictional records shared by recorder and settlement tests."""
from __future__ import annotations

import copy

TIME = "2026-10-26T20:30:00Z"
DEADLINE = "2026-10-26T23:00:00Z"


def sources() -> dict:
    return {
        "official": {"independence_group": "fictional-league", "official_kinds": [
            "corner.awarded", "goal.scored", "period.closed", "event.abandoned"]},
        "feed-a": {"independence_group": "vendor-a", "official_kinds": []},
        "feed-a-copy": {"independence_group": "vendor-a", "official_kinds": []},
        "feed-b": {"independence_group": "vendor-b", "official_kinds": []},
    }


def fact(index: int | str = 1, **overrides) -> dict:
    value = {
        "schema_version": "0.1", "fact_id": f"f-{index}-v1",
        "observation_id": f"observation-{index}", "event_id": "fictional-match-1",
        "kind": "corner.awarded", "period": 2, "subject": "home", "value": 1,
        "state": "official", "source_ids": ["official"], "licence_id": "fixture-licence",
        "occurred_at": "2026-10-26T20:00:00Z", "received_at": TIME,
        "supersedes": None, "reason": None, "correction_deadline": DEADLINE,
        "metric": None,
    }
    value.update(overrides)
    return value


def closure(count: int, index: str = "closure", **overrides) -> dict:
    value = fact(index, kind="period.closed", subject="all", value=count, metric="corner.awarded")
    value.update(overrides)
    return value


def revision(previous: dict, suffix: str = "v2", **overrides) -> dict:
    value = copy.deepcopy(previous)
    value.update(fact_id=f"{previous['observation_id']}-{suffix}",
                 supersedes=previous["fact_id"], received_at="2026-10-26T21:00:00Z")
    value.update(overrides)
    return value


def market(**overrides) -> dict:
    value = {
        "schema_version": "0.1", "market_id": "fictional-corners-over-4.5",
        "event_id": "fictional-match-1", "name": "Fictional second-half corners",
        "settlement": {"fact_type": "corner.awarded", "period": 2,
                       "threshold": 5, "min_state": "official"},
        "outcomes": ["over", "under"], "close_at": "2026-10-26T19:45:00Z",
        "correction_deadline": DEADLINE, "jurisdiction": "TEST",
        "licence_id": "fixture-licence", "rulepack_id": "fixture-rules",
        "consumer": False, "window_seconds": 2700,
    }
    value.update(overrides)
    return value
