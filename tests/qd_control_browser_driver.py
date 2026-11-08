"""Retain exact disposable host ownership while genuine browser tests run."""

import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

from test_quality_dips_control_stop_http import REPO, owner_module


def main():
    parent = Path(sys.argv[1]).resolve()
    if parent.parent != REPO / "logs/diagnostics" or not parent.name.startswith(
        "qd-runtime-wiring-"
    ):
        raise ValueError("EXPLICIT_TEST_EVIDENCE_ROOT_REQUIRED")
    root = REPO / "logs/diagnostics" / ("qd-http-browser-runtime-" + uuid.uuid4().hex)
    root.mkdir()
    raw = json.dumps(
        {
            "schema": "QD_CONTROL_DISPOSABLE_V1",
            "damage": os.environ.get("QD_BROWSER_DAMAGE", "none"),
            "partial": False,
        }
    ).encode()
    (root / "fixture.json").write_bytes(raw)
    owner = owner_module.OwnedHost(
        root, hashlib.sha256(raw).hexdigest(), control_fixture=True
    )
    (parent / "browser-ready.json").write_text(
        json.dumps({"root": str(root), "ready": owner.ready})
    )
    print("DISPOSABLE_BROWSER_READY " + owner.ready["url"], flush=True)
    try:
        sys.stdin.readline()
    finally:
        owner.close(owner.identity)
        (parent / "browser-owned-exit.json").write_text(
            json.dumps({"exited": True, "returncode": owner.process.returncode})
        )


if __name__ == "__main__":
    main()
