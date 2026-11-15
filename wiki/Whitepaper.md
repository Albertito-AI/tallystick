<!-- atlas-whitepaper:managed:v1 -->

# Tallystick: the difference between an observed event and a settled fact


## Abstract and method

Tallystick studies when a count derived from corrected observations can justify a recorded result. It separates declared authority, completeness, revision lineage and local ordering, then makes the decision reproducible from a signed synthetic history. Its present contribution is a bounded reference implementation and comparison evaluator, not a general truth oracle or live settlement service. This paper gives a correction counterexample, links claims to source and tests, and specifies what independent reproduction and semantic review must examine.

The 15 November 2026 revision is based on static inspection of the exact source revision below. Existing recorded demonstrations are distinguished from proposed reproduction. No repository code was executed for this paper revision, and no independent semantic sign-off is asserted.

## Thesis

A result derived from a stream of observations is only as dependable as its rules for completeness, correction and authority. Tallystick makes those rules explicit. Its reference workbench records sports observations, checks declared permissions, evaluates a bounded market rule and preserves enough history for another implementation to reproduce the decision.

The larger idea is that consequential systems should be able to explain what was known at the time, what later changed and why the result changed with it. A plausible final number is insufficient when people need to challenge an earlier decision.

Prepared for Albert Tan Sin Hon with AI assistance, 2 November 2026. This design paper concerns the inspected synthetic research workbench. It does not claim a licensed live feed, wagering service, real-money settlement, legal approval, independent adoption or validated forecasting performance.

## First principles: absence is not completeness

Suppose a rule asks whether at least five corners occurred in a period. Four recorded corners do not establish an under result if the feed is incomplete. The programme needs an explicit closure declaration whose count agrees with the active observations, and the relevant records must meet the required configured state.

This is the first principle: a negative conclusion requires a justified account of coverage. The second is temporal integrity: reconstructing an earlier operator decision requires the history available at that decision. The pure evaluator instead filters the supplied history by declared receipt time; a cutoff alone does not establish the recorder's earlier knowledge. The third is corrigibility with retained lineage. A correction should identify what it supersedes and preserve the earlier observation and decision.

Authority is another separate dimension. A registry can designate a source as official, but the designation is supplied configuration. A recorder's signature authenticates its representation under a pinned key. Neither alone proves a sporting fact, source independence, trusted time or a legal right to use the data.

## Fundamental logic of the reference

The implemented language counts supported occurrences in a defined event and period against an integer threshold. Facts have observation identities and explicit revisions. The ledger rejects invalid lineage, conflicting retries and unsupported changes to identity or correction deadlines. Pending and void are meaningful outcomes, not errors to coerce into a binary result.

The fictional replay demonstrates six authoritative observations and a matching closure, followed by corrections. With a withdrawal but an unchanged closure count, the result becomes pending. Updating the closure restores a determinate result. A later correction can change the outcome while leaving previous receipts available for inspection.

At the source revision inspected on 15 November 2026, main already checks both declared receipt time and append-order acknowledgement of value-changing revisions. The earlier description of that rule as branch-only is therefore superseded. The RFC and review packet still describe an unapproved semantic proposal: implementation presence does not establish independent acceptance of its meaning. Reconcile those historical status records before a reference freeze, particularly for delayed imports and post-closure initial observations.

## Definitions and correction counterexample

An **observation** has a stable identity; a **revision** is a particular recorded statement about it. A **closure** declares a total for a period and metric. **Received time** is supplied data; **append order** is position in the recorder's history. An **as-of result** selects observation revisions whose declared `received_at` is no later than the cutoff, scanning the full history supplied to `evaluate`. That is not automatically the history known to the recorder at an earlier checkpoint. None of these terms authenticates external chronology by itself.

Consider two initial occurrence values, A = 1 and B = 0, with a closure total of one. Two corrections exchange the values: A becomes 0 and B becomes 1. Their net effect on the total is zero. For illustration use a threshold of one, and assume all other required state, deadline and admission checks pass.

