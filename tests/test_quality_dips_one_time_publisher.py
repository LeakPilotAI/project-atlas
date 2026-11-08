"""Synthetic authority models and confined native files, never operational enrollment."""

import copy
import importlib.util
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.investment import quality_dips_operational_contract as c
from test_quality_dips_native_operational_reader import (
    composition,
    reader_module,
    service_module,
)
from test_quality_dips_operational_contract import fixture

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    s = importlib.util.spec_from_file_location(name, ROOT / path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


p = load(
    "one_time_publisher",
    "scripts/observation_runtime/quality_dips_one_time_publisher.py",
)
b = load(
    "publisher_bootstrap",
    "scripts/observation_runtime/quality_dips_enrollment_bootstrap.py",
)


def make(path, reuse=False):
    allowed = Path(os.environ["ATLAS_PUBLISHER_TEST_ROOT"])
    assert (
        allowed.parent == ROOT / "logs/diagnostics"
        and allowed.name.startswith("qd-publisher-")
        and path.is_relative_to(allowed)
    )
    if not reuse:
        path.mkdir()
    n = SimpleNamespace(
        now=100,
        available=True,
        accepted=True,
        healthy=True,
        owned=True,
        fail=None,
        crash=None,
        writes=0,
        path=path,
    )
    x = fixture()
    n.e = x.e
    n.expected = copy.deepcopy(x.b)
    n.process = service_module.observe_self()
    for role in c.ROLES:
        with (
            reader_module.s.w.WindowsOutput(str(path / role))
            if reuse
            else reader_module.s.w.WindowsOutput.create_root(str(path / role))
        ) as out:
            n.e["resources"][role].update(
                root_path=str(path / role),
                native_root=reader_module.s.native.file_identity(out.root_handle),
            )
    n.expected["session"]["process"] = {"schema": "QD_OP_PROCESS_ID_V1", **n.process}
    n.expected["session"]["enrollment_digest"] = c.digest(n.e)

    def refresh(current):
        n.expected["current"] = copy.deepcopy(current)
        n.expected["authority"].update(
            enrollment_digest=c.digest(n.e),
            current_digest=c.digest(current),
            clock_digest=c.digest(n.expected["clock"]),
            session_digest=c.digest(n.expected["session"]),
        )

    @contextmanager
    def read_authority(e, now):
        assert c.body(e) == c.body(n.e)
        value = copy.deepcopy(n.expected)
        yield SimpleNamespace(
            snapshot=value,
            check=lambda v, t: n.healthy and c.body(v) == c.body(n.expected),
        )

    n.authority = SimpleNamespace(lease=read_authority)
    n.port = reader_module.NativeOperationalReadPort(
        authority=n.authority,
        clock=lambda: n.now,
        observer=service_module.observe_self,
        host_identity=lambda: n.expected["session"]["host_id"],
    )
    service = composition(n)
    ledger = path / "test-custody.jsonl"

    def entries():
        return (
            [json.loads(line) for line in ledger.read_text().splitlines()]
            if ledger.exists()
            else []
        )

    def append(row, exclusive=False):
        with ledger.open("x" if exclusive else "a") as f:
            f.write(c.body(row) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def phase():
        return entries()[-1]["state"] if entries() else "UNPUBLISHED"

    def witness():
        rows = entries()
        state = phase()
        ack = rows[-1] if state == "ACKNOWLEDGED" else None
        return {
            "schema": "QD_OP_PUBLICATION_WITNESS_V1",
            "intent_digest": c.digest(n.intent),
            "operation_id": n.intent["operation_id"],
            "resources_digest": n.intent["resources_digest"],
            "state": state
            if state in ("UNPUBLISHED", "ACKNOWLEDGED", "PENDING")
            else "UNKNOWN",
            "ack_id": "SYNTHETIC_ACK" if ack else None,
            "current_digest": ack["current_digest"] if ack else None,
            "acknowledged_at": 100 if ack else None,
        }

    @contextmanager
    def issuer(scope, now):
        yield SimpleNamespace(
            check=lambda v, t: (
                n.accepted and c.body(v) == c.body(n.intent) and 100 <= t <= 130
            )
        )

    @contextmanager
    def publication(scope, now):
        value = witness()
        yield SimpleNamespace(
            snapshot=value,
            check=lambda v, t: n.healthy and c.body(v) == c.body(witness()),
        )

    n.bootstrap = b.EnrollmentBootstrap(
        enrollment=n.e,
        release={
            "schema": "QD_OP_ENROLLMENT_RELEASE_V1",
            "sha256": "a" * 64,
            "executable": n.process["image"],
        },
        issuer=SimpleNamespace(lease=issuer),
        publication=SimpleNamespace(lease=publication),
        clock=lambda: n.now,
        composition=service,
    )
    n.intent = n.bootstrap._scope()

    @contextmanager
    def ownership(context, now):
        yield SimpleNamespace(
            check=lambda v, t: (
                n.owned
                and v == context
                and context["process"]
                == {"schema": "QD_OP_PROCESS_ID_V1", **service_module.observe_self()}
            )
        )

    class Transaction:
        snapshot = None

        def check(self, snapshot, t):
            return n.healthy and snapshot == self.snapshot

        def commit(self, current, now):
            if n.crash == "before_commit":
                os._exit(71)
            if n.fail == "commit":
                raise OSError("TEST_COMMIT_FAILURE")
            append({"state": "COMMITTED", "current": current})
            refresh(current)
            if n.crash == "after_commit":
                os._exit(72)
            return {
                "schema": "QD_OP_GENESIS_COMMIT_V1",
                "operation_id": n.intent["operation_id"],
                "intent_digest": c.digest(n.intent),
                "current_digest": c.digest(current),
                "state": "COMMITTED",
            }

        def acknowledge(self, commit, now):
            if n.fail == "ack":
                raise OSError("TEST_ACK_FAILURE")
            append(
                {"state": "ACKNOWLEDGED", "current_digest": commit["current_digest"]}
            )
            if n.crash == "after_ack":
                os._exit(73)
            return witness()

        def mark_unknown(self, reason):
            if n.fail == "unknown_marker":
                raise OSError("TEST_UNKNOWN_PERSISTENCE_FAILURE")
            append({"state": "UNKNOWN", "reason": reason})

    @contextmanager
    def reserve(scope, writer, now):
        assert c.body(scope) == c.body(n.intent)
        txn = Transaction()
        txn.snapshot = {
            "schema": "QD_OP_GENESIS_PENDING_V1",
            "operation_id": scope["operation_id"],
            "intent_digest": c.digest(scope),
            "writer_digest": c.digest(writer),
            "state": "PENDING",
            "pending_durable": True,
        }
        if n.fail == "reservation":
            txn.snapshot["pending_durable"] = False
        append({"state": "PENDING", "reservation": txn.snapshot}, exclusive=True)
        yield txn

    class Files:
        @contextmanager
        def open(self, e):
            with p.NativeGenesisFiles().open(e) as native:

                class Wrapped:
                    def write(self, role, name, value):
                        n.writes += 1
                        if n.fail == role or n.fail == "unknown_marker":
                            raise OSError("TEST_PARTIAL_WRITE")
                        result = native.write(role, name, value)
                        if n.fail == "clock":
                            n.now = 99
                        if n.fail == "rollback":
                            n.healthy = False
                        if n.fail == "issuer":
                            n.accepted = False
                        if n.fail == "process":
                            n.owned = False
                        return result

                    def verify(self):
                        return native.verify()

                yield Wrapped()

    for entry in entries():
        if "current" in entry:
            refresh(entry["current"])
    n.bootstrap.publication.reserve = reserve
    n.publisher = p.OneTimePublisher(
        bootstrap=n.bootstrap,
        custody=n.bootstrap.publication,
        ownership=SimpleNamespace(lease=ownership),
        observer=lambda: {
            "schema": "QD_OP_PROCESS_ID_V1",
            **service_module.observe_self(),
        },
        files=Files(),
    )
    n.entries, n.phase, n.ledger = entries, phase, ledger
    return n


@pytest.fixture
def native(tmp_path):
    return make(tmp_path / "synthetic")


def test_native_genesis_and_existing_bootstrap(native):
    n = native
    ready = n.publisher.publish()
    assert ready["source_revision"] == 0 and ready["commands_enabled"] is False
    assert n.phase() == "ACKNOWLEDGED" and [x["state"] for x in n.entries()] == [
        "PENDING",
        "COMMITTED",
        "ACKNOWLEDGED",
    ]
    view = n.bootstrap.composition.preflight()
    assert view["state"]["cash"] == "1000" and view["state"]["positions"] == {}
    assert all(view["state"][k] == "0" for k in ("gross", "costs", "net"))
    assert view["report_status"] == "INCOMPLETE"
    assert n.bootstrap.verify_publication() == ready
    with pytest.raises(ValueError):
        n.publisher.publish()
    assert n.writes == 3


@pytest.mark.parametrize(
    "missing", ["bootstrap", "custody", "ownership", "observer", "files"]
)
def test_missing_dependencies_refuse(missing):
    args = {
        "bootstrap": object(),
        "custody": object(),
        "ownership": object(),
        "observer": object(),
        "files": object(),
    }
    args[missing] = None
    with pytest.raises(ValueError):
        p.OneTimePublisher(**args)


@pytest.mark.parametrize("damage", ["issuer", "owner", "stale", "rollback", "conflict"])
def test_no_authority_no_publication(native, damage):
    n = native
    if damage == "issuer":
        n.accepted = False
    if damage == "owner":
        n.owned = False
    if damage == "stale":
        n.now = 131
    if damage == "rollback":
        n.healthy = False
    if damage == "conflict":
        n.bootstrap.release["sha256"] = "b" * 64
    with pytest.raises(ValueError):
        n.publisher.publish()
    assert not n.ledger.exists() and n.writes == 0


@pytest.mark.parametrize(
    "failure",
    [
        "source",
        "projection",
        "report",
        "commit",
        "ack",
        "clock",
        "rollback",
        "issuer",
        "process",
    ],
)
def test_partial_failure_unknown_no_recovery(native, failure):
    n = native
    n.fail = failure
    with pytest.raises(p.PublicationUnknown):
        n.publisher.publish()
    assert n.phase() == "UNKNOWN"
    n.fail = None
    n.now = 100
    n.accepted = n.healthy = n.owned = True
    before = {str(x): x.read_bytes() for x in n.path.rglob("*.json")}
    with pytest.raises(ValueError):
        n.publisher.publish()
    assert before == {str(x): x.read_bytes() for x in n.path.rglob("*.json")}


@pytest.mark.parametrize("damage", ["legacy", "resource", "corrupt_acl"])
def test_existing_or_foreign_resource_refuses(native, damage):
    n = native
    if damage == "legacy":
        (n.path / "source/legacy.json").write_text("{}")
    if damage == "resource":
        n.e["resources"]["source"]["native_root"][2] += 1
    if damage == "corrupt_acl":
        # Existing broad parent is never a valid protected financial source root.
        n.e["resources"]["source"]["root_path"] = str(n.path)
    if damage != "legacy":
        n.bootstrap.enrollment = copy.deepcopy(n.e)
        n.bootstrap.composition.enrollment = copy.deepcopy(n.e)
        n.intent = n.bootstrap._scope()
    with pytest.raises(p.PublicationUnknown):
        n.publisher.publish()
    assert n.writes == 0 and n.phase() == "UNKNOWN"


@pytest.mark.parametrize(
    "phase,exitcode", [("before_commit", 71), ("after_commit", 72), ("after_ack", 73)]
)
def test_abrupt_publication_restart_no_replay(tmp_path, phase, exitcode):
    path = tmp_path / "crash"
    code = "from pathlib import Path;from test_quality_dips_one_time_publisher import make;n=make(Path(__import__('sys').argv[1]));n.crash=__import__('sys').argv[2];n.publisher.publish()"
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "backend")
        + ";"
        + str(ROOT / "tests")
        + ";"
        + str(ROOT / "backend/.venv/Lib/site-packages"),
    }
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, str(path), phase],
        env=env,
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )
    assert result.returncode == exitcode, result.stderr
    n = make(path, reuse=True)
    before = {str(p): p.read_bytes() for p in path.rglob("*") if p.is_file()}
    with pytest.raises(ValueError):
        n.publisher.publish()
    assert before == {str(p): p.read_bytes() for p in path.rglob("*") if p.is_file()}
    if phase == "after_ack":
        assert n.bootstrap.verify_publication()["source_revision"] == 0
    else:
        with pytest.raises(ValueError):
            n.bootstrap.verify_publication()


