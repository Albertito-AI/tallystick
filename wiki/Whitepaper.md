<!-- atlas-whitepaper:managed:v1 -->

# Tallystick: the difference between an observed event and a settled fact

## Thesis

A result derived from a stream of observations is only as dependable as its rules for completeness, correction and authority. Tallystick makes those rules explicit. Its reference workbench records sports observations, checks declared permissions, evaluates a bounded market rule and preserves enough history for another implementation to reproduce the decision.

The larger idea is that consequential systems should be able to explain what was known at the time, what later changed and why the result changed with it. A plausible final number is insufficient when people need to challenge an earlier decision.

Prepared for Albert Tan Sin Hon with AI assistance, 2 November 2026. This design paper concerns the inspected synthetic research workbench. It does not claim a licensed live feed, wagering service, real-money settlement, legal approval, independent adoption or validated forecasting performance.

## First principles: absence is not completeness

Suppose a rule asks whether at least five corners occurred in a period. Four recorded corners do not establish an under result if the feed is incomplete. The programme needs an explicit closure declaration whose count agrees with the active observations, and the relevant records must meet the required configured state.

This is the first principle: a negative conclusion requires a justified account of coverage. The second is temporal integrity. A decision at time t must use the history available at t, not later corrections disguised as prior knowledge. The third is corrigibility with retained lineage. A correction should identify what it supersedes and preserve the earlier observation and decision.

Authority is another separate dimension. A registry can designate a source as official, but the designation is supplied configuration. A recorder's signature authenticates its representation under a pinned key. Neither alone proves a sporting fact, source independence, trusted time or a legal right to use the data.

## Fundamental logic of the reference

The implemented language counts supported occurrences in a defined event and period against an integer threshold. Facts have observation identities and explicit revisions. The ledger rejects invalid lineage, conflicting retries and unsupported changes to identity or correction deadlines. Pending and void are meaningful outcomes, not errors to coerce into a binary result.

The fictional replay demonstrates six authoritative observations and a matching closure, followed by corrections. With a withdrawal but an unchanged closure count, the result becomes pending. Updating the closure restores a determinate result. A later correction can change the outcome while leaving previous receipts available for inspection.

The main-branch semantics also inspect whether a closure acknowledges value-changing revisions. A separate draft proposes a richer two-axis correction treatment. That proposal still requires independent semantic review and must not be described as the accepted reference merely because its tests pass. This is a useful example of the project's own principle: recorded implementation and accepted meaning are distinct.

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

## Inspected foundation

Baseline: [`5fd89b45334169f50e03e17a463a54eb2699f0be`](https://github.com/Albertito-AI/tallystick/tree/5fd89b45334169f50e03e17a463a54eb2699f0be). See [README](https://github.com/Albertito-AI/tallystick/blob/5fd89b45334169f50e03e17a463a54eb2699f0be/README.md), [settlement semantics](https://github.com/Albertito-AI/tallystick/blob/5fd89b45334169f50e03e17a463a54eb2699f0be/docs/settlement-semantics.md) and [roadmap](https://github.com/Albertito-AI/tallystick/blob/5fd89b45334169f50e03e17a463a54eb2699f0be/docs/roadmap.md). Code/documentation retain Apache-2.0 and the original schema layer retains CC BY 4.0. These grants do not confer sports-feed rights or rights to the separately supplied foundation document.
