"""R7E47BF: adversarial session-managed dispatch regression."""

import pytest

from scripts.observation_runtime.contracts import Action, Refused
from scripts.observation_runtime.r7e47aw_fixture import (
    admission,
    make_fixture,
    payload,
)
from scripts.observation_runtime.r7e47w_runner import SyntheticObservationRunner
from scripts.observation_runtime.r7e47x_session import (
    ControlledSyntheticSession,
    SessionRefused,
)


@pytest.fixture
def managed(tmp_path):
    _, _, _, history, world, bootstrap = make_fixture(tmp_path / "fixture")
    runtime = bootstrap.start()
    runner = SyntheticObservationRunner(
        tmp_path / "budget.sqlite",
        admission(limit=1),
        enroll=True,
    )
    session = ControlledSyntheticSession(runtime, runner)
    yield runtime, runner, session, history, world
    if not session.closed:
        session.stop()


@pytest.mark.parametrize(
    "dispatch",
    ["execute", "api_request", "background_step"],
)
def test_direct_dispatch_refused_without_budget(managed, dispatch):
    runtime, runner, session, history, world = managed

    with pytest.raises(Refused):
        getattr(runtime, dispatch)(
            Action.OBSERVE,
            source="synthetic_feed",
        )

    assert runner.remaining() == 1
    assert world.effects == []


def test_budget_exhaustion_prevents_second_ingestion(managed):
    runtime, runner, session, history, world = managed

    session.ingest(payload())
    assert runner.remaining() == 0
    assert len(world.effects) == 1

    with pytest.raises(Exception):
        session.ingest(payload())

    assert len(world.effects) == 1
    assert runner.remaining() == 0


def test_direct_dispatch_refused_after_successful_ingestion(managed):
    runtime, runner, session, history, world = managed

    session.ingest(payload())

    with pytest.raises(Refused):
        runtime.execute(Action.OBSERVE, source="synthetic_feed")

    assert len(world.effects) == 1
    assert runner.remaining() == 0


def test_duplicate_session_ownership_refused(managed):
    runtime, runner, session, history, world = managed

    with pytest.raises(SessionRefused):
        ControlledSyntheticSession(runtime, runner)

    assert runner.remaining() == 1
    assert world.effects == []
