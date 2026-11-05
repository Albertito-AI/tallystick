# RFC 0001: Closure acknowledgement must follow covered corrections

Status: proposed v0.2 contract tightening; implementation in a review branch.
Date: 27 October 2026. This document is AI-assisted and has no independent reviewer sign-off.

## Problem and precise reproduction

The v0.1 evaluator requires a closure with a matching aggregate count and a
receipt timestamp no earlier than value-changing revisions. It does not require
that the closure be recorded *after* those revisions in append order.
An official closure can therefore precede two offsetting corrections in the
local log, all stamped at the same received instant, yet the unchanged aggregate
matches and the result can be labelled settled. A timestamp tie does not show
that the earlier declaration acknowledged subsequently recorded corrections.

## Proposed rule

A matching period closure acknowledges a selected value-changing revision only
when (1) its declared receipt time is at or after the correction receipt and
(2) the active closure revision appears later in the append-order fact log.
If either condition fails, return `pending` and `stale_closure`. A later closure
revision with the same aggregate count is sufficient under the bounded test
contract when the remaining checks pass. State-only promotions are not value
corrections and do not create a fresh-closure requirement.

Example: initial first=1, second=0, closure count=1. Append a same-count closure
revision at 21:00, then revise first to 0 and second to 1, both at 21:00.
The aggregate remains one, but the active closure precedes both changes:
`stale_closure`. Append another same-count closure revision at 21:00 and the
same factual history may now settle, because the acknowledgement follows both
corrections in the local log.

## Compatibility, affected components and testing

The rule changes one observable behaviour: time-tied closure records that
precede covered corrections now fail conservatively. Existing accepted histories
whose closure already follows their corrections, including equal-time ties,
retain their result. It changes no JSON schema fields or public API shape.

Python: `src/tallystick/settlement.py`, using indices from append-order history.
Independent JavaScript: `conformance/reference.mjs`, retaining the latest
visible value-change index with its receipt instant. Unit and cross-language
tests compare the premature and later acknowledgement. Existing 23 golden
cases and the synthetic season are unchanged; their previous observed results
are not represented as tests of this newly added edge case.

Regression outcome must be verified at the exact proposed commit, including
Python 3.11/3.14, Windows 3.12 and the independent JavaScript evaluator.
An implementation that is green but has not been reviewed externally does not
complete D1 or D2. Review residual limits: `received_at` is a declared time,
source authority is configured locally, and recorder log sequence does not
establish completeness or genuine upstream chronology.

## Decision and review

This is a conservative research-contract correction, not an assertion of
contractual sports-settlement law. Record independent semantic review before
freezing the v0.2 reference, and document any alternative tie-ordering
semantics needed for a specific authorised provider. No real-data profile or
live jurisdiction policy is enabled by this change.
