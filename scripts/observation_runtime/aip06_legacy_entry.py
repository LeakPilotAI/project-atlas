"""Guarded disposable legacy probe target. Import is inert; no raw subprocess."""

import argparse
import json

from app.services.paper_financial_replay import digest, strict
from scripts.observation_runtime.aip06_fixture_guard import require_fixture
from scripts.observation_runtime.aip06_harness import SCOPE_HASH, need
from scripts.observation_runtime.aip06_legacy_probe import CASES


def main(argv=None):
    guard = require_fixture("guarded-legacy-probe-entry")
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--nonce", required=True)
    args = parser.parse_args(argv)
    binding = guard.resources.channel.binding
    current = binding["child"]
    need(
        args.nonce == binding["nonce"] and digest(current) == guard.owner,
        "PROBE_CURRENT_PRIVATE_LAUNCH_IDENTITY",
    )
    need(guard.launch_role == ('acceptance_worker' if args.case == 'direct-worker'
                              else 'acceptance_supervisor'), 'PROBE_FORMAL_ROLE_REQUIRED')
    with guard.watchdog(seconds=45 if args.case=='direct-unexpected' else 6, exit_code=71):
        request=None;challenge=None
        if args.case=='direct-unexpected':
            request=strict(guard.read_input(maximum_bytes=65536,timeout=6).decode())
            need(request=={'schema':'AIP06_PROBE_CLOSE_V1','scope':SCOPE_HASH,
                           'case':args.case,'nonce':args.nonce},'PROBE_PRIVATE_CLOSE_CORRELATION')
            challenge=guard.processes.run_unexpected_challenge()
        print(
            json.dumps(
                {
                    "schema": "AIP06_LEGACY_READY_V1",
                    "scope": SCOPE_HASH,
                    "case": args.case,
                    "nonce": args.nonce,
                    "pid": current["pid"],
                    "created": current["created"],
                    "image": current["image"],
                    "role": guard.launch_role,
                }
            ),
            flush=True,
        )
        if challenge is not None:print(json.dumps(challenge),flush=True)
        if request is None:request = strict(guard.read_input(maximum_bytes=65536, timeout=6).decode())
        need(
            request
            == {
                "schema": "AIP06_PROBE_CLOSE_V1",
                "scope": SCOPE_HASH,
                "case": args.case,
                "nonce": args.nonce,
            },
            "PROBE_PRIVATE_CLOSE_CORRELATION",
        )
    return {"exit_code": 0, "native_acceptance": False}


if __name__ == "__main__":
    main()
