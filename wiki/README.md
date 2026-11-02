# Wiki publication source

[Read the complete whitepaper](Whitepaper.md). This is the versioned source for the
project's GitHub Wiki. It is an AI-assisted design synthesis, not independent
review or a claim that the ideal roadmap is already implemented. Existing project
rights and visibility remain unchanged.

## Publication state

At preparation, the Wiki had not been verified as initialised. A committed file
is not proof that a Wiki page is live. GitHub requires a first Wiki page before
ordinary Git publication: [create that page](https://github.com/Albertito-AI/tallystick/wiki/_new).
Use the title `Home`, add a short welcome and save.

The `Publish project whitepaper to Wiki` workflow runs after that initial Wiki
edit and after later source changes. It uses the repository-scoped workflow token.
Its summary reports `PUBLISHED`, `ALREADY_CURRENT` or
`BLOCKED_UNINITIALISED`; the last state means no Wiki page was published.
No paid service or third-party publishing action is used.

The publisher writes only its marked Whitepaper page and a marked, additive Home
section. It preserves other pages and Home text, refuses an existing unmarked
Whitepaper, and uses a non-forced push. Concurrent changes require reconciliation.
Edit the versioned source for future paper updates. The script never executes Wiki
content, changes visibility or grants new reuse rights.

GitHub's documented initialisation requirement:
https://docs.github.com/en/communities/documenting-your-project-with-wikis/adding-or-editing-wiki-pages
