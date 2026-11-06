"""Offline tests for the data-only case-host coordinator."""
import pytest
from scripts.observation_runtime.aip06_case_host_coordinator import CaseHostCoordinator
from tests.test_aip06_case_host_release_gate import fixture


def test_refuses_copied_reservation(monkeypatch):
    _, _, case = fixture(monkeypatch)
    with pytest.raises(ValueError, match='ORIGINAL_COORDINATOR_RESERVATION_REQUIRED'):
        CaseHostCoordinator(case, dict(case.reservation))


def test_preparation_once_only(monkeypatch):
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    seen = []
    def inspect(original, reservation, *, deadline_ns):
        seen.append((original, reservation, deadline_ns))
        return {'native_acceptance': False, 'execution_authorized': False}
    monkeypatch.setattr('scripts.observation_runtime.aip06_case_host_coordinator.inspect_launch_intent', inspect)
    assert coordinator.prepare(deadline_ns=200)['execution_authorized'] is False
    assert seen == [(case, case.reservation, 200)]
    with pytest.raises(ValueError, match='CASE_HOST_COORDINATOR_REPLAY_REFUSED'):
        coordinator.prepare(deadline_ns=200)


def test_preparation_does_not_expose_mutable_retained_handoff(monkeypatch):
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    source = {'argv': ('python', '-B', 'host'), 'handoff': {'reservation': {'held': True}},
              'native_acceptance': False, 'execution_authorized': False}
    monkeypatch.setattr('scripts.observation_runtime.aip06_case_host_coordinator.inspect_launch_intent',
                        lambda *args, **kwargs: source)
    returned = coordinator.prepare(deadline_ns=200)
    returned['handoff']['reservation']['held'] = False
    source['handoff']['reservation']['held'] = False
    assert coordinator.intent['handoff']['reservation']['held'] is True


def test_failed_preparation_cannot_retry(monkeypatch):
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    def fail(*args, **kwargs):
        raise ValueError('PREFLIGHT_REFUSED')
    monkeypatch.setattr('scripts.observation_runtime.aip06_case_host_coordinator.inspect_launch_intent', fail)
    with pytest.raises(ValueError, match='PREFLIGHT_REFUSED'):
        coordinator.prepare(deadline_ns=200)
    with pytest.raises(ValueError, match='CASE_HOST_COORDINATOR_REPLAY_REFUSED'):
        coordinator.prepare(deadline_ns=200)


def test_binding_refuses_foreign_host(monkeypatch):
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    with pytest.raises(ValueError, match='PREPARED_ONCE_ONLY_CASE_HOST_BINDING_REQUIRED'):
        coordinator.bind_existing_host(object())
    monkeypatch.setattr('scripts.observation_runtime.aip06_case_host_coordinator.inspect_launch_intent',
                        lambda *args, **kwargs: {'argv': ('python', '-B', 'host'),
                                                 'native_acceptance': False, 'execution_authorized': False})
    coordinator.prepare(deadline_ns=200)
    with pytest.raises(ValueError, match='ORIGINAL_GUARDED_RELEASED_CASE_HOST_REQUIRED'):
        coordinator.bind_existing_host(object())
    assert coordinator.host is None


def test_handoff_requires_original_bound_host(monkeypatch):
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    with pytest.raises(ValueError, match='BOUND_ONCE_ONLY_CASE_HOST_HANDOFF_REQUIRED'):
        coordinator.deliver_handoff(deadline_ns=200)


def test_handoff_attempt_is_once_only_even_on_failure(monkeypatch):
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    from types import SimpleNamespace
    plan = {'name': 'case_host'}
    child = SimpleNamespace(plan=plan, name='case_host', closed=False)
    coordinator.host = SimpleNamespace(guard=case.guard, child=child,
                                       plan=plan, keys=('original',), closed=False)
    coordinator.original_child = child
    coordinator.original_keys = ('original',)
    case.guard.processes = SimpleNamespace(port=SimpleNamespace(sessions=[child]))
    def refuse(*args, **kwargs):
        raise OSError('transport failure')
    monkeypatch.setattr(type(case), 'deliver_physical_host_handoff', refuse)
    with pytest.raises(OSError, match='transport failure'):
        coordinator.deliver_handoff(deadline_ns=200)
    with pytest.raises(ValueError, match='BOUND_ONCE_ONLY_CASE_HOST_HANDOFF_REQUIRED'):
        coordinator.deliver_handoff(deadline_ns=200)


def test_cleanup_requires_prior_handoff(monkeypatch):
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    with pytest.raises(ValueError, match='ORIGINAL_CASE_HOST_CLEANUP_CHECK_ONCE_ONLY'):
        coordinator.verify_original_cleanup()


