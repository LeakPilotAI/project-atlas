"""Synthetic-only R7E47X integration tests."""

import json

import pytest

from scripts.observation_runtime.bootstrap import Status
from scripts.observation_runtime.r7e47t_candidate import ProviderAdmission
from scripts.observation_runtime.r7e47w_runner import (
    RunnerRefused,
    SyntheticObservationRunner,
)
from scripts.observation_runtime.r7e47x_session import (
    ControlledSyntheticSession,
    SessionRefused,
)
import uuid
from pathlib import Path

from scripts.observation_runtime.bootstrap import (
    Evidence,
    ObservationBootstrap,
    REQUIRED,
    SyntheticWorld,
    evidence_subject,
)
from scripts.observation_runtime.contracts import (
    ALLOWED,
    RuntimeContract,
    digest,
    enroll_fixture,
    file_digest,
    release_tree,
)
from scripts.observation_runtime.history import SessionHistory
def make_fixture(root: Path, *, protected_runtime=None):
    root.mkdir()
    scope = str(uuid.uuid4())
    (root / "synthetic-fixture.json").write_text(json.dumps({"scope": "SYNTHETIC_ONLY", "scope_id": scope}))
    runtime = root / "runtime"
    if protected_runtime is None:
        runtime.mkdir()
    else:
        protected_runtime(runtime)
    paths = {"runtime_root": runtime, "release_root": runtime / "releases" / "fixed",
             "state_root": runtime / "state", "journal_root": runtime / "state" / "journals",
             "cache_root": runtime / "cache", "build_root": runtime / "releases" / "fixed" / "assets",
             "environment_root": runtime / "environment", "configuration_path": runtime / "config" / "session.json"}
    for key, path in paths.items():
        (path.parent if key == "configuration_path" else path).mkdir(parents=True, exist_ok=True)
    paths["configuration_path"].write_bytes(b'{"scope":"SYNTHETIC_ONLY"}\n')
    (paths["release_root"] / "version.py").write_bytes(b"VERSION = 1\n")
    (paths["build_root"] / "index.html").write_bytes(b"fixed-runtime-assets")
    (paths["environment_root"] / "dependency.lock").write_bytes(b"synthetic-pinned-environment\n")
    development = [root / "development" / name for name in ("code", "state", "cache", "build", "env")]
    for path in development:
        path.mkdir(parents=True)
    manifest = {**{k: str(v) for k, v in paths.items()}, "schema": 1, "scope": "SYNTHETIC_ONLY",
                "profile": "OBSERVATION_ONLY", "release_id": digest(release_tree(paths["release_root"])[0]),
                "configuration_id": file_digest(paths["configuration_path"].read_bytes()),
                "dependency_ids": {"postgres": "a" * 64, "redis": "b" * 64,
                                   "environment": digest(release_tree(paths["environment_root"])[0])},
                "database_id": "synthetic_runtime_db", "volume_ids": ["synthetic_pg", "synthetic_redis"],
                "runtime_port": 8000, "session_id": str(uuid.uuid4()),
                "owner": {"pid": 4001, "created": 100, "executable_id": "1" * 64,
                          "command_id": "2" * 64, "run_id": str(uuid.uuid4())},
                "allowed_capabilities": sorted(x.value for x in ALLOWED), "data_sources": ["synthetic_feed"],
                "development": {"roots": list(map(str, development)), "database_ids": ["synthetic_test_db"],
                                "volume_ids": ["synthetic_test_volume"], "ports": [18000]}}
    pin = enroll_fixture(manifest, root, scope)
    contract = RuntimeContract(manifest, pin)
    history = SessionHistory.create_fixture(contract)
    world = SyntheticWorld(1_790_000_000.0)
    attempt = str(uuid.uuid4())
    world.evidence = [Evidence(kind, Status.ADMITTED, world.now, pin.manifest_id, attempt,
                               evidence_subject(manifest, kind)) for kind in sorted(REQUIRED)]
    bootstrap = ObservationBootstrap(contract, history, world, attempt)
    return manifest, pin, contract, history, world, bootstrap





