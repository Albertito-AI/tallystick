"""Exercise actual stdio subprocesses, not only protocol helper functions."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from tallystick.crypto import verify_signature
from tallystick.fixtures import AS_OF, closure, configuration, fact

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2026-07-28"
META = {"io.modelcontextprotocol/protocolVersion": VERSION,
        "io.modelcontextprotocol/clientCapabilities": {},
        "io.modelcontextprotocol/clientInfo": {"name": "subprocess-test", "version": "1"}}


def request(number, method, **params):
    return {"jsonrpc": "2.0", "id": number, "method": method, "params": {"_meta": META, **params}}


def call(number, name, arguments=None):
    return request(number, "tools/call", name=name, arguments=arguments or {})


class MCPTests(unittest.TestCase):
    def exchange(self, messages=None, raw=None, exit_code=0):
        if raw is None:
            raw = b"".join(json.dumps(message).encode("utf-8") + b"\n" for message in messages)
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        process = subprocess.run([sys.executable, "-m", "tallystick.mcp"], input=raw,
                                 capture_output=True, timeout=20, cwd=ROOT, env=env)
        self.assertEqual(process.returncode, exit_code, process.stderr.decode("utf-8"))
        self.assertEqual(process.stderr, b"")
        self.assertTrue(not process.stdout or process.stdout.endswith(b"\n"))
        output = [json.loads(line) for line in process.stdout.splitlines()]
        for response in output:
            self.assertEqual(response["jsonrpc"], "2.0")
            self.assertEqual(int("result" in response) + int("error" in response), 1)
        return output

    def test_discovery_tools_and_clean_eof(self):
        responses = self.exchange([
            request("discover", "server/discover"), request("list", "tools/list"),
            call("example", "tallystick_pricing_example"),
        ])
        self.assertEqual([row["id"] for row in responses], ["discover", "list", "example"])
        discovery = responses[0]["result"]
        self.assertEqual(discovery["supportedVersions"], [VERSION])
        self.assertEqual(discovery["capabilities"], {"tools": {"listChanged": False}})
        for row in responses:
            self.assertEqual(row["result"]["resultType"], "complete")
            self.assertIn("io.modelcontextprotocol/serverInfo", row["result"]["_meta"])
        for row in responses[:2]:
            self.assertEqual(row["result"]["cacheScope"], "public")
            self.assertGreaterEqual(row["result"]["ttlMs"], 0)
        tools = responses[1]["result"]["tools"]
        self.assertEqual([tool["name"] for tool in tools], sorted(tool["name"] for tool in tools))
        self.assertEqual(len(tools), 3)
        for tool in tools:
            self.assertFalse(tool["inputSchema"]["additionalProperties"])
            self.assertTrue(tool["annotations"]["readOnlyHint"])
            self.assertFalse(tool["annotations"]["destructiveHint"])
            self.assertFalse(tool["annotations"]["openWorldHint"])
        result = responses[2]["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(json.loads(result["content"][0]["text"]), result["structuredContent"])
        self.assertEqual(result["structuredContent"]["pricing"]["status"], "ILLUSTRATIVE_MODEL_ONLY")

    def test_stateless_requests_need_no_discovery_and_cannot_borrow_metadata(self):
        responses = self.exchange([
            call(1, "tallystick_pricing_example"),
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            request(3, "tools/list"),
        ])
        self.assertFalse(responses[0]["result"]["isError"])
        self.assertEqual(responses[1]["error"]["code"], -32602)
        self.assertIn("tools", responses[2]["result"])

    def test_version_negotiation_and_legacy_handshake_rejection(self):
        old = request(1, "server/discover")
        old["params"]["_meta"] = dict(META, **{"io.modelcontextprotocol/protocolVersion": "2025-11-25"})
        legacy = {"jsonrpc": "2.0", "id": 2, "method": "initialize",
                  "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                             "clientInfo": {"name": "legacy", "version": "1"}}}
        output = self.exchange([old, legacy, {"jsonrpc": "2.0", "method": "notifications/initialized"},
                                request(3, "server/discover")])
        self.assertEqual(len(output), 3)
        for row in output[:2]:
            self.assertEqual(row["error"]["code"], -32022)
            self.assertEqual(row["error"]["data"], {"supported": [VERSION], "requested": "2025-11-25"})
        self.assertEqual(output[2]["result"]["supportedVersions"], [VERSION])

    def test_unknown_methods_tools_and_bad_arguments_are_distinct(self):
        output = self.exchange([
            request(1, "ping"), call(2, "not_a_tool"),
            call(3, "tallystick_pricing_example", {"path": "/not/read"}),
            request(4, "tools/call", name="tallystick_pricing_example", arguments=[]),
            request(5, "tools/list", cursor="unissued"),
        ])
        self.assertEqual(output[0]["error"]["code"], -32601)
        self.assertEqual(output[1]["error"]["code"], -32602)
        self.assertTrue(output[2]["result"]["isError"])
        self.assertEqual(output[2]["result"]["structuredContent"]["code"], "INVALID_INPUT")
        self.assertEqual(output[3]["error"]["code"], -32602)
        self.assertEqual(output[4]["error"]["code"], -32602)

    def test_market_check_has_ephemeral_public_signature_and_rejects_live_policy(self):
        market = configuration()["market"]
        live = dict(market, jurisdiction="GB")
        output = self.exchange([
            call(1, "tallystick_market_check", {"market": market, "as_of": AS_OF}),
            call(2, "tallystick_market_check", {"market": live, "as_of": AS_OF}),
        ])
        accepted = output[0]["result"]["structuredContent"]
        self.assertTrue(accepted["accepted"])
        cert = accepted["certificate"]
        self.assertTrue(verify_signature(cert["payload"], cert["signature"], accepted["recorder_public_key"]))
        self.assertEqual(accepted["scope"], "ephemeral_demo_only")
        rejected = output[1]["result"]["structuredContent"]
        self.assertFalse(rejected["accepted"])
        self.assertIn("LIVE_JURISDICTION_UNAVAILABLE", rejected["reasons"])
        self.assertIsNone(rejected["certificate"])

    def test_preview_revalidates_authority_and_never_retains_a_prior_call(self):
        market = configuration()["market"]
        history = [fact(i) for i in range(1, 7)] + [closure(6)]
        arguments = {"market": market, "facts": history, "as_of": "2026-01-01T14:00:00Z"}
        forged = deepcopy(arguments)
        forged["facts"][0]["source_ids"] = ["demo-feed-a"]
        empty = dict(arguments, facts=[])
        foreign = dict(arguments, market=dict(market, jurisdiction="GB"))
        output = self.exchange([call(i, "tallystick_settlement_preview", value)
                                for i, value in enumerate([arguments, forged, empty, foreign], 1)])
        complete = output[0]["result"]["structuredContent"]
        self.assertEqual((complete["result"]["status"], complete["result"]["count"],
                          complete["result"]["outcome"]), ("settled", 6, "over"))
        self.assertEqual(complete["validated_fact_count"], 7)
        self.assertEqual(complete["policy_checked_at"], AS_OF)
        self.assertTrue(output[1]["result"]["isError"])
        self.assertEqual(output[1]["result"]["structuredContent"]["code"], "SOURCE_AUTHORITY")
        absent = output[2]["result"]["structuredContent"]["result"]
        self.assertEqual(absent["reasons"], ["no_event_facts"])
        self.assertEqual(absent["status"], "pending")
        self.assertTrue(output[3]["result"]["isError"])
        self.assertEqual(output[3]["result"]["structuredContent"]["code"], "MARKET_REJECTED")

    def test_notifications_produce_no_response_or_tool_invocation(self):
        notification = call(1, "tallystick_pricing_example")
        notification.pop("id")
        output = self.exchange([notification,
            {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 999}},
            request(2, "tools/list")])
        self.assertEqual([row["id"] for row in output], [2])

    def test_bad_json_duplicate_keys_depth_nonfinite_and_batches(self):
        nested = b'{"x":' * 35 + b'0' + b'}' * 35
        valid = json.dumps(request(9, "tools/list")).encode("utf-8")
        raw = b"\n".join([b"{", b'{"jsonrpc":"2.0","jsonrpc":"2.0"}', nested,
                          b'{"value":NaN}', b'{"value":1e999}', b"[]", valid]) + b"\n"
        output = self.exchange(raw=raw)
        self.assertEqual([row["error"]["code"] for row in output[:-1]],
                         [-32700, -32700, -32700, -32700, -32700, -32600])
        self.assertEqual(output[-1]["id"], 9)

    def test_null_boolean_and_fractional_ids_are_invalid(self):
        output = self.exchange([request(value, "tools/list") for value in [None, True, 1.25]])
        self.assertEqual([row["error"]["code"] for row in output], [-32600] * 3)

    def test_oversized_and_unterminated_lines_close_with_bounded_error(self):
        for raw in [b"x" * (1_048_576 + 10) + b"\n", b'{"jsonrpc":"2.0"}']:
            with self.subTest(size=len(raw)):
                output = self.exchange(raw=raw, exit_code=2)
                self.assertEqual(len(output), 1)
                self.assertEqual(output[0]["error"]["code"], -32700)

    def test_call_and_preview_bounds(self):
        output = self.exchange([call(i, "tallystick_pricing_example") for i in range(61)])
        self.assertTrue(all(not row["result"]["isError"] for row in output[:-1]))
        self.assertEqual(output[-1]["result"]["structuredContent"]["code"], "RATE_LIMIT")
        too_many = {"market": configuration()["market"], "facts": [{}] * 257,
                    "as_of": "2026-01-01T14:00:00Z"}
        limited = self.exchange([call(1, "tallystick_settlement_preview", too_many)])[0]
        self.assertTrue(limited["result"]["isError"])
        self.assertIn("256", limited["result"]["structuredContent"]["message"])


if __name__ == "__main__":
    unittest.main()
