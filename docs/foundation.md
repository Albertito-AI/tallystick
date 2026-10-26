# Foundational document and implementation decisions

The source is *The price of a settled fact*, dated 26 October 2026, supplied by
the project owner as `Tallystick_Agent_Sports_Data_Report.docx`.

- Source size: 57,953 bytes.
- SHA-256: `0d39a2fbc447e3f7774d9fada9d1b9a0a02fb787b1df74d1c65015c358aa29cd`.
- Scope used: architecture, state transitions, rights checks, settlement,
  numerical examples, replay, testing and staged implementation.
- The uploaded original is unchanged and retained separately.

## Traceability

| Whitepaper section | Initial implementation |
| --- | --- |
| 5.1–5.7 mathematics | `pricing.py`, documented assumptions and numerical tests |
| 6.1 typed agent interactions | Bounded JSON, idempotency, read-only MCP tools |
| 6.3 fact states and log | `ledger.py`, `crypto.py`, signed checkpoints and corrections |
| 6.4 market definition | A deliberately restricted count-market JSON compiler |
| 6.6 replay | Synthetic match replay and independent synthetic-season conformance |
| 7.2 shadow migration | Roadmap for permitted external comparison; no supplier adapter claimed |
| 8.5 jurisdiction gate | TEST-only dated rule-pack mechanism; no real legal clearance |
| 9 integrity and mandates | Conservative compiler rules and an in-memory batch simulator |
| 10.2 code and schema licensing | Apache-2.0 code, CC BY 4.0 original schema definitions |
| 11 testing | Unit/integration tests, independent JavaScript evaluator, bounded TLA+ models and CI |
| Appendix A | Replayed six-to-five-to-four correction scenario and reproducible evidence export |

## Changes made to make the proposal testable

The build requires an authoritative closure count matching the active observations
before it infers either outcome. It preserves a pending state during incomplete
corrections. It distinguishes recorder authenticity from external fact truth and
trusted time. The batch simulator waits for declared source watermarks and halts
on late-event incidents; it makes no claim to eliminate latency advantages.

The compiler does not infer low manipulation risk solely from aggregation. It
records contextual review as outstanding. A market certificate states that its
scope is synthetic replay and that pricing coherence is not assessed there.

The paper's revenue figures, assertions of market novelty, legal developments,
regulatory classifications and forecasts have not been re-audited for this code
delivery. They are not copied into operative legal rules or commercial promises.
See the separate foundation review for additional limitations.

## Working name

A bounded public check on 26 October 2026 found existing products using the name,
including [Tallystick invoice tools](https://tally-stick.com/api) and
[ShadowForge's Tallystick scorepad](https://shadowforge.dev/tallystick/).
This is evidence of prior use, not a trade mark search or legal conclusion. The
development repository remains private while the working name is reviewed.
