# Settlement semantics

Version 0.1 implements one deliberately bounded market language: count recognised
occurrences of a named metric in one period of one fictional or authorised event,
then compare the count with an integer threshold. The two outcomes are `over` and
`under`. `corner.awarded` and `goal.scored` are the supported count metrics. A
declared authoritative abandonment produces `void`.

## Facts and observation identity

Each fact is a versioned record of an observation. `observation_id` identifies one
occurrence or one completeness declaration; `fact_id` identifies a particular
revision. A new revision explicitly names the current head in `supersedes`.
The ledger rejects a missing predecessor, a branch from an older head, duplicate
fact identifiers, and changes to observation identity, event, period, kind,
subject, original occurrence time, metric, licence identifier or correction
deadline. This prevents a revision from extending its own correction window or
silently replacing the recorded licence.

The state vocabulary is:

| State | Admission requirement |
| --- | --- |
| `provisional` | At least one source in the configured source registry |
| `corroborated` | At least two sources with different configured independence groups |
| `official` | At least one source designated in the registry as official for this fact kind |
| `final` | Official-source requirement and receipt at or after the correction deadline |

These checks verify a supplied record against operator configuration. They do not
prove the external source's identity, independence, receipt of a message, sporting
truth or legal status. This first implementation signs the local recorder's
representation; it does not verify upstream supplier signatures.

A first authoritative record may enter as `official`. The recorder does not invent
an earlier provisional observation. For an unchanged value, a revision may retain
or increase the state. A changed value must carry a nonempty correction reason,
arrive before the immutable deadline, and be recorded before that deadline. It
may return to a lower state while the correction is investigated. A final fact
cannot be revised. Exceptional disputes after finality therefore require a
separately designed adjudication process; this implementation does not silently
reopen them.

Occurrence records have value `1`, or `0` when a correction withdraws an occurrence.
The event kind stays unchanged; the reason records the reclassification. This
choice preserves lineage without making a withdrawn corner into an unrelated
goal event. A genuine different event requires its own observation.

All timestamps use UTC `YYYY-MM-DDTHH:MM:SS[.fraction]Z`, with up to six fractional
digits. Occurrence must precede or equal receipt, receipt must precede or equal
recorder time, and recorder timestamps cannot move backwards. Replay calls may
explicitly provide their historical recorder timestamp. These are declared
timestamps, not a trusted timestamping service.

## Completeness before settlement

Absence of an occurrence is insufficient evidence of a losing outcome. Settlement
requires exactly one active `period.closed` fact for the selected period and metric.
Its value declares the authoritative aggregate count for that metric. The engine
checks that this total equals the sum of active recorded occurrence values.

A closure with value zero can therefore settle a zero-count period. A missing
closure, conflicting closures or a count mismatch produces `pending`. Every
selected occurrence and the closure must have reached the market's required state,
which is either `official` or `final`. The relevant facts must use the market's
same correction deadline.

A closure is an operator-supplied completeness declaration attributed to a
configured source. Matching totals are a consistency check. They cannot prove
that all real-world events have been observed or that the source's total is true.

When an occurrence's value changes, its closure must have a receipt timestamp at
or after every value-changing revision in the selected active occurrences'
history. Equal timestamps are allowed. A count mismatch produces
`closure_count_mismatch`; matching totals with an older closure produce
`stale_closure`. This second check covers offsetting corrections whose net count
stays unchanged. A closure can acknowledge those corrections through a new
revision carrying the same total. State promotions without a value change do not
require a later closure. Future revisions beyond the evaluation time and changes
to unrelated events, metrics or periods are excluded. Both the original and
corrected records remain in the log.

## Deterministic evaluation

`evaluate(market, facts, as_of=...)` consumes the full validated append-order fact
history. It resolves the latest revision of each observation received by `as_of`,
selects the event and count rule, and returns:

```json
{
  "market_id": "fictional-corners-over-4.5",
  "status": "settled",
  "outcome": "over",
  "count": 6,
  "reasons": [],
  "fact_ids": ["example-fact-id", "example-closure-id"]
}
```

The illustrative IDs above are placeholders, not an actual receipt. `fact_ids`
are sorted to make independent comparison deterministic. Pending and void results
have null outcome/count, except that a settled result contains `over` or `under`.
All malformed histories and unsupported rules raise `ValueError`; a caller must
not convert an exception into a successful settlement.

Evaluation checks the following conditions in order:

