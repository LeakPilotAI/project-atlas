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
        return intent

    def execute(self, *args, **kwargs):
        raise ValueError('INDEPENDENT_PHYSICAL_CASE_HOST_NOT_AUTHORIZED')
