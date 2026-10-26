# Foundation review and implementation decisions

Tallystick begins as a research implementation of the supplied report, *The price
of a settled fact*, dated 26 October 2026. The report identifies a useful systems
problem: preserve the provenance, declared permissions and changing status of
the evidence used to decide a sporting market. The first build implements a
bounded synthetic workflow so those claims can be examined through reproducible
outputs.

The report's market statistics, recent court decisions, regulatory developments,
competitive-novelty claims and potential customer demand have **not** been
re-audited for this software build. They are research leads, rather than factual
assumptions embedded in the executable policy. No real jurisdiction is enabled
by an example rule pack, and a successful test creates no supplier licence or
professional certification.

## Decisions that strengthen the proposed design

| Report proposition | Implementation decision | Remaining question |
| --- | --- | --- |
| A logged, signed fact supplies settlement-grade truth | Sign the recorder's exact representation; verify it against a separately trusted key and checkpoint | Whether the source is authentic, complete and correct remains an external question |
| A Merkle proof establishes when a fact was recorded and that nothing was removed | Use domain-separated leaf/node hashes, inclusion proofs and a signed checkpoint; retain the checkpoint outside the mutable working database | A local timestamp is an assertion. Equivocating logs require independent witnesses or other comparison mechanisms |
| Agreement between two feeds corroborates a fact | Count independently configured source groups rather than two source identifiers | A registry can describe independence; it cannot establish actual upstream independence by itself |
| The absence of enough event facts supports the lower outcome | Require an authoritative closure declaration whose total matches the active event records | A false or incomplete closure declaration can still be internally consistent |
| A correction replaces an earlier fact | Append a revision with a reason and a link to the current head; preserve the earlier version | Later real-world disputes require a governed process outside the initial correction window |
| A corrected fact can immediately recompute the result | Require a consistent closure received at or after the latest selected value-changing revision, including offsetting corrections | Partial arrival of correction messages must produce a pending result |
| Every aggregate market has low controllability | Treat any integrity classification as a declared, reviewable policy input | Aggregation does not establish resistance to manipulation |
| Pairwise correlation checks make combinations coherent | Distinguish two-event bounds from feasibility over an explicitly represented joint outcome space | Sampled support can omit feasible outcomes; model error remains separate from numerical error |
| A batch removes the advantage from seeing an event early | Require the declared event watermark to reach the batch boundary and record the applied snapshot and quote | Late events, incorrect event times, cancellation rights and future batches can still create informational advantages |
| A machine-readable rule pack proves lawful operation | Bind decisions to the pack's exact version, declared reviewer and validity period; default to refusal outside the synthetic TEST scope | Real law, licences, customer eligibility and review authority require independent evidence |
| A display-text check defeats injected instructions | Keep operative conditions in a narrow typed schema and never execute display text | A string filter is incomplete; downstream models must continue treating returned content as data |

## Settlement scope

The reference contract counts active `corner.awarded` or `goal.scored` records in
one period of one fictional event. Each occurrence has a stable observation identity and each
revision has its own fact identity. A `period.closed` record declares the complete
count for that metric and period. An unresolved closure, a count mismatch or an
insufficient evidence state produces `pending`. An authoritative abandonment
produces `void`. A complete result produces `over` or `under` against the specified
integer threshold.

This deliberately small language makes an independent evaluator possible. It
does not establish the settlement rules for every sport, dead heats, deductions,
abandoned-event exceptions, exchange clearing or customer payouts. Each extension
needs explicit semantics and new disagreement tests.

## Corrections and finality

The initial contract rejects a value-changing revision received at or after its
declared correction deadline, and rejects any revision of a final observation.
State promotion to final can occur only after that deadline. These are research
semantics chosen for deterministic comparison. They are not a statement that a
late official correction can never have contractual or legal effect. Any future
exceptional adjudication route must preserve the original decision, state its
authority and issue a separate decision instead of rewriting history.

## Evidence and verification boundaries

An inclusion proof answers whether an entry belongs to a particular tree root.
A signature answers whether a holder of the corresponding private key signed
the represented message. Neither establishes the sporting fact or the legal
effect of a licence. A trusted checkpoint is an input to verification; taking a
public key or a replacement checkpoint solely from the same untrusted export
would remove that independent reference.

RFC 9162 supersedes the report's RFC 6962 reference. Its section 2.1 describes the
Merkle tree construction; sections 1 and 11.3 explain the problem of inconsistent
log views. Tallystick uses the construction without implementing the Certificate
Transparency network protocol or claiming CT conformance.

## Initial implementation choice

The first implementation uses Python for the executable workflow and a separate
JavaScript evaluator for semantic comparison. This permits immediate execution
with the available runtime and independent agreement tests. Rust services,
TypeScript SDKs, persistent streams and other parts of the proposed production
architecture remain later work. A separate bounded TLA+ model examines selected
state-machine properties; agreement of that model with the implementation is
not proved by running either test suite.

## Primary implementation references

- [RFC 9162, sections 1, 2.1 and 11.3](https://www.rfc-editor.org/rfc/rfc9162.html).
  Opened 26 October 2026. Describes Merkle constructions and log trust limits.
- [Cryptography Ed25519 documentation](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/).
  Opened for this build. Defines signing and verification APIs; provider identity
  and key distribution are separate design tasks.
- [TLA+ tools release 1.7.4](https://github.com/tlaplus/tlaplus/releases/tag/v1.7.4).
  Official tool source for the bounded model checks. See `tla/README.md` for the
  exact execution record and limits.

The complete uploaded report remains the owner's foundational source. The
repository's tests and documentation describe the implemented contract rather
than republishing its unverified claims as product guarantees.
