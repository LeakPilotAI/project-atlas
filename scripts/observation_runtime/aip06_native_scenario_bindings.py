"""Exact dispatcher-to-source bindings; missing native producers fail closed.

No default subprocess, fault injection or synthetic capacity result. A pinned
per-case guarded context must exist before executing the existing source case.
Cases with no reviewed native producer remain explicitly unbound.
"""

from dataclasses import dataclass

from scripts.observation_runtime.aip06_acceptance_control import scenarios
from scripts.observation_runtime.aip06_acceptance_plan import schedule
from scripts.observation_runtime.aip06_harness import LIMITS, ROOTS, need
from scripts.observation_runtime.aip06_test_driver import run_reviewed_tests


@dataclass(frozen=True)
class NativeScenarioContract:
    id: str
    source_case: str | None
    roles: tuple
    max_children: int
    seconds: int
    fault_boundary: str
    stop_ns: int = 8 * 10**9
    ipc_ns: int = 6 * 10**9


def contracts():
    faults = {'F05': 'hard-realized-session-loss-before-next-admission-no-counterpart-write',
              'F06': 'input-clock-provider-expiry-before-next-admission',
              'F09': 'once-only-inception-interrupted-at-each-durable-cut',
              'F11': 'actual-bounded-native-pressure-with-reserved-stop',
              'F12': 'source-producer-continuation-read-model-committed-notification-native-binding',
              'BOOTSTRAP-IPC-FAULTS': 'bootstrap-credit-receipt-ACK-and-drain-exact-cuts',
              'OWNERSHIP-PROBES': 'contained-unknown-child-and-independent-complete-roster'}
    source = {r['id']: r for r in schedule()}
    return tuple(NativeScenarioContract(s.id, source[s.id].get('source_case'), s.roles,
        source[s.id]['max_children'], s.seconds, faults.get(s.id, 'original-reviewed-source-case')) for s in scenarios())


class NativeScenarioBinding:
    """No mutation of global targets or reuse of a finished guard's role map.

    context must provide the already qualified per-case guard/namespace and
    original prospective ticket. That concrete isolated-context producer is
    still required; an arbitrary module label cannot grant it.
    """
    def __init__(self, contract, *, source_pins, context=None, fault_driver=None):
        need(contract in contracts(), 'EXACT_NATIVE_SCENARIO_CONTRACT')
        self.contract, self.source_pins, self.context, self.fault_driver = contract, dict(source_pins), context, fault_driver
        self.roles = contract.roles

    def check(self, controller, guard, *, deadline_ns):
        guard.check()
        need(controller.clock() < deadline_ns and guard.processes is controller.process_port
             and controller.profile['source_pins'] == self.source_pins,
             'CURRENT_PINNED_GUARDED_NATIVE_SCENARIO')
        need(self.context is not None, 'QUALIFIED_PER_CASE_PHYSICAL_CONTEXT_MISSING:' + self.contract.id)
        need(self.context.guard is guard and self.context.controller is controller
             and self.context.contract == self.contract and self.context.roles == self.roles,
             'NO_CROSS_CONTEXT_ROLE_OR_ACCOUNT_ADOPTION')
        self.context.verify(deadline_ns=deadline_ns)
        if self.contract.source_case is None:
            need(self.fault_driver is not None, 'ACTUAL_NATIVE_FAULT_LOAD_PRODUCER_MISSING:' + self.contract.id)
            need(self.fault_driver.contract == self.contract, 'EXACT_FAULT_POINT_AND_ROLE_CONTRACT')
            self.fault_driver.verify(self.context, deadline_ns=deadline_ns)

    def reserve(self, guard, *, deadline_ns):
        need(self.context is not None and self.context.guard is guard, 'PREDECLARED_CASE_CONTEXT_REQUIRED')
        self.check(self.context.controller, guard, deadline_ns=deadline_ns)
        ticket = self.context.reserve(deadline_ns=deadline_ns)
        state = guard.resources.read()['state']
        need(type(ticket) is dict and ticket.get('scenario') == self.contract.id
             and ticket.get('root') == ROOTS['E'] and ticket.get('roles') == self.roles
             and ticket.get('held') is True and ticket.get('stop_capacity_reserved') is True
             and state['resources'].get(ticket.get('key'), {}).get('closed') is False
             and state['resources'][ticket['key']]['owner'] == guard.owner,
             'GENUINE_SHARED_LEDGER_CASE_RESERVATION')
        return ticket

    def execute(self, controller, guard, reservation, *, deadline_ns):
        self.check(controller, guard, deadline_ns=deadline_ns)
        need(self.context.reservation == reservation and reservation['roles'] == self.roles,
             'EXACT_CASE_RESERVATION_BEFORE_EXECUTION')
        if self.contract.source_case is None:
            result = self.fault_driver.execute(self.context, reservation, deadline_ns=deadline_ns)
        else:
            module = self.contract.source_case.split('::')[0]
            # Current guard must already be installed by the qualified physical
            # child. This call cannot install a second guard or create a child.
            result = run_reviewed_tests(modules=(module,), case_ids=(self.contract.source_case,),
                junit_leaf='scenario-' + self.contract.id + '.xml')
        need(controller.clock() < deadline_ns, 'NATIVE_SCENARIO_DEADLINE')
        return result  # Original source results never confer native PASS.

    def release(self, guard, reservation, evidence, *, deadline_ns):
        need(self.context is not None and guard is self.context.guard, 'ORIGINAL_CASE_RELEASE_CONTEXT')
        return self.context.release(reservation, evidence, deadline_ns=deadline_ns)

    def abort(self, guard, reservation, *, deadline_ns):
        need(self.context is not None and guard is self.context.guard, 'ORIGINAL_CASE_ABORT_CONTEXT')
        return self.context.abort(reservation, deadline_ns=deadline_ns)


def bindings(source_pins, *, contexts=None, fault_drivers=None):
    contexts, fault_drivers = contexts or {}, fault_drivers or {}
    ids = {c.id for c in contracts()}
    need(set(contexts) <= ids and set(fault_drivers) <= ids, 'NO_UNREVIEWED_NATIVE_SCENARIO')
    need(max(c.max_children for c in contracts()) + 2 <= LIMITS['processes'], 'OWNER_AND_DESCENDANT_CAPACITY')
    return {c.id: NativeScenarioBinding(c, source_pins=source_pins, context=contexts.get(c.id),
             fault_driver=fault_drivers.get(c.id)) for c in contracts()}
