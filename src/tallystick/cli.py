"""Command-line entry points and a loopback-only, read-only report server."""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__
from .compiler import MarketCompiler
from .crypto import SigningKey
from .dashboard import render_dashboard
from .fixtures import configuration, scenario
from .gateway import BatchSimulator
from .pricing import whitepaper_example
from .rights import RightsRegistry
from .validation import InputError, loads, require
from .workbench import run_replay, verify_dispute


def read_json(path):
    with Path(path).open("rb") as handle:
        return loads(handle.read(1_048_577))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")


def batch_example():
    """Exercise synthetic acceptance without creating orders or financial balances."""
    sim = BatchSimulator(window_ms=250, required_sources=["demo-official"],
                         max_market_units=1000, max_family_units=600)
    sim.register_mandate({"mandate_id": "demo-mandate", "agent_id": "demo-agent",
                         "model_family": "demo-family", "market_ids": ["corners"],
                         "max_stake_units": 200, "budget_units": 500, "valid_from_ms": 0,
                         "valid_until_ms": 2000, "revoked": False, "consumer": False})
    receipts = [sim.submit({"request_id": request_id, "market_id": "corners",
                            "mandate_id": "demo-mandate", "stake_units": 100,
                            "min_decimal_odds": "2.40"}, received_at_ms=arrival)
                for request_id, arrival in (("request-a", 100), ("request-b", 110))]
    pending = sim.close_batch(250, {"corners": "2.53"}, now_ms=250)
    sim.advance_watermark("demo-official", event_time_ms=250)
    closed = sim.close_batch(250, {"corners": "2.53"}, now_ms=725)
    incident = sim.observe_late("demo-official", event_time_ms=200)
    return {"synthetic": True, "scope": "in-memory acceptance using fictional units and declared watermarks",
            "submission_receipts": receipts, "before_watermark": pending,
            "after_watermark": closed, "late_input_incident": incident,
            "exposure": sim.exposure()}


def report(result):
    verification = verify_dispute(result["bundle"], result["public_key"])
    return {"version": __version__, "synthetic": True, "market_name": result["certificate"]["payload"]["market"]["name"],
            "stages": result["stages"], "entry_count": result["entry_count"],
            "facts": [e["payload"] for e in result["bundle"]["body"]["entries"] if e["kind"] == "fact"],
            "public_key": result["public_key"], "root_hash": result["bundle"]["body"]["checkpoint"]["root_hash"],
            "verification": verification, "pricing": whitepaper_example()}


def build_report(inputs, output):
    dest = Path(output).resolve()
    require(not dest.exists(), "Output path already exists; choose a new directory", "OUTPUT_EXISTS")
    dest.mkdir(parents=True, exist_ok=False)
    try:
        result = run_replay(inputs, database=dest / "ledger.sqlite")
        summary = report(result)
        require(summary["verification"]["valid"], "Generated evidence failed verification")
        write_json(dest / "dispute.json", result["bundle"])
        write_json(dest / "summary.json", summary)
        write_json(dest / "scenario.json", inputs)
        (dest / "public-key.txt").write_text(result["public_key"] + "\n", encoding="ascii")
        (dest / "index.html").write_text(render_dashboard(summary), encoding="utf-8")
        return {"output": str(dest), "synthetic": True, "entry_count": result["entry_count"],
                "verification": summary["verification"], "stages": result["stages"]}
    except Exception:
        # Preserve partial output for diagnosis; it is not labelled as a completed run.
        (dest / "INCOMPLETE.txt").write_text("This run did not complete. Inspect the reported error.\n")
        raise


