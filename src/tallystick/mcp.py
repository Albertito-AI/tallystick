"""Read-only synthetic tools over the MCP 2026-07-28 stdio binding.

This small implementation supports one verified protocol revision. It deliberately
does not emulate the removed initialize handshake or claim SDK certification.
"""
from __future__ import annotations

from collections import deque
import json
import math
import re
import sys
import time
from typing import BinaryIO, TextIO

from . import __version__
from .compiler import MarketCompiler
from .crypto import SigningKey
from .fixtures import AS_OF, configuration
from .ledger import Ledger
from .pricing import whitepaper_example
from .rights import RightsRegistry
from .settlement import parse_time
from .validation import InputError, MAX_JSON_BYTES, exact_keys, loads, require
from .workbench import settlement_with_rights

PROTOCOL_VERSION = "2026-07-28"
PREFIX = "io.modelcontextprotocol/"
MAX_FACTS = 256
CALLS_PER_MINUTE = 60
SERVER_INFO = {"name": "tallystick-synthetic", "version": __version__}
CAPABILITIES = {"tools": {"listChanged": False}}
_META_KEY = re.compile(
    r"(?:(?:[A-Za-z](?:[A-Za-z0-9-]*[A-Za-z0-9])?)(?:\.[A-Za-z](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*/)?"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?)?\Z"
)


def _object(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


_TEXT = {"type": "string", "minLength": 1, "maxLength": 128}
_TIME = {"type": "string", "format": "date-time", "description": "Explicit UTC time ending in Z."}
_MARKET = _object({
    "schema_version": {"const": "0.1"}, "market_id": _TEXT, "event_id": _TEXT,
    "name": {"type": "string", "minLength": 1, "maxLength": 120},
    "settlement": _object({"fact_type": {"enum": ["corner.awarded", "goal.scored"]},
        "period": {"type": "integer", "minimum": 1, "maximum": 10},
        "threshold": {"type": "integer", "minimum": 1, "maximum": 10000},
        "min_state": {"enum": ["official", "final"]}}),
    "outcomes": {"const": ["over", "under"]}, "close_at": _TIME,
    "correction_deadline": _TIME, "jurisdiction": _TEXT, "licence_id": _TEXT,
    "rulepack_id": _TEXT, "consumer": {"type": "boolean"},
    "window_seconds": {"type": "integer", "minimum": 1, "maximum": 86400},
    "participant_scope": {"enum": ["aggregate", "single_actor"]},
    "batch_window_ms": {"type": "integer", "minimum": 1, "maximum": 1000},
})
_FACT = _object({
    "schema_version": {"const": "0.1"}, "fact_id": _TEXT, "observation_id": _TEXT,
    "event_id": _TEXT,
    "kind": {"enum": ["corner.awarded", "goal.scored", "period.closed", "event.abandoned"]},
    "period": {"type": "integer", "minimum": 0, "maximum": 20}, "subject": _TEXT,
    "value": {"type": "integer", "minimum": 0, "maximum": 100000},
    "state": {"enum": ["provisional", "corroborated", "official", "final"]},
    "source_ids": {"type": "array", "minItems": 1, "maxItems": 3, "uniqueItems": True,
                   "items": {"enum": ["demo-feed-a", "demo-feed-b", "demo-official"]}},
    "licence_id": {"const": "synthetic-licence"}, "occurred_at": _TIME, "received_at": _TIME,
    "supersedes": {"type": ["string", "null"]}, "reason": {"type": ["string", "null"]},
    "correction_deadline": _TIME, "metric": {"enum": [None, "corner.awarded", "goal.scored"]},
})
_ANNOTATIONS = {"readOnlyHint": True, "destructiveHint": False,
                "idempotentHint": True, "openWorldHint": False}
TOOLS = [
    {"name": "tallystick_market_check", "title": "Check a synthetic market",
     "description": "Validate a fictional synthetic-* event against the fixed TEST fixture policy and permissions. No legal clearance or live execution. A new ephemeral recorder key signs each accepted example.",
     "inputSchema": _object({"market": _MARKET, "as_of": _TIME}), "annotations": _ANNOTATIONS},
    {"name": "tallystick_pricing_example", "title": "Recompute the whitepaper pricing example",
     "description": "Return the fixed illustrative Poisson, correlation, odds and LMSR calculations. No fitted model, real prices or recommendations.",
     "inputSchema": _object({}), "annotations": _ANNOTATIONS},
    {"name": "tallystick_settlement_preview", "title": "Preview synthetic settlement",
     "description": "Validate up to 256 fictional facts through an ephemeral ledger using only the bundled source registry, then apply TEST rights and settlement rules at as_of. The market policy is checked at the fixed fixture issue time 2026-01-01T12:00:00Z. No retained log or payout.",
     "inputSchema": _object({"market": _MARKET,
         "facts": {"type": "array", "maxItems": MAX_FACTS, "items": _FACT}, "as_of": _TIME}),
     "annotations": _ANNOTATIONS},
]
_TOOL_NAMES = {tool["name"] for tool in TOOLS}


class _ProtocolError(Exception):
    def __init__(self, code: int, message: str, data=None):
        super().__init__(message)
        self.code, self.data = code, data


def _error(request_id, code: int, message: str, data=None) -> dict:
    result = {"jsonrpc": "2.0", "error": {"code": code, "message": message}}
    if request_id is not None:
        result["id"] = request_id
    if data is not None:
        result["error"]["data"] = data
    return result


def _result(request_id, body: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id,
            "result": {"resultType": "complete", "_meta": {PREFIX + "serverInfo": SERVER_INFO}, **body}}


def _tool_result(body: dict, error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(body, ensure_ascii=True, allow_nan=False)}],
            "structuredContent": body, "isError": error}