def test_concurrent_requests_have_one_reservation_and_three_files(native):
    from concurrent.futures import ThreadPoolExecutor

    n = native

    def attempt(_):
        try:
            return n.publisher.publish()
        except (ValueError, FileExistsError):
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sum(r is not None for r in results) == 1 and n.writes == 3
    assert [x["state"] for x in n.entries()] == ["PENDING", "COMMITTED", "ACKNOWLEDGED"]


def test_clock_rollback_inside_freshness_window_refuses(native):
    n = native
    count = 0

    def changed():
        nonlocal count
        count += 1
        return 100 if count < 6 else (110 if count == 6 else 105)

    n.bootstrap.clock = changed
    with pytest.raises(ValueError):
        n.publisher.publish()
    assert n.phase() in ("UNPUBLISHED", "UNKNOWN")
    assert n.writes < 3


def test_interrupted_reservation_acknowledgement_is_unknown(native):
    n = native
    original = n.publisher.custody.reserve

    @contextmanager
    def uncertain(*args):
        with original(*args):
            raise OSError("PENDING_PERSISTED_ACK_LOST")
            yield

    n.publisher.custody.reserve = uncertain
    with pytest.raises(p.PublicationUnknown):
        n.publisher.publish()
    assert n.phase() == "PENDING" and n.writes == 0
    with pytest.raises(ValueError):
        n.publisher.publish()


