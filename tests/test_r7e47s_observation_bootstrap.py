"""Synthetic bootstrap/resources only; never start Atlas or a real container."""
from __future__ import annotations

import copy
import dataclasses
import json
import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path

import pytest

from scripts.observation_runtime import history as history_module
from scripts.observation_runtime.bootstrap import (
    REQUIRED,
    Evidence,
    NextStartupSelection,
    ObservationBootstrap,
    Status,
    SyntheticWorld,
    evaluate_candidate,
    evidence_subject,
)
from scripts.observation_runtime.contracts import (
    ALLOWED,
    Action,
    DevelopmentWorkspace,
    Refused,
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
                "allowed_capabilities": sorted(x.value for x in ALLOWED), "data_sources": ["synthetic-feed"],
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


@pytest.fixture
def fixture(tmp_path):
    return make_fixture(tmp_path / "fixture")


def test_admitted_is_explicitly_synthetic_and_not_production_authority(fixture):
    *_, bootstrap = fixture
    decision = bootstrap.evaluate()
    assert decision.status == Status.ADMITTED
    assert decision.scope == "SYNTHETIC_ONLY"
    assert decision.production_start_authorized is False
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.production_start_authorized = True


@pytest.mark.parametrize("action", sorted(set(Action) - ALLOWED))
@pytest.mark.parametrize("entry", ["execute", "api_request", "background_step"])
def test_forbidden_actions_never_reach_execution_handlers(fixture, action, entry):
    _manifest, _pin, _contract, history, world, bootstrap = fixture
    runtime = bootstrap.start()
    before = history.path.read_bytes()
    with pytest.raises(Refused, match="capability denied"):
        getattr(runtime, entry)(action)
    assert world.effects == []
    assert history.path.read_bytes() == before
    assert world.runtime_alive is True


@pytest.mark.parametrize("action", ["paper_order", "UNKNOWN", "", None, True])
def test_unknown_actions_refuse(fixture, action):
    runtime = fixture[-1].start()
    with pytest.raises(Refused):
        runtime.execute(action)
    assert fixture[-2].effects == []


def test_allowed_observation_and_research_use_explicit_source(fixture):
    *_, world, bootstrap = fixture
    runtime = bootstrap.start()
    assert runtime.execute(Action.OBSERVE, source="synthetic-feed")["synthetic"] is True
    assert runtime.api_request(Action.RESEARCH)["action"] == "RESEARCH"
    with pytest.raises(Refused):
        runtime.background_step(Action.OBSERVE, source="unapproved-feed")
    assert len(world.effects) == 2


@pytest.mark.parametrize("kind", sorted(REQUIRED))
def test_each_required_missing_evidence_is_unknown(fixture, kind):
    bootstrap, world = fixture[-1], fixture[-2]
    world.evidence = [f for f in world.evidence if f.kind != kind]
    assert bootstrap.evaluate().status == Status.UNKNOWN
    with pytest.raises(Refused):
        bootstrap.start()
    assert world.runtime_alive is False
    assert world.effects == []


@pytest.mark.parametrize("age", [5.0001, -0.0001, float("nan"), float("inf")])
def test_stale_future_and_invalid_evidence_never_admit(fixture, age):
    *_, world, bootstrap = fixture
    world.evidence[0] = dataclasses.replace(world.evidence[0], observed_at=world.now - age)
    assert bootstrap.evaluate().status == Status.UNKNOWN


def test_exact_freshness_boundary_and_expired_continuing_dispatch(fixture):
    *_, world, bootstrap = fixture
    world.now += 5
    assert bootstrap.evaluate().status == Status.ADMITTED
    runtime = bootstrap.start()
    world.now += 0.001
    with pytest.raises(Refused):
        runtime.execute(Action.OBSERVE, source="synthetic-feed")
    assert world.effects == []


@pytest.mark.parametrize("change", ["attempt", "manifest", "scope", "status", "duplicate", "unknown", "malformed"])
def test_ambiguous_or_replayed_evidence_is_blocked(fixture, change):
    *_, world, bootstrap = fixture
    fact = world.evidence[0]
    if change == "attempt":
        world.evidence[0] = dataclasses.replace(fact, attempt_id=str(uuid.uuid4()))
    elif change == "manifest":
        world.evidence[0] = dataclasses.replace(fact, manifest_id="0" * 64)
    elif change == "scope":
        world.evidence[0] = dataclasses.replace(fact, scope="PRODUCTION")
    elif change == "status":
        world.evidence[0] = dataclasses.replace(fact, status=True)
    elif change == "duplicate":
        world.evidence.append(dataclasses.replace(fact, status=Status.BLOCKED))
    elif change == "unknown":
        world.evidence[0] = dataclasses.replace(fact, kind="other")
    else:
        world.evidence[0] = {"status": "ADMITTED"}
    assert bootstrap.evaluate().status == Status.BLOCKED


@pytest.mark.parametrize("kind", sorted(REQUIRED))
def test_known_blocked_conditions_refuse_without_clearing(fixture, kind):
    *_, world, bootstrap = fixture
    world.evidence = [dataclasses.replace(f, status=Status.BLOCKED) if f.kind == kind else f for f in world.evidence]
    assert bootstrap.evaluate().status == Status.BLOCKED
    with pytest.raises(Refused):
        bootstrap.start()
    assert world.effects == []


@pytest.mark.parametrize("change", ["state", "development", "cache", "build", "database", "volume", "port", "owner", "dependency", "release", "configuration", "profile", "capability", "missing"])
def test_changed_manifest_cannot_self_authorize(fixture, change):
    manifest, pin, *_ = fixture
    changed = copy.deepcopy(manifest)
    if change == "state": changed["state_root"] = changed["cache_root"]
    elif change == "development": changed["development"]["roots"][0] = changed["release_root"]
    elif change == "cache": changed["cache_root"] = changed["development"]["roots"][2]
    elif change == "build": changed["build_root"] = changed["development"]["roots"][3]
    elif change == "database": changed["development"]["database_ids"] = [changed["database_id"]]
    elif change == "volume": changed["development"]["volume_ids"] = changed["volume_ids"]
    elif change == "port": changed["development"]["ports"] = [changed["runtime_port"]]
    elif change == "owner": changed["owner"]["pid"] += 1
    elif change == "dependency": changed["dependency_ids"]["postgres"] = "c" * 64
    elif change == "release": changed["release_id"] = "f" * 64
    elif change == "configuration": changed["configuration_id"] = "f" * 64
    elif change == "profile": changed["profile"] = "PAPER"
    elif change == "capability": changed["allowed_capabilities"].append("LIVE_ORDER")
    else: changed.pop("journal_root")
    with pytest.raises(Refused):
        RuntimeContract(changed, pin)


@pytest.mark.parametrize("resource", ["database", "volume", "port", "development", "state", "owner", "release", "capability"])
def test_invalid_layout_is_rejected_even_at_explicit_fixture_enrollment(fixture, resource):
    manifest, pin, *_ = fixture
    changed = copy.deepcopy(manifest)
    if resource == "database": changed["development"]["database_ids"] = [changed["database_id"]]
    elif resource == "volume": changed["development"]["volume_ids"] = changed["volume_ids"]
    elif resource == "port": changed["development"]["ports"] = [8000]
    elif resource == "development": changed["development"]["roots"][0] = changed["runtime_root"]
    elif resource == "state": changed["state_root"] = changed["release_root"]
    elif resource == "owner": changed["owner"]["created"] = True
    elif resource == "release": changed["release_id"] = "0" * 64
    else: changed["allowed_capabilities"] = ["LIVE_ORDER"]
    with pytest.raises(Refused):
        enroll_fixture(changed, Path(pin.scope_root), pin.scope_id)


@pytest.mark.parametrize("target", ["state_root", "release_root", "configuration_path"])
def test_path_replacement_is_detected_before_admission(fixture, target):
    manifest, _pin, _contract, _history, world, bootstrap = fixture
    path = Path(manifest[target])
    moved = path.with_name(path.name + "-original")
    path.rename(moved)
    if moved.is_dir(): path.mkdir()
    else: path.write_bytes(moved.read_bytes())
    assert bootstrap.evaluate().status == Status.BLOCKED
    assert world.effects == []


def test_runtime_content_or_configuration_drift_blocks_dispatch(fixture):
    manifest, *_rest, world, bootstrap = fixture
    runtime = bootstrap.start()
    (Path(manifest["release_root"]) / "version.py").write_bytes(b"VERSION = 999\n")
    with pytest.raises(Refused): runtime.execute(Action.RESEARCH)
    assert bootstrap.evaluate(continuing=True).status == Status.BLOCKED
    assert world.effects == []


def test_development_changes_do_not_change_fixed_code_or_assets(fixture):
    manifest, _pin, contract, _history, world, bootstrap = fixture
    runtime = bootstrap.start()
    workspace = DevelopmentWorkspace(contract)
    before = runtime.asset("version.py"), runtime.asset("assets/index.html")
    workspace.write(Path(manifest["development"]["roots"][0]) / "version.py", b"VERSION = 2\n")
    workspace.write(Path(manifest["development"]["roots"][3]) / "index.html", b"development-build")
    assert (runtime.asset("version.py"), runtime.asset("assets/index.html")) == before
    with pytest.raises(RuntimeError, match="synthetic dev failure"):
        raise RuntimeError("synthetic dev failure")
    assert world.runtime_alive is True
    assert runtime.release_id == manifest["release_id"]


@pytest.mark.parametrize("target", ["state_root", "journal_root", "build_root", "release_root", "environment_root"])
def test_development_writer_cannot_write_runtime_resources(fixture, target):
    manifest, _pin, contract, *_ = fixture
    destination = Path(manifest[target]) / "forbidden-output"
    with pytest.raises(Refused): DevelopmentWorkspace(contract).write(destination, b"forbidden")
    assert not destination.exists()


def test_hardlink_alias_is_not_an_independent_development_file(fixture):
    manifest, _pin, contract, *_ = fixture
    source = Path(manifest["release_root"]) / "version.py"
    target = Path(manifest["development"]["roots"][0]) / "alias.py"
    os.link(source, target)
    with pytest.raises(Refused): DevelopmentWorkspace(contract).write(target, b"overwrite")
    assert source.read_bytes() == b"VERSION = 1\n"


def test_promotion_never_changes_active_synthetic_release(fixture):
    _manifest, _pin, contract, history, world, bootstrap = fixture
    runtime = bootstrap.start()
    selection = NextStartupSelection()
    with pytest.raises(Refused): selection.select(contract, world, accepted=True, approved=True)
    assert runtime.release_id == contract.manifest["release_id"]
    runtime.stop()
    for accepted, approved in [(False, True), (True, False)]:
        with pytest.raises(Refused): selection.select(contract, world, accepted=accepted, approved=approved)
    selection.select(contract, world, accepted=True, approved=True)
    assert selection.next_manifest == contract.manifest
    assert history.verify()[-1]["event"] == "GRACEFUL_SHUTDOWN"


def test_history_records_start_identity_source_health_and_graceful_end(fixture):
    manifest, _pin, _contract, history, _world, bootstrap = fixture
    runtime = bootstrap.start()
    runtime.execute(Action.OBSERVE, source="synthetic-feed")
    runtime.health("READY")
    runtime.stop()
    rows = history.verify()
    assert [r["event"] for r in rows] == ["SESSION_START", "DATA_SOURCE", "HEALTH", "GRACEFUL_SHUTDOWN"]
    assert rows[0]["payload"]["release_id"] == manifest["release_id"]
    assert rows[0]["payload"]["profile"] == "OBSERVATION_ONLY"
    assert all(row["session_id"] == manifest["session_id"] for row in rows)
    assert all(row["observed_at"] == 1_790_000_000.0 for row in rows)


def test_unclean_session_blocks_restart_and_nonclearing_records_do_not_grant_startup(fixture):
    _manifest, _pin, contract, history, world, bootstrap = fixture
    bootstrap.start()
    before = history.path.read_bytes()
    restarted = SessionHistory(contract, history.pin)
    other = ObservationBootstrap(contract, restarted, world, bootstrap.attempt_id)
    assert other.evaluate().status == Status.BLOCKED
    history.append("INTERRUPTED", {"reason": "UNKNOWN_EXIT"}, str(uuid.uuid4()), observed_at=world.now)
    history.append("RECOVERY_REQUIRED", {"reason": "PROCESS_INTERRUPTED"}, str(uuid.uuid4()), observed_at=world.now)
    assert history.path.read_bytes().startswith(before)
    assert other.evaluate().status == Status.BLOCKED
    with pytest.raises(Refused): history.append("GRACEFUL_SHUTDOWN", {"outcome": "COMPLETE"}, str(uuid.uuid4()), observed_at=world.now)


def test_expired_shutdown_never_reports_complete(fixture):
    *_, history, world, bootstrap = fixture
    runtime = bootstrap.start()
    world.now += 6
    with pytest.raises(Refused): runtime.stop()
    assert world.runtime_alive is False
    assert [r["event"] for r in history.verify()][-2:] == ["INTERRUPTED", "RECOVERY_REQUIRED"]


def test_second_session_appends_and_preserves_first_session_bytes(fixture):
    manifest, pin, _contract, history, world, bootstrap = fixture
    bootstrap.start().stop()
    before = history.path.read_bytes()
    changed = copy.deepcopy(manifest)
    changed["session_id"] = str(uuid.uuid4())
    new_pin = enroll_fixture(changed, Path(pin.scope_root), pin.scope_id)
    contract = RuntimeContract(changed, new_pin)
    reopened = SessionHistory(contract, history.pin)
    attempt = str(uuid.uuid4())
    world.evidence = [Evidence(k, Status.ADMITTED, world.now, new_pin.manifest_id, attempt,
                               evidence_subject(changed, k)) for k in sorted(REQUIRED)]
    ObservationBootstrap(contract, reopened, world, attempt).start().stop()
    assert history.path.read_bytes().startswith(before)
    assert len({r["session_id"] for r in reopened.verify()}) == 2


def test_history_idempotent_replay_and_conflicting_replay(fixture):
    history, world, bootstrap = fixture[-3:]
    bootstrap.start()
    event_id = str(uuid.uuid4())
    first = history.append("HEALTH", {"state": "READY"}, event_id, observed_at=world.now)
    before = history.path.read_bytes()
    assert history.append("HEALTH", {"state": "READY"}, event_id, observed_at=world.now) == first
    with pytest.raises(Refused): history.append("HEALTH", {"state": "UNAVAILABLE"}, event_id, observed_at=world.now)
    assert history.path.read_bytes() == before


@pytest.mark.parametrize("fault", ["fsync", "partial", "write"])
def test_history_failure_preserves_evidence_and_refuses_retry(fixture, monkeypatch, fault):
    _manifest, _pin, contract, history, world, bootstrap = fixture
    bootstrap.start()
    original = OSError("synthetic history " + fault)
    actual_write = history_module.write_flushed

    def fail(handle, value):
        if fault == "partial":
            handle.write(value[:10])
            handle.flush()
        elif fault == "fsync":
            actual_write(handle, value)
        raise original

    monkeypatch.setattr(history_module, "write_flushed", fail)
    with pytest.raises(OSError) as failure:
        history.append("HEALTH", {"state": "READY"}, str(uuid.uuid4()), observed_at=world.now)
    assert failure.value is original
    before = history.path.read_bytes()
    with pytest.raises(OSError): history.verify()
    with pytest.raises(ValueError): SessionHistory(contract, history.pin)
    assert history.path.read_bytes() == before
    assert history.commitment.path.exists()


@pytest.mark.parametrize("fault", ["truncation", "corruption", "missing_witness", "replaced_witness"])
def test_history_integrity_failures_never_admit(fixture, fault):
    *_, history, _world, bootstrap = fixture
    bootstrap.start().stop()
    if fault == "truncation":
        raw = history.path.read_bytes()
        history.path.write_bytes(raw[:raw.rfind(b"\n", 0, -1) + 1])
    elif fault == "corruption":
        history.path.write_bytes(b"corrupt\n")
    elif fault == "missing_witness":
        history.commitment.path.rename(history.commitment.path.with_suffix(".retained"))
    else:
        path = history.commitment.path
        retained = path.with_suffix(".retained")
        path.rename(retained)
        path.write_bytes(retained.read_bytes())
    assert bootstrap.evaluate().status != Status.ADMITTED


def test_duplicate_start_never_creates_second_synthetic_runtime(fixture):
    *_, world, bootstrap = fixture
    bootstrap.start()
    with pytest.raises(Refused): bootstrap.start()
    assert world.runtime_alive is True
    assert len(bootstrap.history.verify()) == 1


@pytest.mark.parametrize("kind", ["ownership", "dependencies", "storage", "development_isolation"])
def test_wrong_observed_subject_is_blocked(fixture, kind):
    *_, world, bootstrap = fixture
    world.evidence = [dataclasses.replace(f, subject_id="0" * 64) if f.kind == kind else f for f in world.evidence]
    assert bootstrap.evaluate().status == Status.BLOCKED
    assert world.effects == []


@pytest.mark.parametrize("candidate", [None, {}, [], {"scope": "PRODUCTION"}])
def test_raw_candidate_evaluator_reports_refusal_without_initializing(fixture, candidate):
    _manifest, pin, _contract, history, world, bootstrap = fixture
    before = history.path.read_bytes()
    result = evaluate_candidate(candidate, pin, history, world, bootstrap.attempt_id)
    assert result.status != Status.ADMITTED
    assert result.production_start_authorized is False
    assert history.path.read_bytes() == before


def test_startup_rechecks_evidence_after_durable_intent(fixture, monkeypatch):
    *_, history, world, bootstrap = fixture
    actual_append = history.append

    def delayed(*args, **kwargs):
        result = actual_append(*args, **kwargs)
        world.now += 6
        return result

    monkeypatch.setattr(history, "append", delayed)
    with pytest.raises(Refused): bootstrap.start()
    assert not world.runtime_alive
    assert world.effects == []
    assert history.verify()[-1]["event"] == "SESSION_START"
    assert bootstrap.evaluate().status == Status.BLOCKED


def test_slow_handler_cannot_acknowledge_stale_result(fixture, monkeypatch):
    *_, world, bootstrap = fixture
    runtime = bootstrap.start()
    actual = world.perform

    def delayed(action, source):
        result = actual(action, source)
        world.now += 6
        return result

    monkeypatch.setattr(world, "perform", delayed)
    with pytest.raises(Refused): runtime.execute(Action.OBSERVE, source="synthetic-feed")
    assert len(world.effects) == 1  # A request may have begun; no result was acknowledged.
    assert len(bootstrap.history.verify()) == 1


def test_unapproved_external_world_is_rejected(fixture):
    _manifest, _pin, contract, history, _world, bootstrap = fixture
    with pytest.raises(Refused): ObservationBootstrap(contract, history, object(), bootstrap.attempt_id)


def test_configuration_change_never_admits(fixture):
    manifest, *_, bootstrap = fixture
    Path(manifest["configuration_path"]).write_bytes(b'{"changed":true}\n')
    assert bootstrap.evaluate().status == Status.BLOCKED


def test_manifest_view_is_not_a_mutable_capability_override(fixture):
    _manifest, _pin, contract, _history, _world, bootstrap = fixture
    view = contract.manifest
    view["allowed_capabilities"].append("PAPER_ORDER")
    runtime = bootstrap.start()
    with pytest.raises(Refused): runtime.execute(Action.PAPER_ORDER)


def test_environment_mutation_refuses_continuing_execution(fixture):
    manifest, *_, bootstrap = fixture
    runtime = bootstrap.start()
    (Path(manifest["environment_root"]) / "dependency.lock").write_bytes(b"unexpected dependency")
    with pytest.raises(Refused): runtime.execute(Action.RESEARCH)


def test_development_write_failure_cannot_stop_synthetic_runtime(fixture, monkeypatch):
    manifest, _pin, contract, _history, world, bootstrap = fixture
    runtime = bootstrap.start()
    destination = Path(manifest["development"]["roots"][0]) / "failed-build.py"
    actual = Path.open

    def failure(path, *args, **kwargs):
        if path == destination:
            raise OSError("synthetic development failure")
        return actual(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", failure)
    with pytest.raises(OSError): DevelopmentWorkspace(contract).write(destination, b"failed")
    assert world.runtime_alive is True
    assert runtime.execute(Action.RESEARCH)["release_id"] == manifest["release_id"]


def test_candidate_selection_only_affects_a_later_startup(fixture):
    manifest, pin, _contract, history, world, bootstrap = fixture
    running = bootstrap.start()
    changed = copy.deepcopy(manifest)
    new_release = Path(manifest["release_root"]).with_name("next-candidate")
    (new_release / "assets").mkdir(parents=True)
    (new_release / "version.py").write_bytes(b"VERSION = 2\n")
    (new_release / "assets" / "index.html").write_bytes(b"next-assets")
    changed.update(release_root=str(new_release), build_root=str(new_release / "assets"),
                   release_id=digest(release_tree(new_release)[0]), session_id=str(uuid.uuid4()))
    changed["owner"]["run_id"] = str(uuid.uuid4())
    candidate_pin = enroll_fixture(changed, Path(pin.scope_root), pin.scope_id)
    candidate = RuntimeContract(changed, candidate_pin)
    selection = NextStartupSelection()
    with pytest.raises(Refused): selection.select(candidate, world, accepted=True, approved=True)
    assert running.asset("version.py") == b"VERSION = 1\n"
    running.stop()
    previous = history.path.read_bytes()
    selection.select(candidate, world, accepted=True, approved=True)
    assert running.release_id == manifest["release_id"]
    reopened = SessionHistory(candidate, history.pin)
    attempt = str(uuid.uuid4())
    world.evidence = [Evidence(k, Status.ADMITTED, world.now, candidate_pin.manifest_id, attempt,
                               evidence_subject(changed, k)) for k in sorted(REQUIRED)]
    subsequent = ObservationBootstrap(candidate, reopened, world, attempt).start()
    assert subsequent.asset("version.py") == b"VERSION = 2\n"
    assert subsequent.release_id != running.release_id
    assert history.path.read_bytes().startswith(previous)


def test_concurrent_history_writer_refuses_without_losing_committed_rows(fixture, monkeypatch):
    _manifest, _pin, contract, history, world, bootstrap = fixture
    bootstrap.start()
    other = SessionHistory(contract, history.pin)
    entered, release = threading.Event(), threading.Event()
    actual = history.commitment.prepare
    failures = []

    def paused(raw):
        entered.set()
        if not release.wait(3):
            raise TimeoutError("synthetic test coordination")
        return actual(raw)

    monkeypatch.setattr(history.commitment, "prepare", paused)

    def writer():
        try:
            history.append("HEALTH", {"state": "READY"}, str(uuid.uuid4()), observed_at=world.now)
        except (OSError, ValueError) as error:
            failures.append(error)

    worker = threading.Thread(target=writer)
    worker.start()
    try:
        assert entered.wait(3)
        with pytest.raises(Refused):
            other.append("HEALTH", {"state": "DEGRADED"}, str(uuid.uuid4()), observed_at=world.now)
    finally:
        release.set()
        worker.join(timeout=3)
    assert not worker.is_alive()
    assert failures == []
    assert [row["event"] for row in history.verify()] == ["SESSION_START", "HEALTH"]


def test_existing_history_cannot_be_reinitialized(fixture):
    _manifest, _pin, contract, history, _world, bootstrap = fixture
    bootstrap.start().stop()
    before = history.path.read_bytes()
    with pytest.raises(Refused): SessionHistory.create_fixture(contract)
    assert history.path.read_bytes() == before


def test_import_is_inert_and_never_loads_paper_or_main(tmp_path):
    root = Path(__file__).resolve().parents[1]
    import app

    backend = Path(app.__file__).resolve().parent.parent
    code = r'''
import os,sys
sys.dont_write_bytecode=True
sys.path[:0]=[sys.argv[1],sys.argv[2]]
def guard(event,args):
    if event in ('socket.connect','subprocess.Popen'):raise PermissionError('No network/lifecycle')
    if event=='open':
        mode=args[1];flags=args[2]
        if (isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            raise PermissionError('Import must not write')
sys.addaudithook(guard)
import scripts.observation_runtime.bootstrap
assert not any(x in sys.modules for x in ['app.main','app.services.paper_journal','app.services.perp_manual_service','app.prediction.paper_engine'])
print('INERT_IMPORT_NO_PRODUCTION_BOOTSTRAP')
'''
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(root), str(backend)],
                            capture_output=True, text=True, check=False, timeout=15, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "INERT_IMPORT_NO_PRODUCTION_BOOTSTRAP" in result.stdout
