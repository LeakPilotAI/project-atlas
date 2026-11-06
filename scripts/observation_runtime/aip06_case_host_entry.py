"""Case-host child entry through the original guarded inherited bootstrap.

This entry can inspect a private handoff but cannot execute case workloads.
It must never be invoked as an ordinary subprocess or financial worker.
"""

from app.services.paper_financial_replay import strict
from scripts.observation_runtime.aip06_fixture_guard import require_fixture
from scripts.observation_runtime.aip06_harness import need
from scripts.observation_runtime.aip06_host_preflight import inspect


def inspect_inherited_handoff(*, maximum_bytes=65536, timeout=6):
    need(type(maximum_bytes) is int and 0 < maximum_bytes <= 65536
         and type(timeout) is int and 0 < timeout <= 6,
         'BOUNDED_CASE_HOST_HANDOFF_READ_REQUIRED')
    guard = require_fixture('independent-case-host-preflight')
    descriptor = guard.processes.runtime.descriptor
    packet = strict(guard.read_input(maximum_bytes=maximum_bytes, timeout=timeout).decode('utf-8'))
    return inspect(packet, descriptor, guard)


def main():
    # The native owner/Job/reader/cleanup proofs are not yet assembled.
    raise ValueError('NATIVE_CASE_HOST_EXECUTION_NOT_YET_QUALIFIED')


if __name__ == '__main__':
    main()
