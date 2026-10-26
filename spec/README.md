# Tallystick input formats, version 0.1

These JSON Schema 2020-12 documents describe the structural input formats used by the reference workbench. They support editors, interchange, and preliminary validation. The Python validators and compiler still determine whether an input is usable, authorized by the declared fixtures, temporally consistent, and admissible in this synthetic build.

The schema files and original format definitions in this directory are licensed **CC BY 4.0**, with attribution to Albert Tan Sin Hon, Tallystick format definitions, version 0.1. See [LICENSE](LICENSE). Executable code elsewhere in the repository retains its separate Apache-2.0 licence. The schemas do not grant rights to sports data or the separately supplied whitepaper.

## Documents and identifiers

| File | Stable project identifier | Input |
| --- | --- | --- |
| [fact.schema.json](fact.schema.json) | `urn:tallystick:schema:fact:0.1` | One unsigned fact payload |
| [market.schema.json](market.schema.json) | `urn:tallystick:schema:market:0.1` | One market proposal |
| [configuration.schema.json](configuration.schema.json) | `urn:tallystick:schema:configuration:0.1` | Source registry, declared licences, and rule packs, with an optional bundled market |

All three declare `https://json-schema.org/draft/2020-12/schema` as their dialect. Their URNs identify local resources and are not download addresses. JSON Schema's [core specification](https://json-schema.org/draft/2020-12/json-schema-core#section-8.2.1) distinguishes a schema identifier from a network location.

Load `market.schema.json` into a validator's local resource registry under its `$id` before validating configuration. The configuration schema refers to that resource for its optional market and common token/timestamp definitions. All other references are within the same file. No runtime network lookup is required or intended.

The supplied `examples/market.json` and `examples/configuration.json` demonstrate the latter two formats. Individual `stages[*].facts[*]` entries in `examples/synthetic-match.json` demonstrate the fact format. The whole synthetic replay scenario and signed output bundles have separate application formats; these schemas do not describe those envelopes.

## Common structural rules

Fixed objects specify their required fields and reject unknown fields with `additionalProperties: false`. The source registry is intentionally a bounded map: its property names must be valid tokens, and each property's value must have the exact source-entry shape.

Booleans use the JSON boolean type. Counts, periods, thresholds, and windows use the integer type with explicit inclusive limits. JSON Schema recognizes mathematical integers, so a validator can accept `1.0` as an integer. Python's reference validators require `type(value) is int` and therefore reject a decoded floating-point `1.0`. Write integer fields as JSON integers without a decimal point or exponent. Booleans such as `true` are never valid substitutes for integer fields. This distinction follows the [JSON Schema integer definition](https://json-schema.org/draft/2020-12/json-schema-validation#section-6.1.1).

