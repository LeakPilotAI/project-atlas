"""Owner-side case-host launch preflight; never creates or authorizes a process."""

import ntpath
from scripts.observation_runtime.aip06_case_host_entry import HOST_ENTRY

PREFLIGHT = ntpath.join(ntpath.dirname(HOST_ENTRY), 'aip06_host_preflight.py')
from scripts.observation_runtime.aip06_harness import LIMITS, need
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


def verify_reserved_suspended_plan(guard, argv, plan):
    """Validate a case-host process plan before any ownership/handle allocation.

    The original guard still owns all actual suspended creation, Job checks,
    ledger reservations, Stop escrow and cleanup. This grants no authority.
    """
    port = getattr(guard.processes, 'port', guard.processes)
    case = getattr(port, 'scoped_case', None)
    need(type(case) is CaseContext and case.guard is guard
         and case.factory.pending is case and case.reservation is not None,
         'ORIGINAL_SCOPED_CASE_FOR_SUSPENDED_HOST_PLAN')
    executable = case.factory.plan['executable']
    need(tuple(argv) == (executable, '-B', HOST_ENTRY)
         and case.controller.profile['targets'].get('case_host') == HOST_ENTRY,
         'EXACT_SUSPENDED_CASE_HOST_COMMAND')
    need(type(plan) is dict and plan.get('parent_owner') == guard.owner
         and plan.get('name') == 'case_host'
         and type(plan.get('resource_kinds')) is tuple
         and {'job', 'thread', 'image', 'pipe'} <= set(plan['resource_kinds'])
         and plan.get('job_limits') == {
             'processes': LIMITS['processes'],
             'private_bytes': LIMITS['private_bytes'],
             'child_private_bytes': LIMITS['child_private_bytes'],
             'cpu_ns': LIMITS['cpu_ns'], 'kill_on_close': True},
         'ORIGINAL_OWNER_STOP_CAPACITY_AND_SUSPENDED_HOST_RESOURCES')
    request = plan.get('request')
    nonce = getattr(request, 'nonce', None)
    planned = getattr(port, 'plans', {}).get(nonce)
    need(type(nonce) is str and len(nonce) == 32
         and getattr(request, 'role', None) == 'acceptance_worker'
         and getattr(port, 'current_plan_nonce', None) == nonce
         and type(planned) is dict and planned.get('plan') is plan
         and planned.get('argv') == tuple(argv)
         and planned.get('parent') == port.resources.state['owners'][guard.owner]
         and planned.get('case_scope') == case.wire(),
         'ORIGINAL_SINGLE_USE_NATIVE_CASE_HOST_PLAN_BINDING')
    return None
