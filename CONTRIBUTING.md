# Contributing

Tallystick is a public experimental reference. Co-creators are welcome to improve
its reproducibility, semantics, evidence explanations and first-use experience.
Start with a small issue describing a reproducible requirement or defect.
Use synthetic fixtures or data with documented permission. Do not include
licensed-feed samples, confidential client documents or credentials.

## Starter tasks

### Reproduce the quickstart

Follow the README from a fresh checkout and virtual environment using the
included fictional scenario. Record the exact commit, operating system, Python
and Node versions, commands, verification output and any unclear step. Check that
the exported bundle verifies and the local dashboard opens. A useful result is a
run report plus a small documentation correction where needed. No hosted service
or paid Codespace is required. Describe a run as independent only when someone
outside the original implementation workflow actually performed it.

### Review a correction or completeness edge case

Choose one ambiguity in the documented settlement semantics. Write the expected
outcome and reasoning before changing either evaluator. Propose a minimal
synthetic case covering the original observation, correction and closure state.
Completion means the expected outcome is reviewed, both implementations are
checked against it, and any disagreement is explained. Coordinate the case in an
issue first; changes to decision rules follow the RFC process below.

### Explain how a reader verifies an evidence bundle

Walk through the supplied demo using the README and verification documentation.
Identify any step that obscures what the recorder signature, pinned public key,
complete record or replay result establishes. Propose a short documentation change
with a reproducible synthetic example. Completion means the instructions can be
followed and preserve the stated limits around fact truth and trusted time.

## Proposing changes

Changes to fact or market semantics require an RFC describing compatibility,
the decision rules, failure behaviour and independent conformance cases.
Update both settlement implementations independently from the stated semantics.
An implementation agreeing only with itself is insufficient evidence.

Run `python -m unittest discover -s tests -v`, the demonstration and its verifier.
Node.js is needed for the independent evaluator. Include relevant TLA+ model
results when state semantics change. Explain scope and remaining uncertainty
without describing simulated results as customer or production outcomes.

Original contributions are made under the repository's applicable licences.
Confirm your right to contribute each file and identify third-party material.

## Credit and funded collaboration

Describe the work you performed and the tools or sources that materially assisted
it. Credit accepted contributions in the relevant pull request or release notes
using the contributor's preferred name or GitHub handle. Record independent review
only when it actually occurred.

Funded development, research, documentation or support can be proposed when there
is a specific opportunity. Agree scope, roles, acceptance criteria, IP, payment
and ongoing support terms in writing before work starts. Voluntary participation
does not create an automatic payment entitlement or revenue-sharing arrangement.

Report sensitive security issues using the private route in [SECURITY.md](SECURITY.md).
