import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from scripts.observation_runtime.r7e47t_candidate import ProviderAdmission
from scripts.observation_runtime.r7e47u_fixture_boundary import FixtureRefused
from scripts.observation_runtime.r7e47w_runner import (
    RunnerRefused,
    SyntheticObservationRunner,
)


def admission(limit):
    return ProviderAdmission(
        provider="fixture",
        scope="SYNTHETIC_ONLY",
        rights_approved=True,
        budget_approved=True,
        max_requests=limit,
    )


def payload(provider="fixture"):
    return json.dumps(
        {
            "provider": provider,
            "symbol": "BTC-USD",
            "timestamp_ms": 1000,
            "price": 100.0,
            "volume": 1.0,
        }
    ).encode("utf-8")


def test_two_runners_share_one_durable_budget(tmp_path):
    path = tmp_path / "budget.sqlite"
    first = SyntheticObservationRunner(path, admission(2), enroll=True)
    second = SyntheticObservationRunner(path, admission(2))

    first.ingest(payload())
    second.ingest(payload())

    assert first.remaining() == 0
    assert second.remaining() == 0

    with pytest.raises(RunnerRefused):
        first.ingest(payload())


def test_invalid_payload_consumes_exactly_one_attempt(tmp_path):
    path = tmp_path / "budget.sqlite"
    runner = SyntheticObservationRunner(path, admission(3), enroll=True)

    with pytest.raises(FixtureRefused):
        runner.ingest(payload("wrong"))

    assert runner.remaining() == 2
    runner.ingest(payload())
    assert runner.remaining() == 1


def test_concurrent_runners_cannot_exceed_shared_budget(tmp_path):
    path = tmp_path / "budget.sqlite"
    SyntheticObservationRunner(path, admission(5), enroll=True).stop()

    def attempt(_):
        runner = SyntheticObservationRunner(path, admission(5))
        try:
            runner.ingest(payload())
            return True
        except RunnerRefused:
            return False
        finally:
            runner.stop()

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(attempt, range(20)))

    assert sum(results) == 5
    assert SyntheticObservationRunner(
        path, admission(5)
    ).remaining() == 0


def test_reopening_cannot_reset_exhausted_budget(tmp_path):
    path = tmp_path / "budget.sqlite"
    first = SyntheticObservationRunner(path, admission(1), enroll=True)
    first.ingest(payload())
    first.stop()

    for _ in range(3):
        reopened = SyntheticObservationRunner(path, admission(1))
        assert reopened.remaining() == 0
        with pytest.raises(RunnerRefused):
            reopened.ingest(payload())
        reopened.stop()


def test_invalid_payload_does_not_execute_capabilities(tmp_path):
    path = tmp_path / "budget.sqlite"
    runner = SyntheticObservationRunner(path, admission(1), enroll=True)

    with pytest.raises(FixtureRefused):
        runner.ingest(b'{"unexpected":"field"}')

    with pytest.raises(RunnerRefused):
        runner.execute("live_order")

    assert runner.remaining() == 0