def test_cleanup_rejects_unclosed_original_host(monkeypatch):
    from types import SimpleNamespace
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    coordinator.host = SimpleNamespace(closed=False, child=SimpleNamespace(closed=False))
    coordinator.handoff_attempted = True
    case.guard.processes = SimpleNamespace(port=SimpleNamespace(sessions=[]))
    with pytest.raises(ValueError, match='ORIGINAL_CASE_HOST_NATIVE_CLOSURE_EVIDENCE_REQUIRED'):
        coordinator.verify_original_cleanup()
    assert coordinator.cleanup_verified is False


def test_cleanup_accepts_only_original_retained_resources(monkeypatch):
    from types import SimpleNamespace
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    child = SimpleNamespace(closed=True)
    host = SimpleNamespace(guard=case.guard, child=child, keys=('original-key',), closed=True)
    port = SimpleNamespace(sessions=[child], resources_closed=lambda session, keys:
                           session is child and keys == ('original-key',))
    case.guard.processes = SimpleNamespace(port=port)
    coordinator.host = host
    coordinator.original_child = child
    coordinator.original_keys = ('original-key',)
    coordinator.handoff_attempted = True
    host.keys = ('substituted-key',)
    with pytest.raises(ValueError, match='ORIGINAL_CASE_HOST_NATIVE_CLOSURE_EVIDENCE_REQUIRED'):
        coordinator.verify_original_cleanup()
    host.keys = ('original-key',)
    assert coordinator.verify_original_cleanup() is True
    with pytest.raises(ValueError, match='ORIGINAL_CASE_HOST_CLEANUP_CHECK_ONCE_ONLY'):
        coordinator.verify_original_cleanup()


def test_abort_requires_original_bound_host(monkeypatch):
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    with pytest.raises(ValueError, match='ORIGINAL_CASE_HOST_ABORT_ONCE_ONLY'):
        coordinator.abort_original_host(deadline_ns=200)


def test_abort_delegates_once_to_original_owner(monkeypatch):
    from types import SimpleNamespace
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    child = object()
    host = SimpleNamespace(guard=case.guard, child=child)
    called = []
    port = SimpleNamespace(sessions=[child], abort=lambda original, *, deadline_ns:
                           called.append((original, deadline_ns)))
    case.guard.processes = SimpleNamespace(port=port)
    coordinator.host = host
    coordinator.original_child = child
    case.controller = SimpleNamespace(clock=lambda: 100)
    assert coordinator.abort_original_host(deadline_ns=200) is None
    assert called == [(child, 200)]
    with pytest.raises(ValueError, match='ORIGINAL_CASE_HOST_ABORT_ONCE_ONLY'):
        coordinator.abort_original_host(deadline_ns=200)


def test_failed_abort_cannot_replay_or_send_input(monkeypatch):
    from types import SimpleNamespace
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    child = object()
    coordinator.host = SimpleNamespace(guard=case.guard, child=child)
    coordinator.original_child = child
    def fail(original, *, deadline_ns):
        raise OSError('native abort unresolved')
    case.guard.processes = SimpleNamespace(port=SimpleNamespace(sessions=[child], abort=fail))
    case.controller = SimpleNamespace(clock=lambda: 100)
    with pytest.raises(OSError, match='native abort unresolved'):
        coordinator.abort_original_host(deadline_ns=200)
    with pytest.raises(ValueError, match='ORIGINAL_CASE_HOST_ABORT_ONCE_ONLY'):
        coordinator.abort_original_host(deadline_ns=200)
    with pytest.raises(ValueError, match='BOUND_ONCE_ONLY_CASE_HOST_HANDOFF_REQUIRED'):
        coordinator.deliver_handoff(deadline_ns=200)
    assert coordinator.cleanup_verified is False
    assert coordinator.abort_attempted is True
    assert coordinator.abort_completed is False
    with pytest.raises(ValueError, match='ORIGINAL_CASE_HOST_CLEANUP_CHECK_ONCE_ONLY'):
        coordinator.verify_original_cleanup()


def test_native_abort_closure_does_not_certify_wrapper_cleanup(monkeypatch):
    from types import SimpleNamespace
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    child = SimpleNamespace(closed=True)
    host = SimpleNamespace(guard=case.guard, child=child, closed=False,
                           keys=('original',))
    port = SimpleNamespace(sessions=[child], resources_closed=lambda original, keys:
                           original is child and keys == ('original',))
    case.guard.processes = SimpleNamespace(port=port)
    coordinator.host = host
    coordinator.original_child = child
    coordinator.original_keys = ('original',)
    coordinator.abort_attempted = True
    coordinator.abort_completed = True
    assert coordinator.verify_aborted_native_closure() is True
    assert coordinator.cleanup_verified is False
    with pytest.raises(ValueError, match='ORIGINAL_CASE_HOST_NATIVE_CLOSURE_EVIDENCE_REQUIRED'):
        coordinator.verify_original_cleanup()