Dates use `YYYY-MM-DDTHH:MM:SSZ`, optionally with one to six fractional second digits before `Z`. Numeric UTC offsets, missing seconds, spaces instead of `T`, and trailing text are rejected by the pattern. The terminal negative lookahead makes the expression reject even a trailing newline. `format: date-time` supplies an additional annotation; format assertion is configurable in the [2020-12 validation specification](https://json-schema.org/draft/2020-12/json-schema-validation#section-7.2). The application must still parse actual calendar dates, reject unsupported leap-second values, and compare timestamps.

The bounded JSON reader separately limits input to 1,048,576 bytes, 32 levels of nesting, and 100,000 visited structure elements, counting object keys. It rejects duplicate keys, non-finite numbers, invalid Unicode, and integers outside the interoperable range `[-(2**53-1), 2**53-1]`. Schema validation of an already parsed object cannot recover duplicate keys discarded by another JSON parser or enforce the original byte limit.

## Fact format

`fact.schema.json` follows `settlement.validate_fact_shape`. All 17 fields are required, including fields whose value can be `null`.

| Field or group | Structural constraint |
| --- | --- |
| `schema_version` | Exactly `"0.1"` |
| Fact, observation, event, subject, licence and optional predecessor identifiers | 1–160 printable ASCII characters, without spaces |
| `kind` | `corner.awarded`, `goal.scored`, `period.closed`, or `event.abandoned` |
| `period` | Integer 0–20 |
| `value` | Integer 0–100,000 for closures; 0 or 1 for all other kinds |
| `state` | `provisional`, `corroborated`, `official`, or `final` |
| `source_ids` | 1–16 distinct identifiers |
| `metric` | `corner.awarded` or `goal.scored` for a closure; otherwise `null` |
| `supersedes` | Identifier or `null` |
| `reason` | `null`, or text of length 1–2,000; application validation also rejects whitespace-only text |
| `occurred_at`, `received_at`, `correction_deadline` | UTC timestamps as described above |

The conditional closure rule is expressed in the schema with `if`/`then`/`else`. A fact's identifiers are deliberately broader than the compiler's token vocabulary because that is what the fact-shape validator accepts. A registry-backed source or licence ID must additionally match an actual registry entry, whose token syntax is tighter.

The following remain application checks:

- Occurrence must not follow receipt or the correction deadline; final receipt must be at or after that deadline.
- Fact IDs must be unique across the supplied history. Revisions must supersede the current observation head and preserve observation identity, metric, licence and correction deadline.
- Revisions cannot predate their predecessor, revise a final fact, change values after the correction window, or change values without a reason. An unchanged value cannot lose confirmation state.
- Corroboration requires the configured independent source groups. Official or final facts require a designated official source for that fact kind.
- Settlement requires the matching authoritative closure and count, appropriate states, consistent correction deadlines, and consideration of abandonment records.

The relevant functions are `validate_fact_shape`, `validate_revision`, `active_snapshot`, and `evaluate` in `src/tallystick/settlement.py`, with source authority and append-time checks in `src/tallystick/ledger.py`.

## Market proposal format

`market.schema.json` follows `compiler.validate_market`. All 15 top-level fields are required. Tokens begin with an ASCII letter or digit and continue with letters, digits, underscore, period, colon, slash, or hyphen, up to a total of 128 characters.

The settlement object has exactly `fact_type`, `period`, `threshold`, and `min_state`. Its metric is corners or goals, its period is an integer 1–10, its threshold is an integer 1–10,000, and its minimum state is `official` or `final`. Outcomes are exactly `["over", "under"]` in that order. `window_seconds` is 1–86,400 and `batch_window_ms` is 1–1,000.

The schema permits a boolean `consumer` value, any valid jurisdiction token, and either `aggregate` or `single_actor` participant scope because the proposal validator recognizes those values. The current compiler then rejects consumer flows, jurisdictions other than `TEST`, and single-actor proposals with explicit admission reasons. A schema-valid market is not necessarily an accepted market.

Application checks also require printable display text, reject selected directives in that text, ensure `close_at < correction_deadline`, and enforce current policy, source authority, and declared permissions. The compiler checks coverage for the requested count metric and for the supporting `period.closed` and `event.abandoned` facts. It checks licence and rule-pack expiry against the market's correction deadline. These relationships cannot be established from a standalone market schema.

The market's period and threshold limits are intentionally narrower than the generic fact and pure settlement evaluator limits. Use the market schema for compiler inputs rather than deriving compiler limits from `evaluate` alone.

## Configuration format

The supported configuration envelope requires `sources`, `licences`, and `rulepacks`; `market` is optional. It rejects other top-level fields. `examples/configuration.json` includes a bundled demonstration market. The `compile` CLI uses the explicitly supplied market file; the configuration's optional market does not override it. The CLI currently reads the three registry sections directly, so use this schema to enforce the envelope's unknown-field rule before passing external configuration into that path.

| Section | Bounds and supported values |
| --- | --- |
| `sources` | 1–1,000 entries; each entry has exactly `independence_group` and `official_kinds` |
| Source roles | Valid token for the group; 0–4 distinct supported fact kinds for official roles |
| `licences` | 1–128 objects; exact nine-field shape; `synthetic` must be `true` |
| Licence lists | 1–128 distinct entries each; source and territory tokens, five recognized uses, and four recognized fact types |
| `rulepacks` | 1–128 objects; exact thirteen-field shape; `basis` is `synthetic`, jurisdiction is `TEST`, and `allow_consumer` is `false` |
| Rule-pack metadata | Token ID and version; reviewer text of length 1–200; application also requires printable, nonblank text |
| Rule-pack policy | Minimum window 1–86,400 seconds; 1–2 distinct corners/goals metrics; required state `official` or `final` |

`uniqueItems` rejects repeated identical array elements. It does not guarantee uniqueness of one property across different objects: two licence objects with the same `licence_id` but different remaining content still require the registry's duplicate-ID check. The same applies to rule-pack IDs.

`RightsRegistry` checks that licensed source IDs exist, validates date ordering, and checks permission use, territory, metric, source membership, and validity at the requested instant. `MarketCompiler` checks rule-pack date order and admission at the requested instant. Source groups, official roles, licences, reviewer names, and policy packs are local synthetic declarations; neither a schema nor this build verifies legal rights, real independence, credentials, or human approval.

## Validation status

The schema files have been checked for JSON syntax, local reference integrity, field-set correspondence, and agreement of their documented examples with the application validators. No JSON Schema validator dependency was available in the build environment, so these files have not been advertised as passing a separate draft-2020-12 validator suite, and none was added solely for this documentation task.

When integrating a validator, choose draft 2020-12 explicitly, preload the resource identifiers above, decide whether to enable format assertions, and keep all application checks. Schema validation does not replace source verification, revision validation, signed-record verification, rights checks, compiler admission, or settlement evaluation.