| Condition | Result or reason code |
| --- | --- |
| No active facts for the event | `pending`, `no_event_facts` |
| Relevant deadline differs from the market | `pending`, `correction_deadline_mismatch` |
| Active authoritative abandonment with value one | `void`, `event_abandoned` |
| Active unconfirmed abandonment with value one | `pending`, `unconfirmed_abandonment` |
| No matching closure | `pending`, `missing_closure` |
| More than one matching closure | `pending`, `ambiguous_closure` |
| Closure state below the required state | `pending`, `insufficient_closure_state` |
| Any selected occurrence below the required state | `pending`, `insufficient_fact_state` |
| Aggregate closure differs from recorded count | `pending`, `closure_count_mismatch` |
| Matching aggregate closure predates a selected value-changing revision | `pending`, `stale_closure` |
| Every check passes | `settled`, `over` when count meets threshold, otherwise `under` |

Authoritative abandonment means `official` or `final`, even if the market otherwise
requires final count facts. In this reference contract, it is a void condition,
not a win/loss determination. It applies across event periods. A revised abandonment
with value zero removes that condition only while its correction window remains
open; settlement then evaluates the remaining requirements.

Rights checks, rule-pack validity and source-registry authority belong to the
admission/compiler layer. Direct calls to the pure evaluator assume those checks
have already been completed. The function itself creates no customer payment,
bet, order or legal authorisation.

The application compiler requires declared settlement permissions and designated
official sources for the selected count metric, `period.closed` and
`event.abandoned`. Its signed certificate records the count permission and both
supporting permission checks. At each replay decision, the workbench rechecks the
market licence, the relevant active facts' licences and the rule pack at the
decision's actual evaluation time. Expired permissions or policy produce
`pending`, including `LICENCE_NOT_CURRENT` and `RULEPACK_NOT_CURRENT`; an earlier
certificate does not extend their validity.

## The local log and proofs

The SQLite log uses a transaction for the entry, idempotency receipt and derived
observation head. A retry with identical kind and payload returns its original
entry without adding a record. Reuse of the same key for different content raises
`IDEMPOTENCY_CONFLICT`. Record timestamps are excluded from the request fingerprint
so a transport retry does not become a new logical request.

Every entry contains the sequence, previous entry hash, source-registry digest,
declared recorder time and payload. The local Ed25519 key signs that envelope.
The Merkle log uses SHA-256 with the RFC 6962 leaf prefix `0x00` and node prefix
`0x01`, splitting at the largest power of two below the current tree size.
An inclusion bundle contains the entry, its audit path and a signed checkpoint.
`verify_bundle` requires an independently obtained recorder public key; trusting a
key embedded in the same untrusted bundle would establish no useful identity.

The complete dispute verifier also matches the logged certificate to the supplied
certificate, reproduces its assertions from the bundled configuration, and
recomputes every recorded decision from the fact history preceding that decision.
It verifies global timestamp order, unique idempotency keys, and equality of the
final decision, summary and checkpoint timestamps. These checks detect internal
contradictions even in a bundle signed by the recognised recorder. They do not
independently certify the recorder's timestamps or configuration.

Reference sources:

- [RFC 6962 section 2.1](https://www.rfc-editor.org/rfc/rfc6962#section-2.1)
- [Cryptography Ed25519 API](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/)

The JSON encoding is a documented local representation using sorted keys, compact
separators and UTF-8. It is not claimed to implement RFC 8785. Integer facts remain
within the exact interoperable JSON integer range. Nonfinite numbers and excessive
nesting are rejected.

An inclusion proof establishes that an entry belongs to the checkpoint's tree.
A signed checkpoint authenticates a representation under a pinned local key.
Neither supplies independent time, external witnessing, source truth, prevention
of equivocation, or proof that an operator has disclosed every competing history.
SQLite triggers block accidental entry changes. An administrator who controls
the database and signing key can replace both. Production transparency requires
key management, independent checkpoint distribution/witnessing and consistency
proofs or an equivalent mechanism; those capabilities are outside version 0.1.

## Correction demonstration

The replay first demonstrates provisional and corroborated evidence. It then
records six authoritative corners and a closure count of six, so the
over-four-and-a-half market settles `over`. A correction withdraws one corner.
Until the authoritative closure is also revised, evaluation is pending with
`closure_count_mismatch`. A revised closure of five restores `over`. A second
withdrawal and a revised closure of four change the outcome to `under`, with the
new fact identifiers. Earlier proof bundles remain verifiable against their
earlier checkpoints. The application records new settlement receipts rather than
rewriting the old decision.

This is a synthetic conformance exercise. It is not evidence of live supplier
integration, a licensed betting operation, a completed customer pilot or a
guaranteed settlement of a real sporting event.
