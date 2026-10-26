# Agent interface

The local stdio server exposes three read-only tools over **MCP 2026-07-28**.
It uses the bundled fictional source, licence and TEST policy records. It opens
no network listener and accepts no filenames, URLs, registries, signing keys,
shell commands or executable expressions as tool parameters.

## Protocol pin

The official specification landing page resolved to 2026-07-28 when checked on
2026-10-26. That revision removed `initialize`, `notifications/initialized` and
`ping`, and introduced per-request metadata and `server/discover`. This server
implements the current lifecycle only; a client that only implements the older
handshake needs an upgrade or a separate compatibility adapter.

Sources: [official changes](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
and [versioning rules](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning).

Every request supplies its protocol version and client capabilities under
`params._meta`. Discovery is optional. A valid tool call works as the first
request, and later calls cannot borrow metadata from earlier ones. Unsupported
versions return `-32022` with the supported version list; missing required
metadata returns `-32602`. Successful results contain `resultType: "complete"`
and server identity. Discovery and tool-list results include cache hints.

The available methods are `server/discover`, `tools/list` and `tools/call`.
Unknown methods return `-32601`; unknown tools or invalid call envelopes return
`-32602`. Domain validation failures use a tool result with `isError: true`.
Valid notifications receive no response and cannot invoke a tool. This server
advertises no subscriptions, background tasks, sampling or elicitation.

Sources: [base protocol metadata](https://modelcontextprotocol.io/specification/2026-07-28/basic#_meta),
[schema reference](https://modelcontextprotocol.io/specification/2026-07-28/schema)
and [tool messages](https://modelcontextprotocol.io/specification/2026-07-28/server/tools).

This is a small, independently tested implementation of the selected interface,
not an official MCP certification or a claim of interoperability with every host.

## Launch

After installing the project in the Python environment used by the host:

```sh
python -m tallystick mcp
```

The direct module entry point also works:

```sh
python -m tallystick.mcp
```

A host that accepts stdio command configuration can use the following entry.
Replace `python` with the interpreter from the environment where this package is
installed if the host does not inherit that environment. The surrounding host
configuration format is host specific.

```json
{
  "command": "python",
  "args": ["-m", "tallystick", "mcp"]
}
```

Each wire message is a single UTF-8 JSON object followed by a newline. Standard
output contains only protocol messages; diagnostics use standard error. Closing
standard input cleanly stops the server, as described by the
[stdio binding](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio).

This complete discovery request can be sent as one line:

```json
{"jsonrpc":"2.0","id":1,"method":"server/discover","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{},"io.modelcontextprotocol/clientInfo":{"name":"local-example","version":"1"}}}}
```

This tool request is also self-contained:

```json
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}},"name":"tallystick_pricing_example","arguments":{}}}
```

## Tools and boundaries

| Tool | Arguments | Result and scope |
| --- | --- | --- |
| `tallystick_market_check` | `market`, `as_of` | Run the market compiler against fixture permissions and policy. Return acceptance or reasons and an ephemeral example certificate. |
| `tallystick_pricing_example` | `{}` | Recompute the whitepaper's supplied-model arithmetic, including correlation and LMSR. No real probability model is fitted. |
| `tallystick_settlement_preview` | `market`, `facts`, `as_of` | Validate the full fact history in a temporary in-memory ledger, then evaluate the requested snapshot with rights and policy checks. Return the result and permission checks. |

Every input schema rejects extra argument fields. Market and fact objects follow
the repository's bounded count language. Use the complete market returned by
`tallystick.fixtures.configuration()` and invented event identifiers beginning
`synthetic-`. `tools/list` returns the full argument schemas.

The market checker evaluates policy at the supplied `as_of`. Settlement preview
checks initial market admissibility at the fixed fixture issue time,
`2026-01-01T12:00:00Z`, because the requested settlement time normally follows
market close. Its response makes that issue time explicit. Rights and policy are
checked again at the settlement snapshot. Unknown, expired or live-jurisdiction
configurations cannot produce a successful live decision.

Preview facts must belong to that market's event and be ordered by receipt time.
The ledger validates source roles, evidence states, immutable observation identity,
revision chains and correction deadlines. Merely marking a fact `official` is
insufficient: its source must have the corresponding role in the fixed registry.
The labels `demo-feed-a`, `demo-feed-b`, `demo-official` and `synthetic-licence`
represent invented records only. They do not authenticate an upstream supplier.

Each preview uses a fresh memory ledger, which closes after the request. An
accepted market check uses a fresh recorder signing key; only the public key and
signature are returned. That key is ephemeral, not an established external trust
anchor. No private signing material is returned, and no result causes a wager,
payout, feed subscription or durable market registration.

## Bounds and verification

Input lines are limited to 1 MiB excluding the newline. JSON nesting is limited
to 32 levels and 100,000 values by the shared parser. Duplicate keys, non-finite
numbers and JSON batches are rejected. An oversized or unterminated line receives
a bounded error and closes the process; ordinary malformed JSON can be followed
by another valid line. A preview accepts at most 256 facts. The process permits
60 tool calls per rolling minute.

Calls execute synchronously and produce one final result. There is no background
job to cancel after that result; notifications are consumed between calls. This
prototype does not offer interruption of an in-progress calculation.

Run the subprocess tests with:

```sh
python -m unittest discover -s tests -p test_mcp.py -v
```

The tests start actual server processes and check discovery, direct first-call
operation, per-request version enforcement, legacy handshake rejection, line
framing, EOF shutdown, malformed input, tool errors, certificate verification,
source-authority enforcement and isolation between previews. Host-specific UI
integration and a remote transport are outside this test scope.
