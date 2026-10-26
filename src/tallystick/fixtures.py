"""Entirely fictional inputs. No live competition, licence or legal clearance is represented."""
from copy import deepcopy

AS_OF = "2026-01-01T12:00:00Z"
DEADLINE = "2026-01-02T14:00:00Z"


def configuration() -> dict:
    kinds = ["corner.awarded", "goal.scored", "period.closed", "event.abandoned"]
    sources = {
        "demo-feed-a": {"independence_group": "fictional-a", "official_kinds": []},
        "demo-feed-b": {"independence_group": "fictional-b", "official_kinds": []},
        "demo-official": {"independence_group": "fictional-official", "official_kinds": kinds},
    }
    licence = {"schema_version": "0.1", "licence_id": "synthetic-licence", "source_ids": list(sources),
               "uses": ["display", "pricing", "settlement", "redistribution"], "territories": ["TEST"],
               "valid_from": "2026-01-01T00:00:00Z", "valid_until": "2027-01-01T00:00:00Z",
               "fact_types": kinds, "synthetic": True}
    rule = {"schema_version": "0.1", "rulepack_id": "TEST-2026", "version": "0.1.0",
            "jurisdiction": "TEST", "basis": "synthetic", "reviewer": "Fictional test-policy author",
            "reviewed_at": "2025-12-31T00:00:00Z", "valid_from": "2026-01-01T00:00:00Z",
            "valid_until": "2027-01-01T00:00:00Z", "allow_consumer": False,
            "min_window_seconds": 900, "allowed_fact_types": ["corner.awarded", "goal.scored"],
            "required_state": "official"}
    market = {"schema_version": "0.1", "market_id": "demo-corners-h2-over-4.5",
              "event_id": "synthetic-match-001", "name": "Fictional second-half corners over 4.5",
              "settlement": {"fact_type": "corner.awarded", "period": 2, "threshold": 5, "min_state": "official"},
              "outcomes": ["over", "under"], "close_at": "2026-01-01T12:45:00Z",
              "correction_deadline": DEADLINE, "jurisdiction": "TEST", "licence_id": "synthetic-licence",
              "rulepack_id": "TEST-2026", "consumer": False, "window_seconds": 2700,
              "participant_scope": "aggregate", "batch_window_ms": 250}
    return {"sources": sources, "licences": [licence], "rulepacks": [rule], "market": market}


def fact(number: int, *, value: int = 1, state: str = "official", revision: int = 1,
         received_at: str | None = None, supersedes: str | None = None, reason: str | None = None) -> dict:
    occurred = f"2026-01-01T13:{number:02d}:00Z"
    return {"schema_version": "0.1", "fact_id": f"corner-{number}-r{revision}",
            "observation_id": f"corner-{number}", "event_id": "synthetic-match-001",
            "kind": "corner.awarded", "period": 2, "subject": "home" if number % 2 else "away",
            "value": value, "state": state, "source_ids": ["demo-official"] if state in {"official", "final"}
            else (["demo-feed-a", "demo-feed-b"] if state == "corroborated" else ["demo-feed-a"]),
            "licence_id": "synthetic-licence", "occurred_at": occurred,
            "received_at": received_at or occurred, "supersedes": supersedes, "reason": reason,
            "correction_deadline": DEADLINE, "metric": None}


def closure(count: int, *, revision: int = 1, received_at: str = "2026-01-01T13:45:00Z") -> dict:
    return {"schema_version": "0.1", "fact_id": f"closure-r{revision}", "observation_id": "period-2-closure",
            "event_id": "synthetic-match-001", "kind": "period.closed", "period": 2, "subject": "all",
            "value": count, "state": "official", "source_ids": ["demo-official"], "licence_id": "synthetic-licence",
            "occurred_at": "2026-01-01T13:45:00Z", "received_at": received_at,
            "supersedes": f"closure-r{revision - 1}" if revision > 1 else None,
            "reason": "Fictional corrected authoritative count" if revision > 1 else None,
            "correction_deadline": DEADLINE, "metric": "corner.awarded"}


def scenario() -> dict:
    conf = configuration()
    provisional = fact(1, state="provisional")
    corroborated = fact(1, state="corroborated", revision=2, received_at="2026-01-01T13:01:00.625Z", supersedes="corner-1-r1")
    official = fact(1, revision=3, received_at="2026-01-01T13:01:02Z", supersedes="corner-1-r2")
    corrected6 = fact(6, value=0, revision=2, received_at="2026-01-01T14:00:00Z", supersedes="corner-6-r1", reason="Fictional reclassification to a goal kick")
    corrected5 = fact(5, value=0, revision=2, received_at="2026-01-01T14:10:00Z", supersedes="corner-5-r1", reason="Second fictional reclassification")
    conf.update(schema_version="0.1", synthetic=True, compiled_at=AS_OF, stages=[
        {"name": "Provisional observation", "as_of": "2026-01-01T13:01:00Z", "facts": [provisional]},
        {"name": "Corroborated observation", "as_of": "2026-01-01T13:01:00.625Z", "facts": [corroborated]},
        {"name": "Official count of six", "as_of": "2026-01-01T13:45:00Z", "facts": [official] + [fact(i) for i in range(2, 7)] + [closure(6)]},
        {"name": "Correction received before revised closure", "as_of": "2026-01-01T14:00:00Z", "facts": [corrected6]},
        {"name": "Corrected count of five", "as_of": "2026-01-01T14:00:01Z", "facts": [closure(5, revision=2, received_at="2026-01-01T14:00:01Z")]},
        {"name": "Correction changes outcome to under", "as_of": "2026-01-01T14:10:01Z", "facts": [corrected5, closure(4, revision=3, received_at="2026-01-01T14:10:01Z")]},
    ])
    return deepcopy(conf)
