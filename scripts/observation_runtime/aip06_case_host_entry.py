"""Case-host child entry through the original guarded inherited bootstrap.

This entry can inspect a private handoff but cannot execute case workloads.
It must never be invoked as an ordinary subprocess or financial worker.
"""

import ntpath

from app.services.paper_financial_replay import strict
from scripts.observation_runtime.aip06_harness import BASE

HOST_ENTRY = ntpath.join(ntpath.dirname(ntpath.dirname(BASE)), 'scripts',
                         'observation_runtime', 'aip06_case_host_entry.py')
from scripts.observation_runtime.aip06_fixture_guard import require_fixture
from scripts.observation_runtime.aip06_harness import need
from scripts.observation_runtime.aip06_host_preflight import inspect


def inspect_inherited_handoff(*, maximum_bytes=65536, timeout=6):
    need(type(maximum_bytes) is int and 0 < maximum_bytes <= 65536
         and type(timeout) is int and 0 < timeout <= 6,
         'BOUNDED_CASE_HOST_HANDOFF_READ_REQUIRED')
    guard = require_fixture('independent-case-host-preflight')
    descriptor = guard.processes.runtime.descriptor
    argv = descriptor.get('argv')
    need(type(argv) in (tuple, list) and len(argv) == 3
         and argv[1] == '-B' and argv[2] == HOST_ENTRY
         and descriptor.get('targets', {}).get('case_host') == HOST_ENTRY
         and HOST_ENTRY in descriptor.get('source_pins', {}),
         'PINNED_INHERITED_CASE_HOST_COMMAND_REQUIRED')
    # The handoff verifier is execution-critical. Check the retained native
    # source pin before any private INPUT frame can be consumed.
    verifier = ntpath.join(ntpath.dirname(HOST_ENTRY), 'aip06_host_preflight.py')
    need(verifier in descriptor['source_pins'],
         'PINNED_CASE_HOST_PREFLIGHT_SOURCE_REQUIRED')
    guard.processes.runtime.verify_source(verifier)
    # ChildServices owns the authenticated input stream; FixtureGuard does not.
    packet = strict(guard.processes.read_input(
        maximum_bytes=maximum_bytes, timeout=timeout).decode('utf-8'))
    return inspect(packet, descriptor, guard)


def main():
    # Executed only after the original child bootstrap installs its guard.
    # A successful data-only handoff is still not native execution authority.
    inspect_inherited_handoff()
    raise ValueError('NATIVE_CASE_HOST_EXECUTION_NOT_YET_QUALIFIED')


if __name__ == '__main__':
    main()
