import pytest

from scripts.observation_runtime.r7e47t_candidate import (
    AdmissionRefused,
    ProviderAdmission,
    SyntheticCollector,
)


def admitted(max_requests=2):
    return ProviderAdmission(
        provider="fixture",
        scope="SYNTHETIC_ONLY",
        rights_approved=True,
        budget_approved=True,
        max_requests=max_requests,
    )


@pytest.mark.parametrize("changes", [
    {"scope": "PRODUCTION"},
    {"rights_approved": False},
    {"budget_approved": False},
    {"max_requests": 0},
    {"max_requests": True},
    {"provider": ""},
])
def test_invalid_admission_refused(changes):
    values = vars(admitted()).copy()
    values.update(changes)
    with pytest.raises(AdmissionRefused):
        SyntheticCollector(ProviderAdmission(**values))


def test_exact_budget_and_no_extra_fixture_execution():
    collector = SyntheticCollector(admitted())
    calls = []
    for number in range(2):
        assert collector.collect("fixture", lambda: calls.append(number)) is None
    with pytest.raises(AdmissionRefused):
        collector.collect("fixture", lambda: calls.append("forbidden"))
    assert calls == [0, 1]
    assert collector.attempted == 2


def test_failed_fixture_consumes_budget():
    collector = SyntheticCollector(admitted(1))

    def fail():
        raise ValueError("synthetic failure")

    with pytest.raises(ValueError):
        collector.collect("fixture", fail)
    with pytest.raises(AdmissionRefused):
        collector.collect("fixture", lambda: None)
    assert collector.attempted == 1


def test_other_provider_refused_without_budget_consumption():
    collector = SyntheticCollector(admitted(1))
    with pytest.raises(AdmissionRefused):
        collector.collect("other", lambda: None)
    assert collector.attempted == 0


@pytest.mark.parametrize("capability", [
    "paper_order", "live_order", "prediction_open",
    "discord_send", "broker_mutation", "network_request",
])
def test_forbidden_capabilities(capability):
    collector = SyntheticCollector(admitted())
    with pytest.raises(AdmissionRefused):
        collector.execute(capability)


def test_stop_is_terminal():
    collector = SyntheticCollector(admitted())
    collector.stop()
    with pytest.raises(AdmissionRefused):
        collector.collect("fixture", lambda: None)