| Local sequence | Aggregate | Closure acknowledgement | Result under the current rule |
| --- | --- | --- | --- |
| A = 1, B = 0, then closure = 1 | 1 | Follows initial observations | `settled`, `over` |
| Same closure, then both value corrections | 1 | Predates corrections | `pending`, `stale_closure` |
| Then append a new closure revision = 1 with receipt time no earlier than both corrections | 1 | Both ordering conditions satisfied | `settled`, `over` |

Equal receipt timestamps do not repair the second row: the earlier local declaration cannot acknowledge later appended corrections under this rule. Conversely, a closure appended later but declaring an earlier receipt time also fails. The table is a hand-worked explanation of `_closure_covers_value_changes` in [src/tallystick/settlement.py](https://github.com/Albertito-AI/tallystick/blob/80c6da4af1e95108b80905fb33e8a30f57f741f5/src/tallystick/settlement.py), not a new execution result.

This rule is conservative and contestable. A delayed import can append an authentic upstream closure before importing the observations it covered. Requiring local append order may then retain `pending` even when the upstream account was adequate. Initial zero-valued observations and new observations arriving after closure also require explicit domain interpretation; a correction rule alone does not define their meaning. The [docs/rfc-0001-independent-review-packet.md](https://github.com/Albertito-AI/tallystick/blob/80c6da4af1e95108b80905fb33e8a30f57f741f5/docs/rfc-0001-independent-review-packet.md) retains these open semantic questions.

There is also a temporal-replay counterexample. Supply only a closure declaring zero: under the fixture's positive threshold, the expected result is `settled/under`. Then supply a longer history adding a first-version positive occurrence with an older or equal `received_at`. At the same cutoff, that record now participates and the expected result becomes `pending/closure_count_mismatch`. A new zero-valued occurrence can leave `under` unchanged while changing `fact_ids`. These are static consequences of `active_snapshot` and the review packet's 11 November analysis, not new execution results. Reconstructing an earlier operator decision therefore needs its retained signed-log prefix/checkpoint and rule version; a declared receipt-time cutoff over later supplied evidence answers a different question.

## Reproduction and claim-evidence map

Select source revision `80c6da4af1e95108b80905fb33e8a30f57f741f5` in a separate checkout. Use Python 3.11 or later, install the project's declared dependencies in an isolated environment, and use Node.js 22 or later for the second evaluator. From the repository root, following [README.md](https://github.com/Albertito-AI/tallystick/blob/80c6da4af1e95108b80905fb33e8a30f57f741f5/README.md):

```sh
python -m pip install -e .
python -m tallystick demo --output run/paper-review
python -m tallystick verify run/paper-review/dispute.json --public-key-file run/paper-review/public-key.txt
python -m unittest discover -s tests -v
```

Choose a new directory. In the fictional demo, the stages are pending, pending, over at six, pending after a withdrawal, over at five and under at four. The generated public key establishes only continuity within that run. For external authentication the reviewer needs a separately trusted key. Record commit, Python, Node and dependency versions, commands, exit status and discrepancies; do not reuse a historical test count as the current result.

| Claim | Pinned evidence | Boundary |
| --- | --- | --- |
| Missing closure and inconsistent counts remain pending | [src/tallystick/settlement.py](https://github.com/Albertito-AI/tallystick/blob/80c6da4af1e95108b80905fb33e8a30f57f741f5/src/tallystick/settlement.py); [tests/test_settlement.py](https://github.com/Albertito-AI/tallystick/blob/80c6da4af1e95108b80905fb33e8a30f57f741f5/tests/test_settlement.py) | An agreed count can still be factually false |
| Value changes need both receipt-time and local-order acknowledgement | `_closure_covers_value_changes`; tied-time regression in [tests/test_settlement.py](https://github.com/Albertito-AI/tallystick/blob/80c6da4af1e95108b80905fb33e8a30f57f741f5/tests/test_settlement.py) | Local order is not source causal order |
| A second implementation can reproduce selected outcomes | [conformance/reference.mjs](https://github.com/Albertito-AI/tallystick/blob/80c6da4af1e95108b80905fb33e8a30f57f741f5/conformance/reference.mjs); [tests/test_conformance.py](https://github.com/Albertito-AI/tallystick/blob/80c6da4af1e95108b80905fb33e8a30f57f741f5/tests/test_conformance.py) | Agreement can preserve a shared specification error |
| Earlier decisions can be reconstructed from a signed synthetic history | [docs/demo/README.md](https://github.com/Albertito-AI/tallystick/blob/80c6da4af1e95108b80905fb33e8a30f57f741f5/docs/demo/README.md); [docs/validation.md](https://github.com/Albertito-AI/tallystick/blob/80c6da4af1e95108b80905fb33e8a30f57f741f5/docs/validation.md) | Historical execution, not fresh performance or independent adoption |

The source includes richer formal and pricing work, but this reproduction does not by itself execute every optional solver or bounded model. Follow their separately pinned instructions and retain the actual result if making those narrower claims.

## Related work and limits of analogy

[Leslie Lamport, “Time, Clocks, and the Ordering of Events in a Distributed System”, Communications of the ACM 21(7), 558–565 (1978)](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/12/Time-Clocks-and-the-Ordering-of-Events-in-a-Distributed-System.pdf), pages 558–559, distinguishes causal partial order from a chosen total order. This motivates care about receipt time and recorder sequence. Tallystick does not implement Lamport's distributed clock algorithm or acquire external causal knowledge merely by citing it.

[Laurie, Langley and Kasper, RFC 6962 (June 2013)](https://www.rfc-editor.org/rfc/rfc6962), sections 2.1–2.1.2, distinguishes Merkle inclusion from consistency across tree versions and defines separate leaf/node prefixes. The repository uses that tree construction. RFC 6962 is experimental and has been superseded by RFC 9162; the reference is to the specific construction used, not a claim of current Certificate Transparency protocol conformance. A local signed inclusion proof does not show that a recorder disclosed the same history to everyone. Independent checkpoint distribution and verification remain separate design work.

## Why independent replay matters

Tallystick includes a Python implementation and an independent JavaScript evaluator for supported semantics. Agreement across implementations can expose particular bugs and ambiguities. It does not prove that both implementations captured the right institutional rule, especially if both inherited the same mistaken specification.

Signed records, Merkle proofs and complete-log verification make tampering and internal inconsistency more inspectable. A verifier must obtain the recorder key independently; accepting a key included in an untrusted bundle merely establishes self-consistency. External witnessing, key custody and protection against competing histories remain separate production concerns.

Permissions and rule-pack validity are checked for the declared use and relevant time. The supplied jurisdiction is fictional TEST. A past certificate cannot extend an expired permission. These controls model a disciplined boundary; they are not authenticated supplier licences or approval to operate in a real jurisdiction.

## Public-interest purpose and risks

The immediate aim is reproducible settlement review and a useful way to investigate corrections. The broader hope is accountable data infrastructure: people affected by automated decisions should be able to inspect the source lineage, rule version and correction path rather than trust a black box.

Within sports-related systems, the ethical test cannot be transaction volume. Better data infrastructure could also facilitate harmful or exploitative activity if deployed carelessly. The project should retain explicit operating constraints, reject unsupported live uses and assess consumer and integrity consequences independently from mathematical correctness.

The underlying ideas may eventually inform other domains where decisions depend on corrected observations, but transfer is a research proposal. A medical, civic or financial application would need its own data semantics, authority and safeguards. A count-settlement engine is not a universal fact oracle.

## Ideal progression

| Stage | Intended capability | Required evidence |
| --- | --- | --- |
| Stable reference semantics | A precisely understood correction and completeness contract | Independent domain review, adversarial vectors and reconciled specification |
| Independent reproduction | Another person recreates the stated synthetic result | Exact revision, environment, assistance and observed differences |
| Authorised shadow replay | Compare against permitted historical data without affecting live decisions | Source-use rights, scope, accountable reviewers and discrepancy register |
| Operational readiness | Reliable service around the accepted semantics | Key rotation, recovery, load limits, monitoring and incident exercises |
| Scoped real service | One justified use in one actual jurisdiction | Current qualified review, supplier permissions, agreements and acceptance |

The wishlist includes clearer correction acknowledgements, selective evidence exports, independent checkpoints, upstream signature validation, accessibility and stable SDKs. Additional sports or rule types should arrive with independently generated examples, not only extensions of the same favourable fixture. The initial read-only MCP interface needs actual host interoperability evidence before broader protocol claims.

Pricing and batch-simulation research should remain distinct from settlement correctness. Numerical coherence under assumed distributions is not a calibrated prediction. Optional solver unavailability or an unasserted exhaustive outcome space should remain `UNKNOWN`, not become an unwarranted global guarantee.

## Evaluation and reasons to stop

Synthetic tests should report scenario coverage, seeded errors, determinism and failures. A permitted pilot should measure unexplained differences, missing records, correction latency, reviewer effort and the cost of reproducing a decision. Domain reviewers should examine delayed imports, offsetting corrections, zero-value observations and the difference between declared receipt time and append order.

If source rights cannot be established, do not build an adapter that assumes them. If completeness declarations cannot support the intended decision, narrow the rule. If operators cannot explain discrepancies, additional throughput is not progress. If the service increases harm or makes challenge impractical, its operating model needs revision even when replay is technically correct.

The best case is a dependable record of how a result became justified, including the moments when it was not yet justified. That modest discipline could make consequential automation more answerable to the people who rely on it.

## Review method and teaching questions

An independent reviewer should decide expected outcomes before reading evaluator outputs. Include delayed imports, equal timestamps, offsetting changes, state-only promotions, zero initial observations, expired rights and authoritative abandonment. Record both the expected status and the source-specific reason. Comparing implementations is an implementation check; deciding which source convention ought to govern is a semantic judgement. Neither substitutes for the other.

For teaching, ask why four observations without closure cannot justify `under`; why two corrections with no net count change can reopen a result; and what a signed checkpoint proves if its key arrives in the same untrusted bundle. An advanced exercise compares aggregate-only and revision-aware closure policies on a delayed import. The goal is to state the chosen semantics and counterexample it rejects, while admitting the cases it leaves unresolved.

## Inspected foundation

Current implementation assessment: [`80c6da4af1e95108b80905fb33e8a30f57f741f5`](https://github.com/Albertito-AI/tallystick/tree/80c6da4af1e95108b80905fb33e8a30f57f741f5), inspected 15 November 2026. The original foundation baseline below is retained as a historical record. Links in the added claim-evidence map identify the current assessed source. This documentation revision changes no implementation, licence, operating permission or release gate.

Baseline: [`5fd89b45334169f50e03e17a463a54eb2699f0be`](https://github.com/Albertito-AI/tallystick/tree/5fd89b45334169f50e03e17a463a54eb2699f0be). See [README](https://github.com/Albertito-AI/tallystick/blob/5fd89b45334169f50e03e17a463a54eb2699f0be/README.md), [settlement semantics](https://github.com/Albertito-AI/tallystick/blob/5fd89b45334169f50e03e17a463a54eb2699f0be/docs/settlement-semantics.md) and [roadmap](https://github.com/Albertito-AI/tallystick/blob/5fd89b45334169f50e03e17a463a54eb2699f0be/docs/roadmap.md). Code/documentation retain Apache-2.0 and the original schema layer retains CC BY 4.0. These grants do not confer sports-feed rights or rights to the separately supplied foundation document.
