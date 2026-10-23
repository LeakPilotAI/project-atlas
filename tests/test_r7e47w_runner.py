import json

import pytest

from scripts.observation_runtime.r7e47t_candidate import ProviderAdmission
from scripts.observation_runtime.r7e47u_fixture_boundary import FixtureRefused
from scripts.observation_runtime.r7e47w_runner import (
    RunnerRefused,
    SyntheticObservationRunner,
)


def admission(limit=2):
    return ProviderAdmission(
        provider="fixture",
        scope="SYNTHETIC_ONLY",
        rights_approved=True,
        budget_approved=True,
        max_requests=limit,
    )


def raw(provider="fixture"):
    return json.dumps(
        {
            "provider": provider,
            "symbol": "BTC-USD",
            "timestamp_ms": 1000,
            "price": 100.0,
            "volume": 2.0,
        }
    ).encode("utf-8")


def test_valid_ingest_and_durable_remaining(tmp_path):
    path = tmp_path / "budget.sqlite"
    runner = SyntheticObservationRunner(path, admission(), enroll=True)
    snapshot = runner.ingest(raw())
    assert snapshot.symbol == "BTC-USD"
    assert runner.remaining() == 1
    runner.stop()


def test_invalid_fixture_still_consumes_durable_attempt(tmp_path):
    path = tmp_path / "budget.sqlite"
    runner = SyntheticObservationRunner(path, admission(1), enroll=True)
    with pytest.raises(FixtureRefused):
        runner.ingest(raw("wrong"))
    assert runner.remaining() == 0
    with pytest.raises(RunnerRefused):
        runner.ingest(raw())


def test_reopen_preserves_attempts(tmp_path):
    path = tmp_path / "budget.sqlite"
    first = SyntheticObservationRunner(path, admission(), enroll=True)
    first.ingest(raw())
    first.stop()
    reopened = SyntheticObservationRunner(path, admission())
    assert reopened.remaining() == 1
    reopened.ingest(raw())
    assert reopened.remaining() == 0


def test_deleted_ledger_refuses_reopen(tmp_path):
    path = tmp_path / "budget.sqlite"
    runner = SyntheticObservationRunner(path, admission(), enroll=True)
    runner.ingest(raw())
    runner.stop()
    path.unlink()
    with pytest.raises(RunnerRefused):
        SyntheticObservationRunner(path, admission())


def test_closed_runner_refuses_ingest(tmp_path):
    runner = SyntheticObservationRunner(
        tmp_path / "budget.sqlite", admission(), enroll=True
    )
    runner.stop()
    with pytest.raises(RunnerRefused):
        runner.ingest(raw())


@pytest.mark.parametrize(
    "changes",
    [
        {"scope": "PRODUCTION"},
        {"rights_approved": False},
        {"budget_approved": False},
        {"max_requests": 0},
        {"max_requests": True},
        {"provider": "INVALID PROVIDER"},
    ],
)
def test_invalid_admission_refused(tmp_path, changes):
    values = vars(admission()).copy()
    values.update(changes)
    with pytest.raises(RunnerRefused):
        SyntheticObservationRunner(
            tmp_path / "budget.sqlite", ProviderAdmission(**values),
            enroll=True,
        )


def test_no_capability_execution(tmp_path):
    runner = SyntheticObservationRunner(
        tmp_path / "budget.sqlite", admission(), enroll=True
    )
    with pytest.raises(RunnerRefused):
        runner.execute("trade")
    assert runner.remaining() == 2


def test_nonbytes_refused_without_budget_consumption(tmp_path):
    runner = SyntheticObservationRunner(
        tmp_path / "budget.sqlite", admission(), enroll=True
    )
    with pytest.raises(RunnerRefused):
        runner.ingest(lambda: raw())
    assert runner.remaining() == 2