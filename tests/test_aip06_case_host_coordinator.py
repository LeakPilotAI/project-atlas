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


def test_execution_remains_disabled(monkeypatch):
    _, _, case = fixture(monkeypatch)
    coordinator = CaseHostCoordinator(case, case.reservation)
    with pytest.raises(ValueError, match='INDEPENDENT_PHYSICAL_CASE_HOST_NOT_AUTHORIZED'):
        coordinator.execute()
