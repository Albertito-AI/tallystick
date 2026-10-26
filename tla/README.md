# Bounded state models

These models examine selected design invariants. They are deliberately smaller
than the Python implementation and its network, storage and cryptographic
environment. Passing them does not prove that the implementation refines the
models, that an unbounded model is correct, that live feeds are complete, or that
a system meets a regulatory standard. No liveness claim is made.

`Settlement.tla` allows up to three observation revisions and counts from zero
to three. It explores incomplete or mismatching closure declarations, confirmation,
settlement, correction-window closure and finalisation. The invariants require
every settled decision to reference the current complete official observation,
and every finalised result to retain its locked revision.

`Acceptance.tla` explores three request identities under an exposure limit of
two units. The model permits batch closure, a declared watermark, mandate
revocation, acceptance and retries in different orders. Its invariants require
accepted requests to have been ready and authorised when accepted, preserve the
aggregate limit, and prevent a retry from creating a second charge. A truthful
watermark and fixed request payload are assumptions of this abstract model.
Payload-conflict behaviour and concurrent persistence are implementation tests.

## Reproduce

Use Java and the official [TLA+ 1.7.4 tools release](https://github.com/tlaplus/tlaplus/releases/tag/v1.7.4).
The reviewed `tla2tools.jar` has SHA-256
`936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88`.
Its SHA-1 matches the checksum published on that release page:
`bee4a54f3ee3d4afc347c3240ec2d9e93b075104`.
The jar is a development tool and is not committed to this repository.

From the repository root:

```sh
python tla/check.py --jar path/to/tla2tools.jar --output local-model-checks.json
```

The runner validates the tool hash before execution, sets a 60-second limit for
each model, uses one worker, and records the exact model/configuration hashes.
Some sandboxed environments block the local socket used by TLC's runtime; a
socket error is an unsuccessful check, not a model result.

## Recorded run

The check on 26 October 2026 completed both state spaces without an invariant
error:

| Model | Generated states | Distinct states | Result |
| --- | ---: | ---: | --- |
| Settlement | 1,267 | 195 | Passed the configured bounded invariants |
| Acceptance | 87 | 26 | Passed the configured bounded invariants |

See [execution-record.json](execution-record.json) for the measured run,
tool identity and source/configuration hashes. Re-run after a model or
configuration change before relying on that receipt.
