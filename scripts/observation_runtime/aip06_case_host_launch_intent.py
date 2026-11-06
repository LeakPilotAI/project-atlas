"""Owner-side case-host launch preflight; never creates or authorizes a process."""

import ntpath
from scripts.observation_runtime.aip06_case_host_entry import HOST_ENTRY

PREFLIGHT = ntpath.join(ntpath.dirname(HOST_ENTRY), 'aip06_host_preflight.py')
from scripts.observation_runtime.aip06_harness import need
from scripts.observation_runtime.aip06_scoped_context import CaseContext


def inspect_launch_intent(case, reservation, *, deadline_ns):
    """Verify retained owner/reservation and pinned target before launch assembly.

    No synthetic Job, Stop, or process evidence is accepted here. The returned
    data-only intent cannot be used as a process-creation capability.
    """
    need(type(case) is CaseContext, 'ORIGINAL_CASE_CONTEXT_FOR_HOST_LAUNCH')
    case.verify(deadline_ns=deadline_ns)
    need(case.factory.pending is case and reservation == case.reservation
         and type(reservation) is dict and reservation.get('held') is True
         and reservation.get('stop_capacity_reserved') is True,
         'ORIGINAL_HELD_CASE_RESERVATION_FOR_HOST_LAUNCH')
    controller = case.controller
    guard = case.guard
    need(guard.processes is controller.process_port
         and case.factory.guard is guard and case.factory.controller is controller,
         'ORIGINAL_CONTROLLER_OWNER_FOR_HOST_LAUNCH')
    plan = case.factory.plan
    need(type(plan) is dict and type(plan.get('source_pins')) is dict
         and HOST_ENTRY in plan['source_pins']
         and PREFLIGHT in plan['source_pins']
         and controller.profile['source_pins'] == plan['source_pins']
         and controller.profile['targets'].get('case_host') == HOST_ENTRY,
         'PINNED_NATIVE_CASE_HOST_TARGET_REQUIRED')
    need(type(plan.get('executable')) is str and plan['executable'],
         'ORIGINAL_CASE_HOST_INTERPRETER_REQUIRED')
    # Pin membership is not a disk-integrity check. Reopen the two execution-
    # critical sources through the original charged native-handle verifier
    # before a guarded process can be allocated by the caller.
    for path in (HOST_ENTRY, PREFLIGHT):
        verified = controller.verify_source(path)
        need(type(verified) is dict and verified.get('path') == path
             and verified.get('sha256') == plan['source_pins'][path]
             and verified.get('closed') is True,
             'CLOSED_ORIGINAL_CASE_HOST_SOURCE_VERIFICATION_REQUIRED')
    handoff = case.physical_host_handoff(reservation, deadline_ns=deadline_ns)
    return {'schema': 'AIP06_CASE_HOST_LAUNCH_INTENT_V1',
            'argv': (plan['executable'], '-B', HOST_ENTRY),
            'handoff': handoff, 'native_acceptance': False,
            'execution_authorized': False}
