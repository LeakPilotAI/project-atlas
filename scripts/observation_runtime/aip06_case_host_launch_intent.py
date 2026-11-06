"""Owner-side case-host launch preflight; never creates or authorizes a process."""

from scripts.observation_runtime.aip06_case_host_entry import HOST_ENTRY
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
         and controller.profile['source_pins'] == plan['source_pins']
         and controller.profile['targets'].get('case_host') == HOST_ENTRY,
         'PINNED_NATIVE_CASE_HOST_TARGET_REQUIRED')
    need(type(plan.get('executable')) is str and plan['executable'],
         'ORIGINAL_CASE_HOST_INTERPRETER_REQUIRED')
    handoff = case.physical_host_handoff(reservation, deadline_ns=deadline_ns)
    return {'schema': 'AIP06_CASE_HOST_LAUNCH_INTENT_V1',
            'argv': (plan['executable'], '-B', HOST_ENTRY),
            'handoff': handoff, 'native_acceptance': False,
            'execution_authorized': False}