def test_reader_evidence_rejects_unbound_or_synthetic_result(monkeypatch):
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    with pytest.raises(ValueError, match='ORIGINAL_COMPLETED_INDEPENDENT_READER_EVIDENCE_REQUIRED'):
        coordinator.attach_independent_reader_evidence(object(), deadline_ns=200)
    assert coordinator.reader_evidence is None


def test_attached_reader_evidence_rejects_substituted_result(monkeypatch):
    from types import SimpleNamespace
    from scripts.observation_runtime.aip06_harness import digest
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    child = object()
    session = SimpleNamespace(child=child, closed=True)
    result = {'native_acceptance': False, 'cuts': []}
    reader = SimpleNamespace(case=case, session=session, result=result,
                             result_hash=digest(result), failed=False,
                             verify=lambda *, deadline_ns: None)
    case.reader = reader
    coordinator.reader_evidence = (reader, reader.result_hash, session, child)
    assert coordinator.verify_attached_reader_evidence(deadline_ns=200) == reader.result_hash
    reader.result = {'native_acceptance': False, 'cuts': ['substituted']}
    with pytest.raises(ValueError, match='ATTACHED_READER_EVIDENCE_IDENTITY_OR_DIGEST_CHANGED'):
        coordinator.verify_attached_reader_evidence(deadline_ns=200)
    reader.result = result
    reader.session = SimpleNamespace(child=child, closed=True)
    with pytest.raises(ValueError, match='ATTACHED_READER_EVIDENCE_IDENTITY_OR_DIGEST_CHANGED'):
        coordinator.verify_attached_reader_evidence(deadline_ns=200)
    reader.session = session
    session.child = object()
    with pytest.raises(ValueError, match='ATTACHED_READER_EVIDENCE_IDENTITY_OR_DIGEST_CHANGED'):
        coordinator.verify_attached_reader_evidence(deadline_ns=200)


def test_coordinator_abort_lifecycle_retains_native_proof_without_false_case_cleanup(monkeypatch):
    from types import SimpleNamespace
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    child = SimpleNamespace(closed=False)
    host = SimpleNamespace(guard=case.guard, child=child, closed=False,
                           keys=('original-handle',))
    calls = []
    def abort(original, *, deadline_ns):
        assert original is child
        calls.append(deadline_ns)
        child.closed = True
    port = SimpleNamespace(sessions=[child], abort=abort,
                           resources_closed=lambda original, keys:
                           original is child and child.closed and keys == ('original-handle',))
    case.guard.processes = SimpleNamespace(port=port)
    case.controller = SimpleNamespace(clock=lambda: 100)
    coordinator.host = host
    coordinator.original_child = child
    coordinator.original_keys = ('original-handle',)
    assert coordinator.abort_original_host(deadline_ns=200) is None
    assert calls == [200]
    assert coordinator.verify_aborted_native_closure() is True
    with pytest.raises(ValueError, match='ORIGINAL_CASE_HOST_NATIVE_CLOSURE_EVIDENCE_REQUIRED'):
        coordinator.verify_original_cleanup()
    with pytest.raises(ValueError, match='BOUND_ONCE_ONLY_CASE_HOST_HANDOFF_REQUIRED'):
        coordinator.deliver_handoff(deadline_ns=200)
    assert coordinator.cleanup_verified is False


def test_case_scope_release_requires_original_owner_cleanup(monkeypatch):
    from types import SimpleNamespace
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    coordinator.cleanup_verified = True
    case.closed = True
    port = SimpleNamespace(scoped_case=case)
    case.guard.processes = SimpleNamespace(port=port)
    with pytest.raises(ValueError, match='ORIGINAL_CASE_SCOPE_RELEASE_NOT_VERIFIED'):
        coordinator.verify_case_released()
    port.scoped_case = None
    with pytest.raises(ValueError, match='ORIGINAL_CASE_SCOPE_RELEASE_NOT_VERIFIED'):
        coordinator.verify_case_released()
    case.factory.pending = object()
    with pytest.raises(ValueError, match='ORIGINAL_CASE_SCOPE_RELEASE_NOT_VERIFIED'):
        coordinator.verify_case_released()
    case.factory.pending = None
    port.scoped_case = object()
    with pytest.raises(ValueError, match='ORIGINAL_CASE_SCOPE_RELEASE_NOT_VERIFIED'):
        coordinator.verify_case_released()
    port.scoped_case = None
    assert coordinator.verify_case_released() is True


