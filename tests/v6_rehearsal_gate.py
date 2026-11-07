"""Synthetic static gate only. Cannot authorize an installed session."""

import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).parent
if (
    len(sys.argv) != 4
    or sys.argv[1] != "--verify-only"
    or not root.name.startswith("qd-v6-integrated-rehearsal-")
):
    raise SystemExit("DISPOSABLE_REHEARSAL_GATE_ONLY")
sys.stdout = (root / "gate-stdout.log").open("x", buffering=1)
sys.stderr = (root / "gate-stderr.log").open("x", buffering=1)
scope = json.loads((root / "fixture-scope.json").read_bytes())
assert scope["domain"] == "DISPOSABLE_INTEGRATED_ONLY"
assert (
    hashlib.sha256(
        json.dumps(scope, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    == sys.argv[2]
)
assert all(
    not image["path"].casefold().startswith("d:\\atlasruntime")
    for image in scope["ownership"]["images"].values()
)
manifest = json.loads((root / "fixture-source-manifest.json").read_bytes())
for row in manifest:
    p = Path(row["path"])
    assert p.is_relative_to(Path(r"D:\Work\Project Atlas")) and not any(
        x.is_symlink() or x.is_junction() for x in (p, *p.parents)
    )
    data = p.read_bytes()
    assert (
        len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"]
    )
print("DISPOSABLE_SOURCE_AND_OWNER_GATE_NO_OPERATIONAL_AUTHORITY", flush=True)
