# Development roadmap

The first useful result is a reproducible synthetic workflow from fact ingestion
to a reviewable settlement record. Later stages depend on evidence and named
prerequisites. The report's indicative month ranges are planning hypotheses; they
are not delivery commitments.

| Stage | Work | Exit evidence |
| --- | --- | --- |
| Reference contract | Typed facts, explicit revisions, declared source registry, permissions and TEST policy; deterministic count settlement | Both evaluators agree across the documented synthetic season and edge cases; invalid inputs fail with explicit reasons |
| Record verification | Signed append-only local history, proof export and independent verification against a pinned key/checkpoint | Tampering, wrong keys, incorrect proof paths and inconsistent checkpoints fail the tests |
| Synthetic operating tests | Corrections, abandonment, incomplete feeds, retries, batch watermarks, bounded mandates and expiry | Published reproducible test receipt, including failure cases and assumptions |
| Authorised shadow pilot | One permitted data source, a consenting operator, agreed scope and source-use rights; compare results without affecting live settlement | A dated difference register whose discrepancies have explanations and responsible reviewers |
| Domain expansion | Additional sports and market contracts, specified completeness evidence and exceptional correction paths | New independently generated vectors and review by people competent in the domain |
| Deployment preparation | Threat model, authentication, key custody and rotation, backups, operational monitoring, load tests and incident procedures | A deployment review tied to the actual environment and measured service limits |
| Jurisdiction-specific service | Current legal analysis, actual operating/supplier permissions where required, reviewed policy packs and contracting arrangements | Evidence-backed approval of one concrete service in one concrete jurisdiction |
| Commercial integration | Licensed adapters and a funded customer problem; bounded support and acceptance requirements | Paid engagement completed and accepted; measured customer benefit and actual delivery cost |
| Wider interfaces and governance | Stable SDKs, host testing of the initial MCP interface, outside implementations and a governance proposal | Interoperability results and external implementer participation; funding and maintenance ownership established |

## The next three milestones

1. Freeze the v0.1 reference semantics after reviewing disagreements and known
   limits. Publish the exact test commands and generated synthetic evidence.
2. Select one prospective shadow-settlement use case. Confirm the actual data
   rights, settlement rules, comparison method and expected benefit before
   writing a provider-specific adapter.
3. Run the bounded pilot only after the required commercial and operational
   conditions are satisfied. Record every disagreement and the cost of resolving
   it before deciding on a larger service.

## Measurements

During synthetic tests, report scenario coverage, detected seeded errors,
determinism, replay throughput in the measured environment and actual test
failures. Synthetic agreement does not supply an estimate of real settlement
accuracy, fraud-detection precision or customer benefit.

During an authorised pilot, measure unexplained differences, correction latency,
missing or ambiguous source records, reviewer time and the cost of reproducing a
decision. Pricing evaluation should separately report numerical error, model
calibration and the assumptions connecting the simulated distribution to real
outcomes.

Live integrity precision, customer-harm outcomes, availability objectives and
cross-operator exposure coverage require actual operational data and suitable
evaluation methods. They remain unmeasured until that evidence exists.

## Scope held for later work

This initial repository establishes no live bookmaker or exchange, no money
movement, no autonomous consumer betting, no licensed live feed, no approved
real-jurisdiction rule pack, and no third-party certification. It does not
establish a customer, partnership or revenue stream. Those outcomes require
separate work and verifiable receipts.

Tallystick remains a working name. Resolve naming and branding questions before
a public product launch. The experimental repository became public on 26 October
2026 under the owner's instruction to refine it openly and welcome co-creators.
Public visibility is complete; independent external reproduction, a validated
versioned release and a funded pilot retain their own evidence requirements.