def test_execution_remains_disabled(monkeypatch):
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    with pytest.raises(ValueError, match='INDEPENDENT_PHYSICAL_CASE_HOST_NOT_AUTHORIZED'):
        coordinator.execute()


@pytest.mark.parametrize('keys', [(), ('native',), ('native', 'native'),
                                  ('slot', 'native'), ('native', 'slot', 'extra')])
def test_binding_rejects_incomplete_or_substituted_original_resource_set(monkeypatch, keys):
    from types import SimpleNamespace
    from scripts.observation_runtime.aip06_fixture_guard import GuardedProcess
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    monkeypatch.setattr('scripts.observation_runtime.aip06_case_host_coordinator.inspect_launch_intent',
                        lambda *args, **kwargs: {'argv': ('python', '-B', 'host'),
                                                 'native_acceptance': False,
                                                 'execution_authorized': False})
    coordinator.prepare(deadline_ns=200)
    child = SimpleNamespace(keys=('native',), permit={'slots': ('slot',)},
                            target_released=True, closed=False, failed=False)
    port = SimpleNamespace(sessions=[child],
                           verify_case_host_scope_after_release=lambda original: True)
    case.guard.processes = SimpleNamespace(port=port)
    plan = {'name': 'case_host'}
    child.plan = plan
    child.name = 'case_host'
    host = GuardedProcess(case.guard, child, plan, keys,
                          ('python', '-B', 'host'))
    with pytest.raises(ValueError, match='ORIGINAL_GUARDED_RELEASED_CASE_HOST_REQUIRED'):
        coordinator.bind_existing_host(host)
    assert coordinator.host is None and coordinator.original_child is None
    assert coordinator.binding_attempted is True
    host.keys = ('native', 'slot')
    with pytest.raises(ValueError, match='PREPARED_ONCE_ONLY_CASE_HOST_BINDING_REQUIRED'):
        coordinator.bind_existing_host(host)
    assert coordinator.host is None and coordinator.original_keys is None


def test_binding_attempt_is_consumed_before_host_type_validation(monkeypatch):
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    monkeypatch.setattr('scripts.observation_runtime.aip06_case_host_coordinator.inspect_launch_intent',
                        lambda *args, **kwargs: {'argv': ('python', '-B', 'host'),
                                                 'native_acceptance': False,
                                                 'execution_authorized': False})
    coordinator.prepare(deadline_ns=200)
    with pytest.raises(ValueError, match='ORIGINAL_GUARDED_RELEASED_CASE_HOST_REQUIRED'):
        coordinator.bind_existing_host(object())
    assert coordinator.binding_attempted and coordinator.host is None
    with pytest.raises(ValueError, match='PREPARED_ONCE_ONLY_CASE_HOST_BINDING_REQUIRED'):
        coordinator.bind_existing_host(object())


@pytest.mark.parametrize('mutation', ['child', 'keys', 'plan', 'scope', 'reservation', 'closed'])
def test_handoff_rejects_post_binding_owner_mutation_without_replay(monkeypatch, mutation):
    from types import SimpleNamespace
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    plan = {'name': 'case_host'}
    child = SimpleNamespace(plan=plan, name='case_host', closed=False)
    host = SimpleNamespace(guard=case.guard, child=child, plan=plan,
                           keys=('native', 'slot'), closed=False)
    case.guard.processes = SimpleNamespace(port=SimpleNamespace(sessions=[child]))
    coordinator.host, coordinator.original_child = host, child
    coordinator.original_keys = ('native', 'slot')
    if mutation == 'child': host.child = SimpleNamespace(plan=plan, name='case_host', closed=False)
    if mutation == 'keys': host.keys = ('substituted', 'slot')
    if mutation == 'plan': child.plan = {'name': 'case_host'}
    if mutation == 'scope': case.factory.pending = None
    if mutation == 'reservation': case.reservation = dict(case.reservation)
    if mutation == 'closed': child.closed = True
    sent = []
    monkeypatch.setattr(type(case), 'deliver_physical_host_handoff',
                        lambda *args, **kwargs: sent.append(True))
    with pytest.raises(ValueError, match='ORIGINAL_BOUND_HOST_HANDOFF_IDENTITY_CHANGED'):
        coordinator.deliver_handoff(deadline_ns=200)
    assert not sent and coordinator.handoff_attempted
    with pytest.raises(ValueError, match='BOUND_ONCE_ONLY_CASE_HOST_HANDOFF_REQUIRED'):
        coordinator.deliver_handoff(deadline_ns=200)