def admission(provider="synthetic_feed", limit=3):
    return ProviderAdmission(
        provider=provider,
        scope="SYNTHETIC_ONLY",
        rights_approved=True,
        budget_approved=True,
        max_requests=limit,
    )


def payload(provider="synthetic_feed"):
    return json.dumps({
        "provider": provider,
        "symbol": "BTC",
        "timestamp_ms": 1790000000000,
        "price": 100.0,
        "volume": 5.0,
    }).encode()


def setup_session(tmp_path, provider="synthetic_feed", limit=3):
    root = tmp_path / "fixture"
    manifest, pin, contract, history, world, bootstrap = make_fixture(root)
    runtime = bootstrap.start()
    runner = SyntheticObservationRunner(
        tmp_path / "budget.sqlite",
        admission(provider, limit),
        enroll=True,
    )
    return runtime, runner, history, world


def test_successful_observation_and_graceful_shutdown(tmp_path):
    runtime, runner, history, world = setup_session(tmp_path)
    session = ControlledSyntheticSession(runtime, runner)

    snapshot, result = session.ingest(payload())

    assert snapshot is not None
    assert result["synthetic"] is True
    assert result["action"] == "OBSERVE"
    assert runner.remaining() == 2
    assert world.effects == [("OBSERVE", "synthetic_feed")]

    session.stop()

    assert world.runtime_alive is False
    assert runner.closed is True
    assert history.verify()[-1]["event"] == "GRACEFUL_SHUTDOWN"


def test_mismatched_provider_refused_before_dispatch(tmp_path):
    runtime, runner, history, world = setup_session(
        tmp_path, provider="other_feed"
    )

    with pytest.raises(SessionRefused, match="source scope"):
        ControlledSyntheticSession(runtime, runner)

    assert runner.remaining() == 3
    assert world.effects == []
    runtime.stop()
    runner.stop()


def test_invalid_fixture_charges_budget_without_dispatch(tmp_path):
    runtime, runner, history, world = setup_session(tmp_path)
    session = ControlledSyntheticSession(runtime, runner)

    with pytest.raises(Exception):
        session.ingest(b"not-json")

    assert runner.remaining() == 2
    assert world.effects == []
    assert all(row["event"] != "DATA_SOURCE" for row in history.verify())

    session.stop()


def test_budget_exhaustion_refuses_extra_observation(tmp_path):
    runtime, runner, history, world = setup_session(tmp_path, limit=1)
    session = ControlledSyntheticSession(runtime, runner)

    session.ingest(payload())

    with pytest.raises(RunnerRefused, match="budget"):
        session.ingest(payload())

    assert runner.remaining() == 0
    assert world.effects == [("OBSERVE", "synthetic_feed")]
    session.stop()


def test_expired_admission_refuses_before_budget_charge(tmp_path):
    runtime, runner, history, world = setup_session(tmp_path)
    session = ControlledSyntheticSession(runtime, runner)

    world.now += 6

    with pytest.raises(SessionRefused, match="admission"):
        session.ingest(payload())

    assert runner.remaining() == 3
    assert world.effects == []

    with pytest.raises(Exception):
        session.stop()

    events = [row["event"] for row in history.verify()]
    assert "INTERRUPTED" in events
    assert "RECOVERY_REQUIRED" in events
    assert "GRACEFUL_SHUTDOWN" not in events


def test_closed_session_refuses_repeated_operations(tmp_path):
    runtime, runner, history, world = setup_session(tmp_path)
    session = ControlledSyntheticSession(runtime, runner)
    session.stop()

    with pytest.raises(SessionRefused, match="closed"):
        session.ingest(payload())

    with pytest.raises(SessionRefused, match="already closed"):
        session.stop()

    assert runner.closed is True


def test_unstarted_runtime_refused(tmp_path):
    runtime, runner, history, world = setup_session(tmp_path)
    runtime.stop()

    with pytest.raises(SessionRefused, match="Active admitted"):
        ControlledSyntheticSession(runtime, runner)

    runner.stop()