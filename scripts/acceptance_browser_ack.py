"""Record a completed browser-test witness, not startup or financial authority."""

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.observation_runtime.installed_acceptance_handoff import (
    SIGNOFFS,
    submit_browser_ack,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--record-genuine-browser-check", action="store_true", required=True
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--cycle", type=int, choices=(1, 2), required=True)
    for name in SIGNOFFS:
        parser.add_argument(
            "--" + name.replace("_", "-"), action="store_true", required=True
        )
    args = parser.parse_args()
    root = args.root.absolute()
    if not root.resolve().is_relative_to((REPO / "logs/diagnostics").resolve()) or any(
        p.is_symlink() or p.is_junction() for p in [root, *root.parents]
    ):
        raise ValueError("EXACT_CONFINED_ACK_EVIDENCE_ROOT_REQUIRED")
    ticket = json.loads(
        (root / f"cycle-{args.cycle}-browser-request.json").read_bytes()
    )
    if ticket["domain"] == "WINDOWS_LOCAL":
        claim = json.loads((root / "single-use-claim.json").read_bytes())
        if time.perf_counter_ns() >= claim["deadline_ns"]:
            raise ValueError("ACCEPTANCE_SESSION_EXPIRED")
    # The external driver must actually perform the UI checks and tab close.
    # Publish first; stdout/reporting cannot delay the acknowledgement file.
    packet = submit_browser_ack(root, ticket, {k: getattr(args, k) for k in SIGNOFFS})
    print(
        json.dumps(
            {
                "submitted": True,
                "cycle": args.cycle,
                "observed_ns": packet["observed_ns"],
                "consumer_acceptance": "REQUIRES_TIMELY_BOUND_RECEIPT",
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