def _check_metadata(params: dict) -> None:
    meta = params.get("_meta")
    if type(meta) is not dict or any(not _META_KEY.fullmatch(key) for key in meta):
        raise _ProtocolError(-32602, "Valid per-request _meta is required")
    version = meta.get(PREFIX + "protocolVersion")
    if type(version) is not str:
        raise _ProtocolError(-32602, "A per-request protocolVersion is required")
    if version != PROTOCOL_VERSION:
        raise _ProtocolError(-32022, "Unsupported protocol version",
                             {"supported": [PROTOCOL_VERSION], "requested": version})
    if type(meta.get(PREFIX + "clientCapabilities")) is not dict:
        raise _ProtocolError(-32602, "Per-request clientCapabilities must be an object")
    info = meta.get(PREFIX + "clientInfo")
    if PREFIX + "clientInfo" in meta and (type(info) is not dict or any(
            type(info.get(key)) is not str or not info[key] for key in ("name", "version"))):
        raise _ProtocolError(-32602, "clientInfo requires a name and version")
    if "progressToken" in meta and type(meta["progressToken"]) not in (str, int):
        raise _ProtocolError(-32602, "Invalid progressToken")
    if PREFIX + "logLevel" in meta and meta[PREFIX + "logLevel"] not in (
            "debug", "info", "notice", "warning", "error", "critical", "alert", "emergency"):
        raise _ProtocolError(-32602, "Invalid logLevel")


def _only_params(params: dict, required: set[str], optional: set[str] | None = None) -> None:
    try:
        exact_keys(params, required | {"_meta"}, optional)
    except InputError as error:
        raise _ProtocolError(-32602, str(error)) from error


def _run_tool(name: str, arguments: dict) -> dict:
    if name == "tallystick_pricing_example":
        exact_keys(arguments, set())
        return {"synthetic": True, "scope": "illustrative_model_only", "pricing": whitepaper_example()}
    expected = {"market", "as_of"} | ({"facts"} if name == "tallystick_settlement_preview" else set())
    exact_keys(arguments, expected)
    parse_time(arguments["as_of"])
    conf = configuration()
    market = arguments["market"]
    require(type(market) is dict, "market must be an object")
    require(type(market.get("event_id")) is str and market["event_id"].startswith("synthetic-"),
            "Only fictional event identifiers beginning synthetic- are accepted", "LIVE_DATA_DISABLED")
    rights = RightsRegistry(conf["licences"], conf["sources"])
    signer = SigningKey.generate()
    compiler = MarketCompiler(rights, conf["rulepacks"], signer)
    checked_at = arguments["as_of"] if name == "tallystick_market_check" else AS_OF
    compiled = compiler.compile(market, checked_at)
    if name == "tallystick_market_check":
        return {"synthetic": True, "scope": "ephemeral_demo_only",
                "recorder_public_key": signer.public_key_hex, **compiled}
    require(compiled["accepted"], ", ".join(compiled["reasons"]), "MARKET_REJECTED")
    facts = arguments["facts"]
    require(type(facts) is list and len(facts) <= MAX_FACTS, "facts must contain at most 256 records")
    with Ledger(":memory:", signer, conf["sources"], "tallystick-mcp-preview") as ledger:
        for index, fact in enumerate(facts):
            require(type(fact) is dict, "Every fact must be an object")
            require(fact.get("event_id") == market["event_id"], "Every fact must belong to the synthetic market event")
            # This validates registered source authority, evidence states and revisions.
            # The memory ledger is destroyed after this single request.
            ledger.append_fact(fact, f"preview:{index}", fact.get("received_at"))
            rights.require(licence_id=fact["licence_id"], use="settlement", territory=market["jurisdiction"],
                           fact_type=fact["kind"], source_ids=fact["source_ids"], as_of=fact["received_at"])
        result, checks = settlement_with_rights(market, ledger.facts(), rights, arguments["as_of"],
                                              compiler.rulepacks)
    return {"synthetic": True, "scope": "synthetic_preview_only", "result": result,
            "rights_checks": checks, "validated_fact_count": len(facts), "policy_checked_at": checked_at}


