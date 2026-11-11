# RFC 0001: independent semantic review packet

Status: **prepared for independent review, not yet submitted or approved**. Originally prepared on 28 October 2026 for the
existing [draft PR #1](https://github.com/Albertito-AI/tallystick/pull/1).
This is an AI-assisted first-party review aid, not an independent review,
external reproduction, or a normative statement about a live feed.

## Proposed contract and scope

The candidate adds a second condition to closure acknowledgement: a selected
value-changing occurrence revision must both (a) have `received_at` no later
than the active closure's `received_at`, and (b) appear before that closure
revision in the recorder's append-order facts. Otherwise a matching aggregate
is `pending/stale_closure`.

This proposal applies to the synthetic count-market research contract. It does
not authenticate a source, validate a real operator's causal message ordering,
extend a data licence, or make a live settlement decision. The existing
[proposed RFC](rfc-0001-closure-ack-order.md) gives the implementation rationale.

## Two ordering concepts to scrutinise

1. **Declared receipt time.** `received_at` is carried in the fact record and
   is validated for format and within-observation monotonicity. It is not
   independently authenticated trusted time.
2. **Recorder append order.** The position in the supplied full log represents
   the local order in which records were appended. It is not independently
   authenticated upstream emission order, and delayed historical ingestion may
   invert the provider's causal order.

A reviewer should decide whether requiring *both* conditions is appropriate
for this bounded local replay contract. If an operator supplies final aggregate
records and individual occurrences on separate channels or imports backlog
out of order, this test can remain pending even though an upstream authority's
closure was valid. That may be a deliberate conservative limit, but its cost
and the required re-acknowledgement procedure must be explicit before freeze.

## Review matrix

Use fictional observations only. The results below are either covered by the
existing regression suite or identified as a further contract question. A case
marked "inspect" is **not** a claimed passing test.

| ID | History and time relationship | Candidate result | Evidence or unresolved question |
| --- | --- | --- | --- |
| R01 | Closure logged before two offsetting value corrections, all with equal receipt timestamps; aggregate unchanged | `pending/stale_closure` | New Python and independent JS regression in PR #1 |
| R02 | Fresh same-count closure revision logged after both corrections, also at the tied timestamp | `settled` if other gates pass | New regression in PR #1 |
| R03 | Closure logged after corrections, but its receipt timestamp is earlier than a correction's | `pending/stale_closure` | Provisional Python/independent JavaScript regression added 30 October; semantic review pending |
| R04 | Closure logged before a later appended correction, but the closure has a later declared receipt timestamp | `pending/stale_closure` | Provisional Python/independent JavaScript regression added 30 October; delayed-import interpretation remains open |
| R05 | Only an evidence-state promotion follows closure, with no value change | Unchanged settlement if other gates pass | Existing state-promotion tests |
| R06 | A related value-changing correction is beyond the `as_of` receipt cutoff | Earlier historical result remains available | Existing historical replay tests; examine clock/append assumptions |
| R07 | Closure count and active occurrence sum disagree | `pending/closure_count_mismatch` before freshness check | Existing precedence tests |
| R08 | A new first-version occurrence is appended after closure, and its value makes the earlier declared aggregate match | **Inspect: current implementation may settle** | The freshness helper traverses superseding value revisions, not initial occurrence insertions. Decide whether closure must acknowledge these, or whether late ingestion after an authoritative total is permitted. Do not silently change R01/R02 rules to resolve this |
| R09 | A zero-valued initial occurrence is appended after a matching zero closure | **Inspect: current implementation may settle** | Clarify whether such records alter completeness without changing the aggregate |
| R10 | A final observation is revised after finality | Reject malformed history | Existing revision-validation rule |
| R11 | Two distinct active closures for the same metric and period | `pending/ambiguous_closure` | Existing closure test |
| R12 | An unrelated event or different metric changes after closure | No effect on selected market | Existing unrelated-history tests |

For R08/R09, the finding is an analytical question about the relation between
a closure's declared *aggregate* and the set of individually received records.
It is not a verified exploit, and the intended semantics could legitimately
accept a backfill. The independent reviewer should give a concrete counterexample,
interpretation and expected result, rather than accepting a generic assertion
that any later append invalidates a closure.

## R08/R09 decision gate: late first-version observations (31 October 2026)

The current helper tests whether **superseding value revisions** predate an
active closure. A new *first-version* observation has no predecessor and is not
included in that revision check. The reviewer must decide whether this hybrid
treatment of initial records and corrections is intentional. The examples below
are analytical source-code characterisations, **not** independently executed
tests or an approved specification. They assume a single fictional event,
period 2, official fact states, matching deadlines and a market threshold of
five, evaluated after all stated receipts.

| Case | Recorder append history | Count before / after later record | Code-path characterisation | Decision needed |
| --- | --- | --- | --- | --- |
| R08 | Closure(count=1), then new corner(value=1) | 0 / 1 | Closure-only initially has closure_count_mismatch; the later first-version fact can make the total match and settle under, without a new closure | Can a previously declared aggregate cover a later locally recorded occurrence? |
| R09 | Closure(count=0), then new corner(value=0) | 0 / 0 | Both the closure-only history and the history containing the later first-version zero can settle under; no value-changing revision is detected | Does an initial zero-valued occurrence carry completeness meaning, or must zero require a superseded earlier positive record? |
| Control | Corner(value=1), then closure(count=1) | 1 | The normal aggregate-matching history can settle under | Record the distinction from R08 explicitly |
| Mismatch | Corner(value=1), then closure(count=0) | 1 | closure_count_mismatch | Confirms aggregate disagreement is a separate gate |

Both R08 and R09 should be reproduced by an independent implementer against
the exact candidate commit before treating the code-path description as an
observed execution result. Use the fictional fixture constructors in
conformance/fixtures.py and the independent evaluator
conformance/reference.mjs. Capture input JSON, receipt/append ordering,
as_of, Python output, JavaScript output and environment; do not put a
provisional expected result into a normative regression test merely to make
the suite green.

The current reference behaves as **aggregate reconciliation for newly inserted
observations**, while proposing **append-order acknowledgement for value
corrections**. That combination can be deliberate, but it is not equivalent to
proof that a source has acknowledged every individual message.

Three models are available for an explicit independent decision, not as new
implemented features:

1. **Aggregate-only closure:** a source attests the final aggregate, not a
   recorder prefix. Late first-version observations may make the sum agree;
   the local count match remains insufficient to authenticate the source,
   finality or full coverage.
2. **Local prefix acknowledgement:** every relevant first-version observation
   and value correction must precede the closure in recorder append order.
   R08/R09 would need fresh acknowledgement even for a zero-valued record;
   legitimate delayed and bulk imports could be left pending.
3. **Source-versioned acknowledgement:** a signed or otherwise authenticated
   provider sequence/watermark declares the exact coverage. This is not
   implemented or available from the fictional example, and may require an
   additional schema/source profile rather than a change to this evaluator.

For the final decision, the reviewer should record the selected interpretation,
a counterexample it rejects, the expected statuses for R08/R09, handling of
same-time ties and historical as_of, whether initial zero records are valid
under the factual ontology, and the source evidence required for a new closure.
Where no defensible source contract exists, keep the historical adapter and
production claims gated rather than silently selecting a model. A decision and
new tests must precede any D1 semantic freeze; an AI-authored decision grid is
not independent approval.

## Local cross-language characterisation for R08/R09 (1 November 2026)

The draft includes `test_postclosure_initial_observations_characterisation`
in `tests/test_conformance.py`. It constructs six fictional control/history
cases covering a positive initial occurrence appended after closure, a zero
initial occurrence appended after closure, and their pre-closure controls.
The test requires the Python and independent JavaScript evaluators to agree,
but **deliberately does not prescribe** either contested post-closure outcome.
Only the existing pre-insertion aggregate-mismatch gate has an asserted result.

This is a first-party regression *characterisation*, not semantic approval,
provider authentication or independent reproduction. Check the exact candidate
commit's CI before treating the new test as successfully executed. The reviewer
still needs to decide R08/R09 expected statuses and source-acknowledgement
semantics; later normative assertions should follow that decision.

## Reviewer's required questions

- What event exactly constitutes source acknowledgement of a correction:
  the declared time, the local append event, an upstream sequence/message ID,
  or an expressly versioned closure reference?
- Is a new closure revision with unchanged count a genuine source statement
  or merely a locally synthesised update? If the latter, how is its authority
  documented and how are invented acknowledgements prohibited?
- Are late, re-ordered or batched historical records expected? Does the proposed
  rule make such legitimate imports permanently pending?
- Should new observations after closure, including zero-valued records, have
  the same freshness requirement as revisions? Distinguish aggregate agreement
  from source-supported completeness.
- Is the `as_of` cut based on declared receipt time consistent with the
  proposed append-order requirement during retrospective replay?
- Do the Python and independent JavaScript evaluators reject or classify
  malformed and adverse histories identically, and does the exact candidate
  revision pass the CI matrix after any change?

## Reproducibility procedure for a non-implementing reviewer (5 November 2026)

Record the *exact* 40-character PR commit SHA at the start of the review; do not
use a moving branch name as the reviewed version. Work from an independent fresh
checkout with Python 3.11 or later and Node.js 22 or later. The commands below
are instructions, not a claim that a third party has run them:

```sh
git clone https://github.com/Albertito-AI/tallystick.git
cd tallystick
git fetch origin pull/1/head:review-pr-1
# Replace REVIEW_SHA with the recorded exact commit SHA (from this PR).
git checkout --detach REVIEW_SHA
git rev-parse HEAD
python -m venv .venv
# Activate the environment for your shell, then:
python -m pip install -e .
python --version
node --version
python -m unittest discover -s tests -p test_conformance.py -v
python -m unittest discover -s tests -p test_settlement.py -v
```

If Node.js cannot run, record the absence as **not reproduced**, even if Python
unit tests pass; the conformance suite can skip Node-dependent checks. Capture
exit codes, full outputs, platform/runtime versions and any assistance received.
If installation or execution fails, retain the failure report. A clean-run receipt
requires observed commands and results from an actual non-implementing person.

A **semantic review** is a separate exercise. Before comparing with the current
implementation, a competent domain reviewer should record independently reasoned
expected statuses and reasons for R01–R12, particularly R08/R09, zero-valued
first records, time ties, delayed import and source acknowledgement. Include the
source authority and completeness assumptions, counterexamples and whether
provider-specific messages would require a different profile. Mark any case
**underdetermined** rather than inventing normative expectations. The recorded
Python/JavaScript agreement characterises current code; it cannot adjudicate
correctness. In a review receipt, distinguish (a) independent semantic findings,
(b) independent execution, and (c) the maintainer's disposition of differences.

After adjudication, update the existing PR's proposed semantics and tests, then
combine it safely with the current main branch, run CI on the *exact combined
commit* and record a compatibility decision. Do not infer these steps from
mergeability or earlier green runs. No independent review, external reproduction
or integrated-candidate verification was completed by adding this procedure.


## Temporal replay and signed-checkpoint question (11 November 2026)

**Status: first-party source analysis; proposed executable characterisation, not a test
result, semantic decision, independent reproduction or defect finding.** This
extends R06/R08/R09 within RFC 0001; it does not start another RFC or change
the settlement rule. At draft head \`be06d53b113d94ab480271a018786078cc483b2d\`,
\`active_snapshot(facts, as_of)\` scans the *supplied full history*, validates
append-order revisions, and selects observation heads whose declared
\`received_at <= as_of\`. No separate authenticated ledger-prefix, insertion
sequence at a prior checkpoint, or original operator-decision record is an
input to \`evaluate\`.

The same declared cutoff can therefore yield different results when a later
supplied history contains a new first-version record declaring an older/equal
receipt time. That does not establish wrong behaviour: a receipt-time replay
of the *currently supplied evidence* and an "as known by this recorder at its
earlier decision" reconstruction are different evidential questions.

| Fictional history supplied to evaluator | Declared \`as_of\` | Source-derived result to test, **not observed here** |
| --- | --- | --- |
| H0: \`closure(0)\` | \`TIME\` | \`settled/under\` with closure-only \`fact_ids\` |
| H1: H0, then \`fact("late-positive", value=1)\` appended later with \`received_at=TIME\` | same \`TIME\` | \`pending/closure_count_mismatch\`; new occurrence appears in \`fact_ids\` |
| H2: H0, then \`fact("late-zero", value=0)\` appended later with \`received_at=TIME\` | same \`TIME\` | \`settled/under\` but \`fact_ids\` includes the new zero-valued occurrence |

This minimal script deliberately *prints* observed outputs rather than
asserting that a particular unresolved closure contract is correct. It uses
the repository's fictional TEST fixtures. Pin a real 40-character commit SHA
in an isolated checkout before executing, and record that SHA, runtime
versions, exact output and assistance:

~~~python
import sys
sys.path.insert(0, "tests")
from fixtures_core import TIME, closure, fact, market
from tallystick.settlement import evaluate

h0 = [closure(0)]
h1 = h0 + [fact("late-positive", value=1, received_at=TIME)]
h2 = h0 + [fact("late-zero", value=0, received_at=TIME)]
for label, history in (("H0", h0), ("H1", h1), ("H2", h2)):
    r = evaluate(market(), history, as_of=TIME)
    print(label, r["status"], r["outcome"], r["reasons"], r["fact_ids"])
~~~

**Independent reviewer decision required:** Is \`as_of\` expressly only a
declared-receipt-time filter over available history, or is reconstruction of
what an operator knew at a signed earlier checkpoint also promised? If the
latter, identify the externally trustworthy evidence needed to bind a local
append-prefix/checkpoint, rule version, authenticated receipt order and
historical source acknowledgement. Decide separately how H1/H2, delayed
imports, late first-version observations and value corrections affect closure
completeness. A locally signed prefix cannot itself prove upstream truth,
source completeness or data-use rights. Mark insufficiently specified cases
**underdetermined** pending actual provider-specific authority.

**Acceptance gate:** two real non-implementers execute this and the established
R01–R12 tests on the *same exact reviewed candidate* and report actual output,
environment, observed discrepancies and assistance; an independent domain
reviewer first supplies reasoned expected semantics. The maintainer then
disposes of findings in the existing draft PR and validates a guarded
combination with current main. Neither this section nor the current green
separate-branch CI satisfies D1, D2 or L1. No customer dataset, production
settlement or payment operation is involved.

## Independent-review receipt

Record the reviewer identity or consented public handle, relevant expertise,
independence from the implementation, date, exact commit SHA, commands and test
environment. Capture R01-R12 findings individually: agreement, disagreement,
unavailable evidence, or a concrete proposed counterexample. Include whether
a new source profile is required instead of changing the general contract.

Review completion requires an actual competent reviewer, recorded substantive
findings, resolution of critical disagreements, updated semantic and conformance
cases, and a final exact-commit check. A green workflow, a maintainer or
AI-generated critique, and a mergeable draft do **not** satisfy independent
semantic review, D1 freeze or D2 independent reproduction.

## Historical evidence and next gate

The 28 October note recorded draft head `d5064a0973d2ee24912b98c9d90d8318c9556111`
and an earlier base. The later 1 November characterisation commit was
`28605c97cd12d2fa04cded41357baef6ab42f04a`; both are **historical
snapshots**, not a claim about the latest head. In the 5 November pre-edit check,
main was `d729c695cae47f0075564f5f206f938096726c02`, PR #1 was open/draft
at `28605c97cd12d2fa04cded41357baef6ab42f04a`, no submitted independent
review or discussion comments were found, and the PR and main had diverged
(seven ahead, ten behind). The last recorded PR implementation CI was successful
at that PR SHA, but no combined-tree validation had occurred.

**Next owner:** Albert to secure a competent independent reviewer and two actual
non-implementer reproductions, using the current pinned PR SHA. The maintainer
must record findings and counterexamples in this existing PR, adjudicate the
proposed contract, reconcile the current main branch and verify exact-combined
CI before proposing D1 freeze or merge. This document authorises no new customer,
licensed-feed, financial or external communication operation.
