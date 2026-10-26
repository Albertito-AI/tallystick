# Synthetic batch acceptance

`tallystick.gateway.BatchSimulator` is an in-memory experiment for bounded mandates, reservation caps, common closing quotes, and source-watermark gates. It processes synthetic integer units. It does not connect to an operator, authenticate an agent, hold cash, place a wager, or accept a consumer mandate.

The simulator makes a distinction that matters for the paper's timing example: a 250 ms batch timer cannot establish that a corroborating source with a 625 ms delay has finished reporting. A batch remains pending until every configured source explicitly advances its event-time watermark to the batch boundary. These watermarks are declarations supplied by a test caller; the simulator does not verify a signed provider completeness claim.

## Runnable example

```python
from tallystick.gateway import BatchSimulator

sim = BatchSimulator(
    window_ms=250,
    required_sources=["demo-official"],
    max_market_units=1000,
    max_family_units=600,
)
sim.register_mandate({
    "mandate_id": "mandate-a",
    "agent_id": "agent-a",
    "model_family": "family-a",
    "market_ids": ["corners"],
    "max_stake_units": 200,
    "budget_units": 500,
    "valid_from_ms": 0,
    "valid_until_ms": 2000,
    "revoked": False,
    "consumer": False,
})

for request_id, arrival_ms in (("r1", 100), ("r2", 110)):
    receipt = sim.submit({
        "request_id": request_id,
        "market_id": "corners",
        "mandate_id": "mandate-a",
        "stake_units": 100,
        "min_decimal_odds": "2.40",
    }, received_at_ms=arrival_ms)
    assert receipt["status"] == "QUEUED"

pending = sim.close_batch(250, {"corners": "2.53"}, now_ms=250)
assert pending["status"] == "PENDING"
assert pending["reason"] == "SOURCE_WATERMARK_PENDING"

sim.advance_watermark("demo-official", event_time_ms=250)
closed = sim.close_batch(250, {"corners": "2.53"}, now_ms=725)
assert closed["status"] == "CLOSED"
assert all(d["status"] == "ACCEPTED" for d in closed["decisions"])
assert all(d["decimal_odds"] == "2.53" for d in closed["decisions"])
assert sim.exposure()["market_units"]["corners"] == 200
```

The 2.53 quote is an illustrative input. The gateway neither generates that quote nor attests to its accuracy. The pricing module can calculate hypothetical quotes separately; no automatic risk decision is inferred from such a calculation.

## Interface and records

| Method | Result and meaning |
| --- | --- |
| `register_mandate(mandate)` | Validates and stores one immutable mandate; returns a copy |
| `revoke(mandate_id)` | Marks a known mandate revoked; pending submissions are checked again at close |
| `submit(intent, received_at_ms)` | Returns an immutable submission receipt, either `QUEUED` or `REJECTED` |
| `advance_watermark(source_id, event_time_ms)` | Advances a required source's declared watermark monotonically |
| `close_batch(end_ms, quotes, now_ms)` | Returns `PENDING`, `HALTED`, or a `CLOSED` batch containing final request decisions |
| `observe_late(source_id, event_time_ms)` | Records a late-input incident; halts if it affects the closed interval |
| `get_request(request_id)` | Returns the latest disposition for one known request |
| `exposure()` | Returns pending plus accepted units by market, model family, and mandate |

Every mandate requires exactly the ten fields shown in the example. Every intent requires exactly its five fields. Unknown or missing fields raise `GatewayError`; its `code` identifies the error. Invalid input raises an exception before creating a submission receipt. Validly formed requests that fail a mandate, budget, exposure, or halt check receive a stored `REJECTED` receipt and a specific `reason`.

IDs are 1–80 characters drawn from ASCII letters, digits, underscore, hyphen, period, and colon. Units and times must be actual integers; booleans and floating-point substitutes are rejected. Odds must be plain decimal strings between 1 and 1,000,000,000, with no exponent notation and at most 12 fractional places. Values are compared using `Decimal`. Input and returned records are copied to prevent accidental mutation of stored state through a returned dictionary.

## Time and closure

Windows are half-open and aligned to zero. With a 250 ms window, arrival times from 0 through 249 belong to the batch ending at 250; an arrival at 250 belongs to the batch ending at 500. New submission arrival times and attempted close times cannot move backwards. Event-time watermarks are a separate timeline and never substitute for the simulated processing clock.

A close succeeds only when:

1. `end_ms` is an aligned batch boundary and `now_ms >= end_ms`.
2. No earlier batch still contains queued requests.
3. Every required source has a declared watermark at least as large as `end_ms`.
4. No late-input incident has halted the simulator.

