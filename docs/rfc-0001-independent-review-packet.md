# RFC 0001: independent semantic review packet

Status: **review requested, not approved**. Prepared on 28 October 2026 for the
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

## Current evidence and next gate

On 28 October 2026, PR #1 remained draft at
`d5064a0973d2ee24912b98c9d90d8318c9556111`, with no submitted PR
reviews or discussion comments. Its earlier five CI jobs passed for that exact
head at
https://github.com/Albertito-AI/tallystick/actions/runs/40470922928 .
The default branch has since advanced to
`04502d4f1ec34ee52866c8441e12b0d4440d1309` through CI-hardening
changes. Recheck the current head and run results before any later merge.

**Next owner:** Albert to secure a competent independent reviewer, supported by
the Tallystick maintainer's self-contained reproduction and review packet.
Keep the PR in draft until the findings are adjudicated. No customer or
licensed-feed use is authorised by this document.