def create_report_server(directory, port=0):
    """Build a loopback server from a verified bundle, without starting its loop."""
    folder = Path(directory).resolve()
    require(not (folder / "INCOMPLETE.txt").exists(), "Cannot serve an incomplete run")
    summary = read_json(folder / "summary.json")
    require(type(summary) is dict and type(summary.get("stages")) is list,
            "Invalid report summary")
    require(all(type(stage) is dict and type(stage.get("name")) is str
                and len(stage["name"]) <= 200 for stage in summary["stages"]),
            "Invalid report stage labels")
    bundle = read_json(folder / "dispute.json")
    key = (folder / "public-key.txt").read_text(encoding="ascii").strip()
    verification = verify_dispute(bundle, key)
    require(verification["valid"], "Evidence bundle failed verification; refusing to serve it")
    # Rebuild the displayed records from verified content, not from editable summary claims.
    body = bundle["body"]
    stages = []
    for entry in body["entries"]:
        if entry["kind"] == "settlement-decision":
            matching = next((s for s in summary.get("stages", []) if s.get("sequence") == entry["sequence"]), {})
            stages.append({"name": matching.get("name", "Recorded decision"), "as_of": entry["payload"]["as_of"],
                           "sequence": entry["sequence"], **entry["payload"]["result"]})
    safe = {"version": __version__, "synthetic": True, "market_name": body["market"]["name"],
            "stages": stages, "entry_count": len(body["entries"]),
            "facts": [e["payload"] for e in body["entries"] if e["kind"] == "fact"],
            "public_key": key, "root_hash": body["checkpoint"]["root_hash"],
            "verification": verification, "pricing": whitepaper_example()}
    routes = {
        "/": ("text/html; charset=utf-8", render_dashboard(safe).encode()),
        "/index.html": ("text/html; charset=utf-8", render_dashboard(safe).encode()),
        "/api/summary": ("application/json", json.dumps(safe).encode()),
        "/api/verify": ("application/json", json.dumps(verification).encode()),
        "/dispute.json": ("application/json", json.dumps(bundle, indent=2).encode()),
        "/public-key.txt": ("text/plain", (key + "\n").encode()),
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            # Fixed routes prevent local-file exposure. The process binds only to loopback.
            if self.path not in routes:
                self.send_error(404)
                return
            mime, content = routes[self.path]
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, fmt, *args):
            print(fmt % args, file=sys.stderr)

    require(type(port) is int and 0 <= port <= 65535, "Invalid port")
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve_report(directory, port):
    server = create_report_server(directory, port)
    print(f"Tallystick synthetic review dashboard: http://127.0.0.1:{server.server_port}", file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tallystick", description="Synthetic sports-data settlement research workbench")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Replay the fictional example and export a verified report")
    demo.add_argument("--output", required=True)
    replay = commands.add_parser("replay", help="Replay a supplied synthetic JSON scenario")
    replay.add_argument("scenario")
    replay.add_argument("--output", required=True)
    verify = commands.add_parser("verify", help="Verify a bundle against a separately trusted recorder key")
    verify.add_argument("bundle")
    verify.add_argument("--public-key-file", required=True)
    compile_cmd = commands.add_parser("compile", help="Check a market against synthetic permissions and policy")
    compile_cmd.add_argument("market")
    compile_cmd.add_argument("--config", required=True)
    compile_cmd.add_argument("--as-of", required=True)
    commands.add_parser("price-example", help="Recompute the whitepaper's mathematical example")
    commands.add_parser("batch-example", help="Run the synthetic watermark and batch-acceptance example")
    commands.add_parser("example-scenario", help="Print the fictional replay scenario")
    commands.add_parser("mcp", help="Run the bounded read-only MCP stdio interface")
    serve = commands.add_parser("serve", help="Serve an existing verified report on localhost")
    serve.add_argument("--directory", required=True)
    serve.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            result = build_report(scenario(), args.output)
        elif args.command == "replay":
            result = build_report(read_json(args.scenario), args.output)
        elif args.command == "verify":
            result = verify_dispute(read_json(args.bundle), Path(args.public_key_file).read_text(encoding="ascii").strip())
            print(json.dumps(result, indent=2))
            return 0 if result["valid"] else 1
        elif args.command == "compile":
            config = read_json(args.config)
            signer = SigningKey.generate()
            compiler = MarketCompiler(RightsRegistry(config["licences"], config["sources"]), config["rulepacks"], signer)
            result = compiler.compile(read_json(args.market), args.as_of)
            result["recorder_public_key"] = signer.public_key_hex
            print(json.dumps(result, indent=2))
            return 0 if result["accepted"] else 2
        elif args.command == "price-example":
            result = whitepaper_example()
        elif args.command == "batch-example":
            result = batch_example()
        elif args.command == "example-scenario":
            result = scenario()
        elif args.command == "mcp":
            from .mcp import serve_stdio
            return serve_stdio()
        elif args.command == "serve":
            require(0 <= args.port <= 65535, "Invalid port")
            serve_report(args.directory, args.port)
            return 0
        print(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"error": getattr(error, "code", "INVALID_INPUT"), "message": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