Missing and stale source watermarks both leave a batch pending. Passing more wall-clock time does not override the gate. A caller may retry a pending close with updated inputs. Once closed, a batch is immutable: repeating its boundary with the same quote dictionary returns the original result; changing its quotes raises `BATCH_CONFLICT`. The returned `now_ms` remains the original close time.

Each queued request is revalidated at actual close time. A mandate valid at submission can expire while a batch waits for its sources. The validity interval is `valid_from_ms <= time < valid_until_ms`; revocation before close also causes rejection. Missing quotes and quotes below the intent's minimum cause rejection. All accepted requests in the same market and batch receive the same supplied closing quote, regardless of their minimum.

Decisions are ordered by a SHA-256 digest of an unambiguously encoded batch boundary, request ID, and market ID, with the request ID as a final tie-breaker. This order supports deterministic replay. It does not supply unpredictable randomness or proof of fairness: callers choose request IDs, and admission to the reserved capacity still occurs in arrival order.

## Authority and exposure

The simulator enforces each mandate's allowed markets, per-request unit limit, validity, revocation flag, and total unit budget. Re-registering an identical mandate is harmless. Reusing its identifier with different fields raises `MANDATE_CONFLICT`, including an attempt to restore a revoked mandate. Consumer mandates are explicitly unsupported.

A queued request reserves its units immediately against three counters:

- The market's cumulative limit across all registered mandates and model families.
- The model family's cumulative limit across its mandates and markets.
- The individual mandate's budget.

This catches attempts to split requests across accounts that declare the same model family. It does not authenticate those declarations or discover an undeclared common controller. All counters are local to one simulator instance; there is no registry across operators or processes.

A request rejected at submission reserves nothing. A request rejected at close releases its reservation exactly once. Accepted units remain in all three counters, so the displayed exposure is cumulative accepted plus pending units. There is no automatic balance credit, settlement release, netting, cancellation, or payout. Those would need their own explicit accounting semantics. The conservative cumulative counters cannot be interpreted as a real portfolio's net financial risk.

## Idempotency

The request ID binds to the exact validated payload and original `received_at_ms`. An identical retry returns the original submission receipt without adding another reservation. A different payload or timestamp under that ID raises `IDEMPOTENCY_CONFLICT`; even changing `"2.0"` to `"2.00"` counts as a payload change.

After a queued request closes, an exact `submit` retry still returns its historical `QUEUED` submission receipt. Use `get_request` to retrieve its final `ACCEPTED` or `REJECTED` disposition. An initially rejected request also retains its immutable receipt, even if circumstances later change. A fresh request needs a fresh ID.

## Late-input handling

`observe_late` only accepts a configured source. If the fact's event time is at or before the latest closed boundary, the simulator records `LATE_FACT_AFTER_CLOSE` and enters a global halt. Future new submissions are rejected and pending batches cannot close. Existing accepted records and reserved exposure are preserved for review; they are not silently rewritten or refunded.

The boundary comparison is deliberately conservative and inclusive, even though arrival windows are half-open. Facts after the latest closed boundary are recorded without a halt. There is no automatic recovery API or correction workflow in this module. It identifies the need for explicit review rather than inventing a financial remedy.

## Bounds and practical limits

Window sizes are 1–60,000 ms. An instance supports 1–16 distinct required sources, up to 1,000 mandates, up to 10,000 requests, up to 10,000 closed batches, and up to 1,000 late-input records. Each mandate allows at most 64 markets and a close accepts at most 64 market quotes. Unit values are bounded by `10**12`; timestamps are bounded by the largest exactly representable JSON integer, `2**53-1`. A capacity limit raises `CAPACITY_REACHED` and does not evict history.

This module is a single-threaded, in-memory replay component. It has no durability, distributed locking, signed mandate verification, provider transport, clock synchronization, or automatic integration with the append-only event ledger. Restarting the process discards its state. Direct access to Python object internals is not a security boundary. These limits are material if this experiment is adapted into a service.

## Verification

Run `python -m unittest discover -s tests -p test_gateway.py -v` after installing the package, or set `PYTHONPATH=src` from a checkout. The focused tests cover missing and stale source watermarks, the 625 ms delayed-feed case, uniform quotes, arrival boundaries, duplicate retries, changed ID reuse, split-account exposure caps, revocation and expiry before delayed close, reservation release, late-input halt, immutable returned records, input bounds, and deterministic replay ordering.

The timing figures are illustrative inputs from the foundational whitepaper. The tests establish the implemented state transitions under synthetic declarations. They do not validate an external provider's completeness, demonstrate resistance to all timing attacks, or establish production throughput.
