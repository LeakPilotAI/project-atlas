"""Bounded existing offline suites in exclusive repository-owned scratch space.

No production imports, runtime authorization, provider connections, permission
changes, automatic elevation, or altered test assertions. Native OS restrictions
remain test failures. Retain all artifacts, including failed/unfinished runs.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=("javascript", "provider"))
    args = parser.parse_args()
    base = ROOT / "logs" / "diagnostics" / "offline-readiness-checks"
    # Check existing namespace components before creating disposable destinations.
    for component in (ROOT, ROOT / "logs", ROOT / "logs/diagnostics", base):
        if component.is_symlink() or component.is_junction():
            raise ValueError("Linked test scratch root refused")
    base.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix=args.suite + "-", dir=base))
    scratch = run / "scratch"
    scratch.mkdir()
    env = dict(os.environ, TEMP=str(scratch), TMP=str(scratch), TMPDIR=str(scratch))
    if args.suite == "javascript":
        files = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "frontend/offline").rglob("*")
                       if p.is_file() and ".test." in p.name and p.suffix in (".js", ".cjs", ".mjs"))
        command = ["node", "--test", *files]
    else:
        env.update(PYTHONPATH="backend;tests", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
        command = [sys.executable, "-m", "pytest", "-q", "-p", "pytest_asyncio.plugin",
                   "tests/test_r7e46r_provider_dispatch.py", "--basetemp=" + str(run / "pytest")]
    evidence = {"suite": args.suite, "started_utc": datetime.now(UTC).isoformat(),
                "command": command, "scratch": str(scratch), "production_authorized": False,
                "outcome": "IN_PROGRESS"}
    receipt = run / "result.json"
    receipt.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(str(run), flush=True)
    with (run / "output.txt").open("w", encoding="utf-8") as output:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT)
        evidence["pid"] = process.pid
        receipt.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        try:
            result = process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            # Do not assert that an interrupted observer stopped a test worker.
            evidence.update(outcome="UNKNOWN", reason="TEST_DEADLINE_EXPIRED", returncode=None)
            receipt.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            raise
    evidence.update(outcome="PASS" if result == 0 else "FAILED",
                    returncode=result, finished_utc=datetime.now(UTC).isoformat())
    receipt.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
