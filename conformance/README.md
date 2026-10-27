# Settlement conformance

The JavaScript evaluator is a separate implementation of the bounded settlement
contract. It does not import the Python evaluator. It receives full append-order
fact histories as JSON, resolves observation revisions at the supplied `as_of`
time, and produces the same result fields.

The scope is semantic agreement on valid ledger histories. Source authentication,
licence enforcement, signature verification, database transactions and service
access controls belong to the main implementation and its separate tests.
Agreement between these implementations does not establish sporting truth or
correctness for markets outside the specified count language.

## Run

From the repository root, with Python and Node.js available:

```sh
python -m pip install -e .
python -m unittest discover -s tests -p test_conformance.py -v
```

The suite checks a deterministic **380-match synthetic season**, with 36 separate
corrected snapshots (416 season evaluations in total), and 23 named edge cases. Every
match and source is invented; no historical season or licensed feed is included.
Known-answer outcomes are derived from generated counts and thresholds without
calling either evaluator.

The edge cases cover a complete upper and lower outcome, a zero count with an
explicit closure, absent data, missing or conflicting closure records, incomplete
feeds, insufficient evidence states, confirmed and unconfirmed abandonment,
deadline mismatch, a correction that changes the outcome, historical replay,
finalisation and a second supported metric. Offsetting corrections require a fresh
closure even when their net count is unchanged; an evidence-state promotion alone
does not. A separate regression compares both evaluators when a closure and
later-appended offsetting corrections declare identical receipt timestamps.
The closure remains stale until a new acknowledgement is appended. Additional tests check that unrelated
events, unrelated periods and future corrections do not change an earlier
decision, and that independent observations can be reordered without changing
the result.

The initial shared contract supports `corner.awarded` and `goal.scored` with
binary occurrence values, an integer threshold and `period.closed` evidence.
The full signature and result format are documented in the settlement semantics.

For an individual JSON case:

```sh
node conformance/reference.mjs < case.json
```

Input is `{ "market": {...}, "facts": [...], "as_of": "2026-11-04T10:00:00Z" }`.
An array of such cases is also accepted. Invalid input exits with status 2 and
an error on stderr. Node.js is required for the cross-language tests; the unittest
suite records a skip when it is unavailable rather than claiming agreement.

`fixtures.py` is the independently authored synthetic generator.
`golden.json` provides portable named inputs and known-answer fields for other
implementations. Regenerate it only when the reference contract intentionally
changes and record the reason for that change.
