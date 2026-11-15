# Wiki publication source

[Read the complete whitepaper](Whitepaper.md). This is the versioned source for the
project's GitHub Wiki. It is an AI-assisted design synthesis, not independent
review or a claim that the ideal roadmap is already implemented. Existing project
rights and visibility remain unchanged.

## Publication state

On 15 November 2026, anonymous retrieval of the separate [live Wiki](https://github.com/Albertito-AI/tallystick/wiki) succeeded at Wiki commit `c27d7841d01b4c928a60fc02308ba586c43492fe`. Its `Whitepaper.md` was byte-identical to the committed source at `80c6da4af1e95108b80905fb33e8a30f57f741f5`. The managed Home section also matched; the Wiki retained its surrounding welcome text. This is a dated publication receipt, not a promise that later source or Wiki edits have already propagated.

The 15 November scholarly revision must receive a separate successful publication check after merge. A local candidate or repository commit alone does not prove that the live page has updated. The earlier preparation note that initialisation was unverified is historical and no longer describes this observed baseline.

Edit the versioned source for ordinary updates. Only if a later publication reports `BLOCKED_UNINITIALISED` and inspection confirms the Wiki has no first page should a maintainer [create a Home page](https://github.com/Albertito-AI/tallystick/wiki/_new). Do not recreate or overwrite an existing Home page to resolve unrelated authentication, conflict or publishing failures.

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
