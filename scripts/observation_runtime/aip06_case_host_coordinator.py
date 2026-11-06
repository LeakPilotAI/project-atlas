"""Fail-closed original-owner case-host orchestration boundary.

This module assembles a verified data-only plan. It does not spawn, resume,
release, send INPUT, or authorize a physical acceptance session.
"""
from scripts.observation_runtime.aip06_case_host_launch_intent import inspect_launch_intent
from scripts.observation_runtime.aip06_harness import need
from scripts.observation_runtime.aip06_scoped_context import CaseContext


class CaseHostCoordinator:
    """Retain one original reserved case and reject plan replay."""

    def __init__(self, case, reservation):
        need(type(case) is CaseContext and case.factory.pending is case
             and case.reservation is not None and reservation is case.reservation,
             'ORIGINAL_COORDINATOR_RESERVATION_REQUIRED')
        self.case = case
        self.reservation = reservation
        self.prepared = False
        self.intent = None
        self.host = None
        self.handoff_attempted = False

    def prepare(self, *, deadline_ns):
        need(not self.prepared, 'CASE_HOST_COORDINATOR_REPLAY_REFUSED')
        # Consume before verification: a failed preflight must not be retried
        # with mutated owner, reservation, source pins, or time authority.
        self.prepared = True
        intent = inspect_launch_intent(self.case, self.reservation,
                                       deadline_ns=deadline_ns)
        need(type(intent) is dict and intent.get('native_acceptance') is False
             and intent.get('execution_authorized') is False,
             'CASE_HOST_COORDINATOR_DATA_ONLY_INTENT_REQUIRED')
        self.intent = intent
        return intent

    def bind_existing_host(self, process):
        """Retain the exact already-guarded host; no native actions performed."""
        from scripts.observation_runtime.aip06_fixture_guard import GuardedProcess
        need(self.prepared and self.intent is not None and self.host is None,
             'PREPARED_ONCE_ONLY_CASE_HOST_BINDING_REQUIRED')
        need(type(process) is GuardedProcess,
             'ORIGINAL_GUARDED_RELEASED_CASE_HOST_REQUIRED')
        case = self.case
        port = getattr(case.guard.processes, 'port', case.guard.processes)
        need(process.guard is case.guard
             and not process.closed and type(process.plan) is dict
             and process.plan.get('name') == 'case_host'
             and any(child is process.child for child in port.sessions)
             and process.child.target_released is True
             and process.child.closed is False and process.child.failed is False
             and type(process.argv) in (tuple, list)
             and tuple(process.argv) == self.intent['argv']
             and case.factory.pending is case and case.reservation is self.reservation,
             'ORIGINAL_GUARDED_RELEASED_CASE_HOST_REQUIRED')
        port.verify_case_host_scope_after_release(process.child)
        self.host = process
        return process

    def deliver_handoff(self, *, deadline_ns):
        """Once-only original guarded INPUT; transport grants no execution authority."""
        need(self.host is not None and not self.handoff_attempted,
             'BOUND_ONCE_ONLY_CASE_HOST_HANDOFF_REQUIRED')
        # Mark before invoking the guarded channel: partial I/O is never replayed.
        self.handoff_attempted = True
        return self.case.deliver_physical_host_handoff(self.host,
                                                       deadline_ns=deadline_ns)

    def execute(self, *args, **kwargs):
        raise ValueError('INDEPENDENT_PHYSICAL_CASE_HOST_NOT_AUTHORIZED')