def test_cli_has_no_default_authority(tmp_path):
    env = {**os.environ, "PYTHONPATH": str(ROOT / "backend")}
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT / "scripts/observation_runtime/quality_dips_one_time_publisher.py"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0 and "REFUSED" in result.stderr


def test_unacknowledged_pending_reservation_blocks_first_write(native):
    n = native
    n.fail = "reservation"
    with pytest.raises(p.PublicationUnknown):
        n.publisher.publish()
    assert n.writes == 0 and n.phase() == "UNKNOWN"


def test_unknown_persistence_failure_preserves_original_exception(native):
    n = native
    n.fail = "unknown_marker"
    with pytest.raises(p.PublicationUnknown) as caught:
        n.publisher.publish()
    assert "TEST_UNKNOWN_PERSISTENCE_FAILURE" in str(caught.value.__cause__)
    assert "TEST_PARTIAL_WRITE" in str(caught.value.__cause__.__context__)
    assert n.phase() == "PENDING"
    with pytest.raises(ValueError):
        n.publisher.publish()


def test_split_publication_custody_refuses_before_effects(native):
    n = native
    with pytest.raises(ValueError, match="CUSTODY_MUST_MATCH"):
        p.OneTimePublisher(
            bootstrap=n.bootstrap,
            custody=object(),
            ownership=object(),
            observer=object(),
            files=object(),
        )
    assert n.writes == 0 and not n.ledger.exists()
