# Validation record

Version 0.1.0 was checked on 26 October 2026. These results concern the supplied
synthetic fixtures and stated test boundaries. They do not establish production
fitness, a legal permission, real-feed completeness, sporting truth or a security
certification.

## Executed locally

| Check | Observed result |
| --- | --- |
| Full Python suite, Python 3.12 | 142 tests passed, zero failures, errors or skips |
| Independent JavaScript settlement | 23 named golden cases and 416 season snapshots agreed with Python |
| Synthetic season | 380 fictional matches, including 36 additional corrected snapshots |
| End-to-end example | 20 signed entries, 13 fact revisions, six reproduced decisions; latest count four, outcome under |
| Correctly signed adversarial bundles | Inconsistent historical decisions, certificate claims, configuration, timestamps and summaries were rejected |
| Optional pricing solver | SciPy 1.17.0 was present; finite-outcome witness checks and independent Poisson comparisons passed |
| Real subprocess MCP checks | 11 tests passed, including framing, per-request metadata, source authority and isolated previews |
| Local HTTP integration | Verified-input startup and fixed routes passed; unknown and file-traversal routes returned 404 |
| Browser interaction | Chrome Headless Shell 156.0.8078.47 passed all ten interaction/layout checks at desktop and mobile sizes |
| Packaging | Editable installation and wheel build succeeded; the wheel imported from outside the checkout |
| Settlement TLA+ model | 1,267 generated states, 195 distinct states, no configured invariant violation |
| Acceptance TLA+ model | 87 generated states, 26 distinct states, no configured invariant violation |

The full test suite includes the CLI, compiler, ledger, rights, complete-log
verifier, settlement, batch gateway, pricing, MCP and independent conformance.
The local suite was rerun after the final closure-freshness and equivalent-UTC
corrections. An environment permission was needed to create the loopback socket
used by the HTTP test; the test then executed successfully and was not skipped.

The browser check exercised initial rendering, timeline buttons, the stage
slider, the evidence table, the verification view, evidence download, pricing,
mobile width, JavaScript errors and external page requests. An initial mobile
tab overflow was corrected, and the complete check then passed. The report uses
no external page requests. Browser testing was separate from the unit suite.

## Reproduce

After installing the package and Node.js 22 or later:

```sh
python -m unittest discover -s tests -v
python -m tallystick demo --output run/validation-demo
python -m tallystick verify run/validation-demo/dispute.json --public-key-file run/validation-demo/public-key.txt
python -m tallystick batch-example
```

Install `.[coherence]` to run solver-dependent checks instead of their explicit
unavailable-solver branches. For the bounded models, follow the pinned-tool
instructions in [tla/README.md](../tla/README.md). The committed
[model receipt](../tla/execution-record.json) includes exact source and
configuration hashes, tool identity, state counts and checker output.

The optional browser script needs Playwright as a separately installed
development tool. It does not add a browser or JavaScript runtime dependency to
the Python package. With a report server running:

```sh
node scripts/check-dashboard.cjs http://127.0.0.1:8765 run/browser-check
```

`TALLYSTICK_CHROMIUM` can select an installed Chromium-compatible executable.
The script saves desktop/mobile screenshots and a JSON receipt. Its expected
counts describe the bundled demo, not every possible user-supplied scenario.

## Continuous integration

[The workflow](../.github/workflows/checks.yml) runs the full suite and a fresh
CLI replay on Ubuntu with Python 3.11 and 3.14, and Windows with Python 3.12.
Separate jobs check optional SciPy pricing and the pinned bounded models.
Node.js 22 is installed in every full-suite job. Action references are pinned to
the official action commit SHAs checked during this build. Read the result for
the exact commit in GitHub Actions; a workflow definition alone is not evidence
that its jobs passed.

The local operating system was Linux. Windows and other Python-version outcomes
must be read from the relevant CI run. The development-container configuration
uses the documented official Python image and Node feature, but Docker was not
available for a local container build. No Codespace or hosted production service
was provisioned during local validation.

## Remaining boundaries

There is no measured production throughput, load or fault-tolerance result.
No external sports feed, operator, payment service, legal policy issuer or
timestamp witness participated. Source groups and batch watermarks are fixture
declarations. The TLA+ models are bounded abstractions with no implementation
refinement or liveness proof. The independent evaluator tests agreement on valid
histories, while ingestion and adversarial-signature checks have their own tests.

The JSON Schemas were checked for parsing, internal references and field
correspondence with application validators. An independent JSON Schema validator
was not installed for this build. Structural schemas cannot replace the
application's authority, revision, chronology and policy checks.
