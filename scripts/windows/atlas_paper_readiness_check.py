"""Read-only desktop PAPER launch gate. Never grants trading authority."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
CHECKS = (
    ("desktop_start", "ATLAS.bat", "scripts/windows/Atlas-Launch.ps1"),
    ("desktop_stop", "ATLAS-STOP.bat", "scripts/windows/Atlas-Stop.ps1"),
)
BLOCK = "ATLAS_LEGACY_LIFECYCLE_BLOCKED"


def inspect(root=ROOT):
    results = {}
    for name, batch_name, script_name in CHECKS:
        batch = root / batch_name
        script = root / script_name
        try:
            batch_text = batch.read_text(encoding="utf-8-sig")
            script_text = script.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            results[name] = "UNVERIFIED"
            continue
        if script_name.replace("/", "\\").lower() not in batch_text.lower():
            results[name] = "UNVERIFIED"
        elif BLOCK in script_text:
            results[name] = "BLOCKED_LEGACY"
        else:
            # Absence of the guard is NOT proof of a certified implementation.
            results[name] = "UNVERIFIED"
    return {
        "schema": "ATLAS_PAPER_DESKTOP_READINESS_V1",
        "decision": "NO_GO",
        "paper_startup_authorized": False,
        "live_trading_authorized": False,
        "desktop": results,
        "reason": "INDEPENDENT_PAPER_SESSION_AND_STOP_ACCEPTANCE_REQUIRED",
    }


def main():
    print(json.dumps(inspect(), sort_keys=True))
    return 2


if __name__ == "__main__":
    sys.exit(main())