class _Server:
    def __init__(self):
        self._calls: deque[float] = deque()

    def dispatch(self, message) -> dict | None:
        request_id = message.get("id") if type(message) is dict else None
        if type(request_id) not in (str, int) or (type(request_id) is int and abs(request_id) > 2**53 - 1):
            request_id = None
        try:
            if (type(message) is not dict or message.get("jsonrpc") != "2.0"
                    or type(message.get("method")) is not str
                    or not message.keys() <= {"jsonrpc", "id", "method", "params"}
                    or ("id" in message and request_id is None)):
                raise _ProtocolError(-32600, "Invalid JSON-RPC request")
            if "id" not in message:
                # Notifications never invoke tools and never receive responses. No
                # subscription or background work is advertised by this server.
                return None
            params = message.get("params")
            if type(params) is not dict:
                raise _ProtocolError(-32602, "Request params must be an object")
            method = message["method"]
            if method == "initialize":
                version = params.get("protocolVersion")
                if type(version) is str and version != PROTOCOL_VERSION:
                    raise _ProtocolError(-32022, "Unsupported protocol version; this server uses per-request metadata",
                                         {"supported": [PROTOCOL_VERSION], "requested": version})
                raise _ProtocolError(-32601, "initialize is unavailable; use MCP 2026-07-28 per-request metadata",
                                     {"supported": [PROTOCOL_VERSION]})
            _check_metadata(params)
            if method == "server/discover":
                _only_params(params, set())
                return _result(request_id, {"supportedVersions": [PROTOCOL_VERSION], "capabilities": CAPABILITIES,
                    "instructions": "Synthetic local research tools. Use only invented TEST inputs. These results do not grant data rights, legal clearance, or authority to place wagers.",
                    "ttlMs": 60000, "cacheScope": "public"})
            if method == "tools/list":
                _only_params(params, set(), {"cursor"})
                if "cursor" in params:
                    raise _ProtocolError(-32602, "No continuation cursor is available")
                return _result(request_id, {"tools": TOOLS, "ttlMs": 60000, "cacheScope": "public"})
            if method != "tools/call":
                raise _ProtocolError(-32601, "Method not found")
            _only_params(params, {"name"}, {"arguments"})
            name, arguments = params["name"], params.get("arguments", {})
            if type(name) is not str or name not in _TOOL_NAMES:
                raise _ProtocolError(-32602, "Unknown tool")
            if type(arguments) is not dict:
                raise _ProtocolError(-32602, "Tool arguments must be an object")
            now = time.monotonic()
            while self._calls and now - self._calls[0] >= 60:
                self._calls.popleft()
            if len(self._calls) >= CALLS_PER_MINUTE:
                return _result(request_id, _tool_result({"code": "RATE_LIMIT", "message": "At most 60 tool calls per minute are allowed"}, True))
            self._calls.append(now)
            try:
                body = _run_tool(name, arguments)
                return _result(request_id, _tool_result(body))
            except (ValueError, TypeError, KeyError, OverflowError) as error:
                return _result(request_id, _tool_result({"code": getattr(error, "code", "INVALID_INPUT"),
                                                        "message": str(error)}, True))
        except _ProtocolError as error:
            return _error(request_id, error.code, str(error), error.data)


def _bounded_message(raw: bytes):
    message = loads(raw)
    # Also catches exponent overflow (1e999), which JSON parse_constant does not.
    stack = [message]
    while stack:
        value = stack.pop()
        if type(value) is float and not math.isfinite(value):
            raise InputError("JSON numbers must be finite")
        if type(value) is dict:
            stack.extend(value.values())
        elif type(value) is list:
            stack.extend(value)
    return message


def serve_stdio(stdin: BinaryIO | None = None, stdout: BinaryIO | None = None,
                stderr: TextIO | None = None) -> int:
    """Serve bounded newline-framed requests until EOF; return a process exit code.

    Streams default to the process standard streams. No user-controlled path,
    network endpoint, source registry, signing key or executable is accepted.
    """
    source = stdin if stdin is not None else sys.stdin.buffer
    target = stdout if stdout is not None else sys.stdout.buffer
    errors = stderr if stderr is not None else sys.stderr
    server = _Server()

    def send(message):
        target.write(json.dumps(message, ensure_ascii=True, allow_nan=False,
                                separators=(",", ":")).encode("utf-8") + b"\n")
        target.flush()

    try:
        while True:
            raw = source.readline(MAX_JSON_BYTES + 2)
            if not raw:
                return 0
            if len(raw.rstrip(b"\n")) > MAX_JSON_BYTES or not raw.endswith(b"\n"):
                send(_error(None, -32700, "Input must be a newline-terminated JSON message of at most 1 MiB"))
                return 2
            try:
                message = _bounded_message(raw[:-1])
            except (ValueError, UnicodeError, RecursionError):
                send(_error(None, -32700, "Invalid JSON or input structure exceeds limits"))
                continue
            try:
                response = server.dispatch(message)
            except Exception:
                # Do not send stack traces, input payloads or local paths to the client.
                errors.write("Tallystick MCP request failed internally\n")
                errors.flush()
                candidate = message.get("id") if type(message) is dict else None
                request_id = candidate if type(candidate) in (str, int) else None
                response = _error(request_id, -32603, "Internal server error")
            if response is not None:
                send(response)
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(serve_stdio())
