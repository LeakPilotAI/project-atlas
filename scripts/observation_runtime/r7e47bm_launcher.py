"""R7E47BM: guarded offline observation subprocess.

This is a Python-level guard, not an OS security sandbox.
No real network or production execution is authorized.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

CHILD = """
import builtins
import json
import runpy
import socket
import subprocess
import sys

blocked = []

def refuse(label):
    def inner(*args, **kwargs):
        blocked.append(label)
        raise RuntimeError("Prohibited operation: " + label)
    return inner

socket.socket.connect = refuse("socket.connect")
socket.socket.connect_ex = refuse("socket.connect_ex")
socket.create_connection = refuse("socket.create_connection")
subprocess.Popen = refuse("subprocess.Popen")

original_import = builtins.__import__

def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    prohibited = ("app.main", "app.trading", "app.discord", "app.scanners")
    if any(name == item or name.startswith(item + ".") for item in prohibited):
        blocked.append("import:" + name)
        raise RuntimeError("Prohibited import: " + name)
    return original_import(name, globals, locals, fromlist, level)

builtins.__import__ = guarded_import

sys.argv = ["observation_entry", "--synthetic-once"]

try:
    runpy.run_module(
        "scripts.observation_runtime.observation_entry",
        run_name="__main__",
    )
except SystemExit as exc:
    code = exc.code
    if code not in (None, 0):
        raise RuntimeError("Observation entry failed: " + repr(code))

if blocked:
    raise RuntimeError("Prohibited operations attempted: " + repr(blocked))

print("R7E47BM_GUARDS_CLEAR", file=sys.stderr)
"""

def run_offline():
    if not (BACKEND / "app/core/durable_io.py").is_file():
        raise RuntimeError("Required backend dependency missing")

    command = [
        sys.executable, "-I", "-S", "-c",
        (
            "import sys; "
            f"sys.path.insert(0, {str(BACKEND)!r}); "
            f"sys.path.insert(0, {str(ROOT)!r}); "
            + CHILD
        ),
    ]

    result = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError("Guarded child failed: " + result.stderr[-1500:])

    if result.stderr.strip() != "R7E47BM_GUARDS_CLEAR":
        raise RuntimeError("Guard confirmation missing or unexpected stderr")

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError("Unexpected observation output")

    report = json.loads(lines[0])

    expected = {
        "mode": "SYNTHETIC_OFFLINE",
        "profile": "OBSERVATION_ONLY",
        "network_enabled": False,
        "trading_enabled": False,
        "runtime_alive": False,
        "session_closed": True,
        "final_event": "GRACEFUL_SHUTDOWN",
        "observations": 1,
        "budget_remaining": 0,
    }

    if any(report.get(key) != value for key, value in expected.items()):
        raise RuntimeError("Observation lifecycle contract failed")

    return report

if __name__ == "__main__":
    print(json.dumps(run_offline(), sort_keys=True))
