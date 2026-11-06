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
    coordinator.host = object()  # Isolate once-only transport behavior from native binding.
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


def test_execution_remains_disabled(monkeypatch):
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    with pytest.raises(ValueError, match='INDEPENDENT_PHYSICAL_CASE_HOST_NOT_AUTHORIZED'):
        coordinator.execute()
