"""Run the two bounded models with the pinned official TLA+ tool.

The tool is an external development dependency, never a runtime dependency.
Download it from the documented official release; this runner makes no network
requests and verifies its content before execution.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

TLA_TOOLS_SHA256 = "936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    jar = args.jar.resolve(strict=True)
    if sha256(jar) != TLA_TOOLS_SHA256:
        parser.error("tool checksum differs from the reviewed TLA+ 1.7.4 release")
    folder = Path(__file__).resolve().parent
    models = []
    for model in ("Settlement", "Acceptance"):
        with tempfile.TemporaryDirectory(prefix="tallystick-tlc-") as tmp:
            command = ["java", "-Xmx512m", "-XX:+UseParallelGC", "-cp", str(jar),
                       "tlc2.TLC", "-workers", "1", "-cleanup", "-metadir", tmp,
                       "-config", model + ".cfg", model + ".tla"]
            completed = subprocess.run(command, cwd=folder, capture_output=True,
                                       text=True, check=False, timeout=60)
            output = completed.stdout + completed.stderr
        match = re.search(r"(\d+) states generated, (\d+) distinct states found", output)
        passed = completed.returncode == 0 and "Model checking completed. No error has been found." in output
        record = {
            "model": model,
            "source_sha256": sha256(folder / (model + ".tla")),
            "config_sha256": sha256(folder / (model + ".cfg")),
            "exit_code": completed.returncode,
            "passed": passed,
            "generated_states": int(match[1]) if match else None,
            "distinct_states": int(match[2]) if match else None,
            "output": output,
        }
        models.append(record)
        print(f"{model}: {'PASS' if passed else 'FAIL'}; "
              f"{record['distinct_states']} distinct states")
        if not passed:
            print(output)
    receipt = {
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tool_release": "tlaplus/tlaplus v1.7.4",
        "tool_sha256": TLA_TOOLS_SHA256,
        "scope": "Bounded abstract invariant checks; no implementation refinement or liveness proof",
        "models": models,
    }
    if args.output:
        args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return 0 if all(model["passed"] for model in models) else 1


if __name__ == "__main__":
    raise SystemExit(main())
