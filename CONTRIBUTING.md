# Contributing

Start with a small issue describing a reproducible requirement or defect.
Use synthetic fixtures or data with documented permission. Do not include
licensed-feed samples, confidential client documents or credentials.

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
