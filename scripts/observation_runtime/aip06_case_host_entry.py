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


def inspect(packet, descriptor, guard):
    # Import only after the inherited runtime verifies the pinned source.
    from scripts.observation_runtime.aip06_host_preflight import inspect as verified
    return verified(packet, descriptor, guard)


def inspect_inherited_handoff(*, maximum_bytes=65536, timeout=6):
    need(type(maximum_bytes) is int and 0 < maximum_bytes <= 65536
         and type(timeout) is int and 0 < timeout <= 6,
         'BOUNDED_CASE_HOST_HANDOFF_READ_REQUIRED')
    guard = require_fixture('independent-case-host-preflight')
    descriptor = guard.processes.runtime.descriptor
    argv = descriptor.get('argv')
    targets = descriptor.get('targets')
    pins = descriptor.get('source_pins')
    need(type(argv) in (tuple, list) and len(argv) == 3
         and argv[1] == '-B' and argv[2] == HOST_ENTRY
         and type(targets) is dict and targets.get('case_host') == HOST_ENTRY
         and type(pins) is dict and HOST_ENTRY in pins,
         'PINNED_INHERITED_CASE_HOST_COMMAND_REQUIRED')
    # The handoff verifier is execution-critical. Check the retained native
    # source pin before any private INPUT frame can be consumed.
    verifier = ntpath.join(ntpath.dirname(HOST_ENTRY), 'aip06_host_preflight.py')
    need(verifier in pins,
         'PINNED_CASE_HOST_PREFLIGHT_SOURCE_REQUIRED')
    need(all(type(pins[path]) is str and len(pins[path]) == 64
             and all(char in '0123456789abcdef' for char in pins[path])
             for path in (HOST_ENTRY, verifier)),
         'VALID_CASE_HOST_SOURCE_DIGESTS_REQUIRED')
    source = guard.processes.runtime.verify_source(verifier)
    need(type(source) is dict and source.get('path') == verifier
         and source.get('sha256') == descriptor['source_pins'][verifier]
         and source.get('closed') is True,
         'CLOSED_INHERITED_PREFLIGHT_SOURCE_RECEIPT_REQUIRED')
    # The host entry itself must also retain a closed source receipt.
    host_source = guard.processes.runtime.verify_source(HOST_ENTRY)
    need(type(host_source) is dict and host_source.get('path') == HOST_ENTRY
         and host_source.get('sha256') == descriptor['source_pins'][HOST_ENTRY]
         and host_source.get('closed') is True,
         'CLOSED_INHERITED_HOST_SOURCE_RECEIPT_REQUIRED')
    # ChildServices owns the authenticated input stream; FixtureGuard does not.
    raw = guard.processes.read_input(maximum_bytes=maximum_bytes, timeout=timeout)
    need(type(raw) is bytes and 0 < len(raw) <= maximum_bytes,
         'BOUNDED_ORIGINAL_CASE_HOST_INPUT_BYTES_REQUIRED')
    packet = strict(raw.decode('utf-8'))
    return inspect(packet, descriptor, guard)


def main():
    # Executed only after the original child bootstrap installs its guard.
    # A successful data-only handoff is still not native execution authority.
    inspect_inherited_handoff()
    raise ValueError('NATIVE_CASE_HOST_EXECUTION_NOT_YET_QUALIFIED')


if __name__ == '__main__':
    main()
