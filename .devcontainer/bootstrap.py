"""Prepare an isolated development environment; no service or paid resource is created."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, "-m", "venv", ".venv"], cwd=root, check=True)
python = root / ".venv" / "bin" / "python"
subprocess.run([str(python), "-m", "pip", "install", "-e", "."], cwd=root, check=True)
print("Ready. Run .venv/bin/python -m tallystick demo --output run/demo")
print("Then run .venv/bin/python -m tallystick serve --directory run/demo --port 8765")
