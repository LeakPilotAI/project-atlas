"""R7E47BB: characterize direct synthetic observation dispatch."""

from scripts.observation_runtime.contracts import Action
from scripts.observation_runtime.r7e47aw_fixture import (
    admission,
    make_fixture,
)
from scripts.observation_runtime.r7e47w_runner import SyntheticObservationRunner
from scripts.observation_runtime.r7e47x_session import ControlledSyntheticSession


def test_direct_runtime_observation_refused_without_budget(tmp_path):
    _, _, _, history, world, bootstrap = make_fixture(tmp_path / "fixture")
    runtime = bootstrap.start()
    runner = SyntheticObservationRunner(
        tmp_path / "budget.sqlite",
        admission(limit=1),
        enroll=True,
    )
    session = ControlledSyntheticSession(runtime, runner)

    try:
        before = runner.remaining()
        from scripts.observation_runtime.contracts import Refused

        try:
            runtime.execute(Action.OBSERVE, source="synthetic_feed")
        except Refused:
            pass
        else:
            raise AssertionError("Direct observation bypass was not refused")

        after = runner.remaining()

        assert before == 1
        assert after == 1
        assert world.effects == []
        assert not any(
            row["event"] == "DATA_SOURCE"
            for row in history.verify()
        )
    finally:
        if not session.closed:
            session.stop()
