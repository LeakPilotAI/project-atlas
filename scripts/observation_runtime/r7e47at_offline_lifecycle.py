"""R7E47AT: development-only synthetic observation lifecycle.

Reuses the existing test fixture factory. Not a production entry point.
No provider HTTP requests, PAPER execution, or trading.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from scripts.observation_runtime.r7e47x_session import ControlledSyntheticSession
from scripts.observation_runtime.r7e47w_runner import SyntheticObservationRunner
from scripts.observation_runtime.r7e47aw_fixture import admission, make_fixture, payload


def run_once() -> dict:
    with tempfile.TemporaryDirectory(prefix="atlas-observation-fixture-") as temp:
        root = Path(temp)
        _, _, _, history, world, bootstrap = make_fixture(root / "fixture")

        runtime = bootstrap.start()
        runner = SyntheticObservationRunner(
            root / "budget.sqlite",
            admission(limit=1),
            enroll=True,
        )
        session = ControlledSyntheticSession(runtime, runner)

        snapshot, result = session.ingest(payload())
        budget_remaining = runner.remaining()
        session.stop()

        events = [row["event"] for row in history.verify()]

        if (
            result.get("synthetic") is not True
            or result.get("action") != "OBSERVE"
            or budget_remaining != 0
            or world.runtime_alive is not False
            or events[-1] != "GRACEFUL_SHUTDOWN"
        ):
            raise RuntimeError("Synthetic lifecycle verification failed")

        return {
            "profile": "OBSERVATION_ONLY",
            "mode": "SYNTHETIC_OFFLINE",
            "observations": 1,
            "budget_remaining": budget_remaining,
            "session_closed": session.closed,
            "runtime_alive": world.runtime_alive,
            "final_event": events[-1],
            "network_enabled": False,
            "trading_enabled": False,
        }


def main() -> int:
    print(json.dumps(run_once(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
