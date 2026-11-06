"""Fail-closed original-owner case-host orchestration boundary.

This module prepares an owner-bound plan, binds an existing guarded host,
and delegates a single INPUT to the original guarded channel. It does not
spawn, resume, release, or authorize physical case execution.
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
        self.binding_attempted = False
        self.handoff_attempted = False
        self.cleanup_verified = False
        self.abort_attempted = False
        self.abort_completed = False
        self.original_child = None
        self.original_keys = None
        self.reader_evidence = None

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
        # Never expose the retained authority-bearing handoff by reference.
        import copy
        self.intent = copy.deepcopy(intent)
        return copy.deepcopy(intent)

    def bind_existing_host(self, process):
        """Retain the exact already-guarded host; no native actions performed."""
        from scripts.observation_runtime.aip06_fixture_guard import GuardedProcess
        need(self.prepared and self.intent is not None and self.host is None
             and not self.binding_attempted,
             'PREPARED_ONCE_ONLY_CASE_HOST_BINDING_REQUIRED')
        self.binding_attempted = True
        need(type(process) is GuardedProcess,
             'ORIGINAL_GUARDED_RELEASED_CASE_HOST_REQUIRED')
        case = self.case
        port = getattr(case.guard.processes, 'port', case.guard.processes)
        need(process.guard is case.guard
             and not process.closed and type(process.plan) is dict
             and process.plan.get('name') == 'case_host'
             and process.child.plan is process.plan
             and process.child.name == 'case_host'
             and any(child is process.child for child in port.sessions)
             and process.child.target_released is True
             and process.child.closed is False and process.child.failed is False
             and type(process.argv) in (tuple, list)
             and tuple(process.argv) == self.intent['argv']
             and type(process.keys) in (tuple, list)
             and bool(process.keys) and len(process.keys) == len(set(process.keys))
             and all(type(key) is str for key in process.keys)
             and tuple(process.keys) == (tuple(process.child.keys)
                                        + tuple(process.child.permit['slots']))
             and case.factory.pending is case and case.reservation is self.reservation,
             'ORIGINAL_GUARDED_RELEASED_CASE_HOST_REQUIRED')
        port.verify_case_host_scope_after_release(process.child)
        self.host = process
        self.original_child = process.child
        self.original_keys = tuple(process.keys)
        return process

    def deliver_handoff(self, *, deadline_ns):
        """Once-only original guarded INPUT; transport grants no execution authority."""
        need(self.host is not None and not self.handoff_attempted
             and not self.abort_attempted and not self.cleanup_verified,
             'BOUND_ONCE_ONLY_CASE_HOST_HANDOFF_REQUIRED')
        # Mark before validation or I/O: an owner substitution must not be retried.
        self.handoff_attempted = True
        port = getattr(self.case.guard.processes, 'port', self.case.guard.processes)
        need(self.host.guard is self.case.guard
             and self.host.child is self.original_child
             and any(child is self.original_child for child in port.sessions)
             and tuple(self.host.keys) == self.original_keys
             and self.host.child.plan is self.host.plan
             and self.host.child.name == 'case_host'
             and self.host.child.closed is False
             and self.host.closed is False
             and self.case.factory.pending is self.case
             and self.case.reservation is self.reservation,
             'ORIGINAL_BOUND_HOST_HANDOFF_IDENTITY_CHANGED')
        return self.case.deliver_physical_host_handoff(self.host,
                                                       deadline_ns=deadline_ns)

    def abort_original_host(self, *, deadline_ns):
        """One bounded abort through the original native session owner only."""
        need(self.host is not None and self.original_child is not None
             and not self.abort_attempted and not self.cleanup_verified,
             'ORIGINAL_CASE_HOST_ABORT_ONCE_ONLY')
        process = self.host
        port = getattr(self.case.guard.processes, 'port', self.case.guard.processes)
        need(process.guard is self.case.guard
             and process.child is self.original_child
             and any(retained is self.original_child for retained in port.sessions)
             and type(process.keys) in (tuple, list)
             and tuple(process.keys) == self.original_keys
             and bool(self.original_keys)
             and type(deadline_ns) is int
             and self.case.controller.clock() < deadline_ns,
             'ORIGINAL_BOUNDED_CASE_HOST_ABORT_OWNER_REQUIRED')
        self.abort_attempted = True
        # The port owns termination, Job and process-handle closure. Never
        # issue a second termination or claim closure after an exception.
        port.abort(self.original_child, deadline_ns=deadline_ns)
        self.abort_completed = True
        return None

    def verify_aborted_native_closure(self):
        """Verify native abort closure without claiming wrapper or case closure."""
        need(self.abort_completed and self.original_child is not None
             and not self.cleanup_verified,
             'COMPLETED_ORIGINAL_ABORT_REQUIRED_FOR_NATIVE_CLOSURE')
        port = getattr(self.case.guard.processes, 'port', self.case.guard.processes)
        need(self.host.guard is self.case.guard
             and self.host.child is self.original_child
             and any(retained is self.original_child for retained in port.sessions)
             and type(self.host.keys) in (tuple, list)
             and tuple(self.host.keys) == self.original_keys
             and self.original_child.closed is True
             and bool(self.original_keys)
             and port.resources_closed(self.original_child, self.original_keys) is True,
             'ABORTED_ORIGINAL_NATIVE_RESOURCES_NOT_CLOSED')
        # A native abort does not mark GuardedProcess.closed or CaseContext.closed.
        # Leave the complete cleanup gate closed until separately proven.
        return True

    def verify_original_cleanup(self):
        """Observe completed original-owner cleanup; never terminate by PID."""
        need(self.host is not None and (self.handoff_attempted or self.abort_completed)
             and not self.cleanup_verified,
             'ORIGINAL_CASE_HOST_CLEANUP_CHECK_ONCE_ONLY')
        process = self.host
        port = getattr(self.case.guard.processes, 'port', self.case.guard.processes)
        need(getattr(process, 'guard', None) is self.case.guard
             and getattr(process, 'child', None) is self.original_child
             and self.original_child is not None
             and type(process.keys) in (tuple, list)
             and tuple(process.keys) == self.original_keys
             and bool(self.original_keys)
             and process.closed is True and process.child.closed is True
             and any(retained is self.original_child for retained in port.sessions)
             and port.resources_closed(self.original_child, self.original_keys) is True
             and all(key in self.case.guard.resources.state['resources']
                     and self.case.guard.resources.state['resources'][key]['closed'] is True
                     for key in self.original_keys),
             'ORIGINAL_CASE_HOST_NATIVE_CLOSURE_EVIDENCE_REQUIRED')
        self.cleanup_verified = True
        return True

    def attach_independent_reader_evidence(self, reader, *, deadline_ns):
        """Retain completed original reader evidence; never treat it as native acceptance."""
        from scripts.observation_runtime.aip06_scoped_context import ReaderContext
        from scripts.observation_runtime.aip06_harness import digest
        need(self.prepared and self.host is not None
             and self.reader_evidence is None and not self.abort_attempted
             and not self.cleanup_verified and type(reader) is ReaderContext
             and reader.case is self.case and self.case.reader is reader
             and reader.result is not None and reader.failed is False
             and reader.session.closed is True
             and reader.result_hash == digest(reader.result)
             and type(reader.result) is dict
             and reader.result.get('native_acceptance') is False,
             'ORIGINAL_COMPLETED_INDEPENDENT_READER_EVIDENCE_REQUIRED')
        reader.verify(deadline_ns=deadline_ns)
        self.reader_evidence = (reader, reader.result_hash, reader.session,
                                reader.session.child)
        return reader.result_hash

    def verify_attached_reader_evidence(self, *, deadline_ns):
        """Recheck original retained reader and result against substitution."""
        from scripts.observation_runtime.aip06_harness import digest
        need(self.reader_evidence is not None,
             'ORIGINAL_READER_EVIDENCE_NOT_ATTACHED')
        reader, result_hash, session, child = self.reader_evidence
        need(reader.case is self.case and self.case.reader is reader
             and reader.session is session and session.child is child
             and reader.result_hash == result_hash
             and type(reader.result) is dict
             and reader.result.get('native_acceptance') is False
             and digest(reader.result) == result_hash
             and reader.failed is False and session.closed is True,
             'ATTACHED_READER_EVIDENCE_IDENTITY_OR_DIGEST_CHANGED')
        reader.verify(deadline_ns=deadline_ns)
        return result_hash

    def verify_case_released(self):
        """Check that the original case owner released its scope."""
        port = getattr(self.case.guard.processes, 'port', self.case.guard.processes)
        need(self.cleanup_verified and self.case.closed is True
             and self.case.factory.pending is None
             and getattr(port, 'scoped_case', None) is None,
             'ORIGINAL_CASE_SCOPE_RELEASE_NOT_VERIFIED')
        return True

    def execute(self, *args, **kwargs):
        raise ValueError('INDEPENDENT_PHYSICAL_CASE_HOST_NOT_AUTHORIZED')
