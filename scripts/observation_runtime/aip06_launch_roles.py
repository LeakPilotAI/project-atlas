"""Exact legacy launch-role mapping; no launch or execution authority."""

import ntpath

from scripts.observation_runtime.aip06_harness import BASE, need


def launch_role(argv, targets):
    ENTRY = ntpath.join(ntpath.dirname(ntpath.dirname(BASE)), 'scripts', 'observation_runtime', 'aip06_acceptance_controller.py')
    if len(argv) >= 3 and argv[2] == ENTRY:
        from scripts.observation_runtime.aip06_controller_contract import controller_argv
        controller_argv(argv, targets)
        return 'acceptance_supervisor'
    from scripts.observation_runtime.aip06_case_host_entry import HOST_ENTRY
    if len(argv) >= 3 and argv[2] == HOST_ENTRY:
        need(len(argv) == 3 and argv[1] == '-B'
             and targets.get('case_host') == HOST_ENTRY,
             'EXACT_CASE_HOST_INHERITED_LAUNCH_REQUIRED')
        # A case host is a guarded child, never a supervisor or authorization.
        return 'acceptance_worker'
    legacy = ntpath.join(
        ntpath.dirname(ntpath.dirname(BASE)),
        "scripts",
        "observation_runtime",
        "aip06_legacy_entry.py",
    )
    if len(argv) >= 3 and argv[2] == legacy:
        need(
            targets.get("query") == legacy
            and len(argv) == 7
            and argv[1] == "-B"
            and argv[3] == "--case"
            and argv[5] == "--nonce"
            and type(argv[6]) is str
            and len(argv[6]) == 32
            and set(argv[6]) <= set("0123456789abcdef")
            and argv[4] in ("direct-worker", "direct-supervisor", "direct-unexpected"),
            "EXACT_LEGACY_ROLE_COMMAND_REQUIRED",
        )
        return (
            "acceptance_supervisor"
            if argv[4] != "direct-worker"
            else "acceptance_worker"
        )
    return "acceptance_worker"
