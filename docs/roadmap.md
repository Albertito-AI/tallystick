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

## Next evidence gates (reviewed 2 November 2026)

The v0.1 synthetic reference exists and the experimental repository is public
(L0). The later validated versioned release (L1) is **not complete**.

1. **D1, v0.2 reference freeze:** settle the documented semantics, schema and
   reproducibility contract. [Draft PR #1](https://github.com/Albertito-AI/tallystick/pull/1)
   proposes RFC 0001's two-axis correction acknowledgement. Its first-party
   tests and passing commit-specific CI do **not** constitute independent
   semantic approval. Obtain an independent domain review of the
   [R01-R12 packet](rfc-0001-independent-review-packet.md), especially delayed
   historical imports, late initial observations, zero-value records, declared
   receipt time versus recorder append order, and upstream source authority.
   Resolve findings in the existing PR, safely integrate the current main tree,
   then validate the **exact combined candidate** before deciding whether to
   merge and freeze. No date or green status substitutes for those steps.
2. **D2, independent reproduction:** obtain two genuine non-implementer
   reproductions of a specified public commit and synthetic workflow. Keep
   the tested SHA, environment, commands, inputs, observed outcomes, failures,
   material assistance and reviewer consent in private review receipts.
   Internal Python/JavaScript agreement, hosted CI and AI-prepared commentary
   do not count as independent users. Cite external findings publicly only
   with permission.
3. **C1/C2, one customer problem and permitted data path:** qualify a specific
   settlement or source-correction review task, the responsible buyer, a usable
   historical dataset and rights for acquisition, analysis, retention and
   export. A provider-specific adapter remains blocked until that evidence
   exists. A later bounded pilot also needs agreed scope, acceptance, funding
   and lawful operational controls.

The canonical private milestone tracker is the operational status record,
not a public customer ledger.
Release decisions, sponsorship readiness and actual available collections
must remain distinct. No licensed feed, customer adoption, independent review,
production deployment or funding is implied by publishing the reference.

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
