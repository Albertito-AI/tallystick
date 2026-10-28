# Recorded correction-aware match replay

Executed on 28 October 2026 from
[`04502d4f1ec34ee52866c8441e12b0d4440d1309`](https://github.com/Albertito-AI/tallystick/tree/04502d4f1ec34ee52866c8441e12b0d4440d1309).
Environment: CPython 3.12.14, cryptography 50.0.2 and Node.js 24.22.1 on Linux x86_64.
The README image is an illustration of observed results, not a browser screenshot.

## Input and reproduction

[The synthetic scenario](../../examples/synthetic-match.json) supplies fictional
corner observations, source roles, correction events and completeness declarations.
Its supported market asks whether there are at least five second-half corners.
An "official" source is a configured test role, not an authenticated sports supplier.

After the [documented installation](../../README.md#run-it), from the repository root:

```sh
PYTHONPATH=src python -m tallystick demo --output run/readme-demo
PYTHONPATH=src python -m tallystick verify run/readme-demo/dispute.json --public-key-file run/readme-demo/public-key.txt
```

Use a new output directory. Both commands exited with status 0 in the recorded run,
which used a temporary directory instead of `run/readme-demo`.

| Observed stage | Status | Outcome | Count |
| --- | --- | --- | --- |
| Provisional observation | `pending` | none | unavailable |
| Corroborated observation | `pending` | none | unavailable |
| Six observations and matching closure | `settled` | `over` | 6 |
| Correction before revised closure | `pending` | none | unavailable |
| Corrected count and closure of five | `settled` | `over` | 5 |
| Correction and closure reduce count to four | `settled` | `under` | 4 |

The first two pending results retain `missing_closure`. The correction/closure
disagreement retains `closure_count_mismatch`. Earlier records remain available.
The separate verifier returned `valid: true`, `entries_verified: 20` and
`decisions_verified: 6`, ending with `under` at count 4.

## Inspect the actual viewer and verify this recorded bundle

Open [index.html](index.html) from your checkout. It is the unmodified generated
offline report. GitHub displays its HTML source. The associated [synthetic bundle](dispute.json)
and [demo public key](public-key.txt) are kept beside it for the viewer's download link.
No private key is exported. Verify the stored example from the repository root:

```sh
PYTHONPATH=src python -m tallystick verify docs/demo/dispute.json --public-key-file docs/demo/public-key.txt
```

[The recorded stdout, verifier result and file hashes](recorded-run.json) bind
this example to its source revision. Each fresh demo generates a different
recorder key, so signatures, hashes and key bytes will differ on your machine.

This proves consistency with the supplied demo key and synthetic history. The
key is distributed with the example; it is not an independent identity anchor.
The result authenticates no real sporting fact, supplier, licence or trusted time.
The `settled` field is a replay state and creates no wager or financial settlement.

The local suite ran 142 tests: 141 passed; one report-server test was blocked by
the execution sandbox's prohibition on loopback sockets. No runtime was changed
to bypass that restriction. This change's hosted checks report the full suite
on their exact commit. No new browser-interaction, human-use or production result
is inferred from these runs.
