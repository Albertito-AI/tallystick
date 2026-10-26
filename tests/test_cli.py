"""Exercise installed entry points, report safety and the actual review routes."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import http.client
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

from tallystick.cli import build_report, create_report_server, main
from tallystick.crypto import SigningKey
from tallystick.dashboard import render_dashboard
from tallystick.fixtures import configuration, scenario


class CliTests(unittest.TestCase):
    def invoke(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(map(str, args)))
        return code, out.getvalue(), err.getvalue()

    def test_real_process_demo_verify_and_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "report"
            run = subprocess.run([sys.executable, "-m", "tallystick", "demo", "--output", str(dest)],
                                 capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr)
            summary = json.loads(run.stdout)
            self.assertTrue(summary["verification"]["valid"])
            self.assertEqual([s["outcome"] for s in summary["stages"]],
                             [None, None, "over", None, "over", "under"])
            self.assertEqual(summary["stages"][-1]["count"], 4)
            verify = [sys.executable, "-m", "tallystick", "verify", str(dest / "dispute.json"),
                      "--public-key-file", str(dest / "public-key.txt")]
            valid = subprocess.run(verify, capture_output=True, text=True, timeout=30)
            self.assertEqual(valid.returncode, 0, valid.stderr)
            bundle = json.loads((dest / "dispute.json").read_text())
            bundle["body"]["decision"]["count"] = 99
            (dest / "dispute.json").write_text(json.dumps(bundle), encoding="utf-8")
            invalid = subprocess.run(verify, capture_output=True, text=True, timeout=30)
            self.assertEqual(invalid.returncode, 1)
            self.assertFalse(json.loads(invalid.stdout)["valid"])

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "existing"
            dest.mkdir()
            marker = dest / "keep.txt"
            marker.write_text("original record")
            code, _, err = self.invoke("demo", "--output", dest)
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(err)["error"], "OUTPUT_EXISTS")
            self.assertEqual(marker.read_text(), "original record")
            self.assertEqual([p.name for p in dest.iterdir()], ["keep.txt"])

    def test_json_framing_and_failed_run_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.json"
            for text in ('{"synthetic":true,"synthetic":false}', '{"x":1e999}', '[1,2,3]'):
                source.write_text(text)
                code, _, err = self.invoke("replay", source, "--output", root / "report")
                self.assertEqual(code, 2)
                self.assertIsInstance(json.loads(err)["message"], str)
            # Array input reaches report creation; diagnostic output is explicitly incomplete.
            self.assertTrue((root / "report" / "INCOMPLETE.txt").exists())
            with self.assertRaises(ValueError):
                create_report_server(root / "report")

    def test_consumer_compilation_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = configuration()
            market = deepcopy(config.pop("market"))
            market["consumer"] = True
            (root / "config.json").write_text(json.dumps(config))
            (root / "market.json").write_text(json.dumps(market))
            code, out, _ = self.invoke("compile", root / "market.json", "--config", root / "config.json",
                                       "--as-of", "2026-01-01T12:00:00Z")
            self.assertEqual(code, 2)
            self.assertFalse(json.loads(out)["accepted"])

    def test_dashboard_script_parses_and_untrusted_text_stays_data(self):
        node = os.environ.get("CODEX_PRIMARY_RUNTIME_NODE") or shutil.which("node")
        if not node:
            self.fail("Node.js is required for dashboard and independent conformance checks")
        hostile = '</script><script>globalThis.injected=true</script>&__DATA____TITLE__'
        summary = {"market_name": hostile, "stages": [{"name": hostile}]}
        page = render_dashboard(summary)
        self.assertNotIn("<script>globalThis.injected", page)
        data = re.search(r'<script type="application/json" id="data">(.*?)</script>', page, re.S)
        self.assertIsNotNone(data)
        self.assertEqual(json.loads(data[1]), summary)
        scripts = re.findall(r'<script>(.*?)</script>', page, re.S)
        self.assertEqual(len(scripts), 1)
        check = subprocess.run([node, "-e", "new(require('node:vm').Script)(require('node:fs').readFileSync(0,'utf8'))"],
                               input=scripts[0], text=True, encoding="utf-8", capture_output=True, timeout=10)
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_batch_example_is_gated_and_retains_accepted_exposure(self):
        code, out, err = self.invoke("batch-example")
        self.assertEqual(code, 0, err)
        data = json.loads(out)
        self.assertTrue(data["synthetic"])
        self.assertEqual(data["before_watermark"]["status"], "PENDING")
        self.assertEqual(data["after_watermark"]["status"], "CLOSED")
        self.assertEqual([d["decimal_odds"] for d in data["after_watermark"]["decisions"]], ["2.53", "2.53"])
        self.assertEqual(data["exposure"]["market_units"]["corners"], 200)

    def test_report_server_verifies_input_and_exposes_only_fixed_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "report"
            build_report(scenario(), folder)
            summary = json.loads((folder / "summary.json").read_text())
            summary["verification"] = {"valid": False}
            summary["stages"][-1]["outcome"] = "over"
            (folder / "summary.json").write_text(json.dumps(summary))
            server = create_report_server(folder)
            self.assertEqual(server.server_address[0], "127.0.0.1")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            try:
                connection.request("GET", "/api/summary")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")
                data = json.loads(response.read())
                self.assertTrue(data["verification"]["valid"])
                self.assertEqual(data["stages"][-1]["outcome"], "under")
                for route in ("/", "/api/verify", "/dispute.json", "/public-key.txt"):
                    connection.request("GET", route)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertIn("frame-ancestors 'none'", response.getheader("Content-Security-Policy"))
                    response.read()
                for route in ("/../ledger.sqlite", "/ledger.sqlite", "/scenario.json", "/?file=../../etc/passwd"):
                    connection.request("GET", route)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 404)
                    response.read()
            finally:
                connection.close()
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()
            (folder / "public-key.txt").write_text(SigningKey.generate().public_key_hex)
            with self.assertRaises(ValueError):
                create_report_server(folder)


if __name__ == "__main__":
    unittest.main()
