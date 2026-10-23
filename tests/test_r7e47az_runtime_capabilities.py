"""R7E47AZ: direct synthetic runtime capability regression."""

import pytest

from scripts.observation_runtime.r7e47aw_fixture import (
    admission,
    make_fixture,
    payload,
)
from scripts.observation_runtime.r7e47w_runner import SyntheticObservationRunner
from scripts.observation_runtime.r7e47x_session import ControlledSyntheticSession


@pytest.fixture
def controlled(tmp_path):
    _, _, _, history, world, bootstrap = make_fixture(tmp_path / "fixture")
    runtime = bootstrap.start()
    runner = SyntheticObservationRunner(
        tmp_path / "budget.sqlite",
        admission(limit=1),
        enroll=True,
    )
    session = ControlledSyntheticSession(runtime, runner)
    yield session, runner, history, world
    if not session.closed:
        session.stop()


@pytest.mark.parametrize(
    "capability",
    [
        "LIVE_PROVIDER",
        "PAPER_TRADE",
        "REAL_TRADE",
        "DISCORD",
        "PRODUCTION_BACKEND",
        "NETWORK",
    ],
)
def test_direct_capability_refused(controlled, capability):
    session, runner, history, world = controlled

    with pytest.raises(Exception):
        session.execute(capability)

    assert runner.remaining() == 1
    assert world.effects == []


def test_observation_still_works_after_refusal(controlled):
    session, runner, history, world = controlled

    with pytest.raises(Exception):
        session.execute("REAL_TRADE")

    snapshot, result = session.ingest(payload())

    assert snapshot is not None
    assert result["synthetic"] is True
    assert result["action"] == "OBSERVE"
    assert runner.remaining() == 0

    session.stop()

    assert session.closed is True
    assert world.runtime_alive is False
    assert history.verify()[-1]["event"] == "GRACEFUL_SHUTDOWN"
