"""R7E47BI: offline-only transport regression."""

import pytest

from scripts.observation_runtime.r7e47bi_offline_transport import (
    OfflineFixtureTransport,
)
from scripts.observation_runtime.r7e47y_live_boundary import ObservationPlan
from scripts.observation_runtime.r7e47z_request_budget import (
    RequestBudget,
    RequestBudgetRefused,
)
from scripts.observation_runtime.r7e47aa_transport import TransportRefused


def plan():
    return ObservationPlan()


def test_offline_fixture_charges_before_parse(tmp_path):
    budget = RequestBudget(tmp_path / "budget.sqlite", enroll=True)
    transport = OfflineFixtureTransport(plan(), budget, b"invalid-json")

    with pytest.raises(Exception):
        transport.execute()

    assert budget.remaining() == 0


def test_second_attempt_refused(tmp_path):
    budget = RequestBudget(tmp_path / "budget.sqlite", enroll=True)
    transport = OfflineFixtureTransport(plan(), budget, b"invalid-json")

    with pytest.raises(Exception):
        transport.execute()

    with pytest.raises(TransportRefused):
        transport.execute()

    assert budget.remaining() == 0


def test_shared_ledger_refuses_second_transport(tmp_path):
    path = tmp_path / "budget.sqlite"
    budget = RequestBudget(path, enroll=True)

    first = OfflineFixtureTransport(plan(), budget, b"invalid-json")
    second = OfflineFixtureTransport(
        plan(),
        RequestBudget(path),
        b"invalid-json",
    )

    with pytest.raises(Exception):
        first.execute()

    with pytest.raises(RequestBudgetRefused):
        second.execute()

    assert budget.remaining() == 0


def test_arbitrary_sender_refused(tmp_path):
    budget = RequestBudget(tmp_path / "budget.sqlite", enroll=True)

    with pytest.raises(TransportRefused):
        OfflineFixtureTransport(plan(), budget, lambda: b"data")

    assert budget.remaining() == 1


def test_live_execution_refused_without_charge(tmp_path):
    budget = RequestBudget(tmp_path / "budget.sqlite", enroll=True)
    transport = OfflineFixtureTransport(plan(), budget, b"invalid-json")

    with pytest.raises(TransportRefused):
        transport.execute_live()

    assert budget.remaining() == 1
