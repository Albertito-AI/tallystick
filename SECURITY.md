# Security

This is a local research implementation with synthetic data and no real-money
connection. Use isolated development environments and permitted test inputs.
No production security audit or supplier certification is claimed.

Private vulnerability reporting is enabled. Use the repository's **Security** tab
and **Report a vulnerability** to send a reproducible security issue privately.
Do not put personal data, supplier data, private keys or working exploit
credentials in public issues. Include the commit, platform, smallest synthetic
reproduction and observed versus expected behaviour.

## Trust boundaries

- A recorder signature proves possession of a key, not the truth of a sports fact.
- Source independence and official roles are configured declarations.
- A pinned checkpoint can detect a changed representation. The local database
  is not an externally witnessed immutable service.
- The pure settlement evaluator expects ingestion-validated facts. Use the
  workbench to apply source and permission checks.
- Input is bounded JSON. No market expression is passed to `eval`, a shell or
  a model. Text is data and must remain so in downstream integrations.
- The display-text filter catches only specified directives; it is not a
  comprehensive prompt-injection defence.
- The HTTP report server binds to loopback, has fixed routes and performs no
  writes. It is not an authenticated deployment server.
- The batch simulator is not durable, distributed or an exchange. Its source
  watermarks are declarations, not proof that no delayed event exists.

Use appropriate key custody, independent audits, authenticated source feeds,
access controls and deployment-specific review before considering an external
pilot. Keep live supplier credentials and data outside this repository.
