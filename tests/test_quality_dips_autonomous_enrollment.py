"""Synthetic authorities only; no real account or operational dependency installed."""

import copy
import importlib.util
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import body, digest
from app.services.quality_dips_autonomous_enrollment import (
    ROLES,
    WRITERS,
    AutonomousNativeEnrollment,
    publication_intent,
    validate_enrollment,
)


def fixture():
    now = [1000]
    e = {
        "schema": "QD_AUTO_NATIVE_ENROLLMENT_V4",
        "profile": "AUTONOMOUS_PAPER_ONLY_V1",
        "account_id": "SYNTHETIC-ACCOUNT",
        "epoch": "SYNTHETIC-EPOCH",
        "policy_digest": "a" * 64,
        "inception_digest": "b" * 64,
        "release_digest": "c" * 64,
        "acceptance_id": "SYNTHETIC-NOT-ACCEPTED-OPERATIONALLY",
        "clock_source": "SYNTHETIC-CLOCK",
        "resources": {
            r: {
                "schema": "QD_AUTO_NATIVE_ROOT_V4",
                "path": "D:\\synthetic-test\\" + r,
                "native_id": [1, i, 0],
            }
            for i, r in enumerate(ROLES)
        },
        "writers": {
            r: {
                "schema": "QD_OP_PROCESS_ID_V1",
                "pid": 1,
                "creation_filetime": 1,
                "image": "D:\\synthetic.exe",
            }
            for r in WRITERS
        },
    }
    g = {
        "schema": "QD_AUTO_NATIVE_SESSION_V4",
        "session_id": "SYNTHETIC-SESSION",
        "enrollment_digest": digest(e),
        "issued_at": 999,
        "expires_at": 1100,
        "capabilities": ["AUTO_PAPER"],
    }
    flags = {"valid": True, "native": True, "clock": True}
    a = {
        "schema": "QD_AUTO_NATIVE_ACCEPTANCE_V4",
        "request_digest": None,
        "scope": "DISPOSABLE_TEST",
        "acceptance_id": e["acceptance_id"],
        "profile": e["profile"],
        "gates": dict.fromkeys(("B1", "C1", "D1", "E1"), "ACCEPTED"),
        "revoked": False,
        "issued_at": 999,
        "expires_at": 1029,
    }
    o = {
        "schema": "QD_AUTO_NATIVE_OWNERSHIP_V4",
        "request_digest": None,
        "writers": copy.deepcopy(e["writers"]),
        "resources": copy.deepcopy(e["resources"]),
        "unknown_writers": [],
    }
    c = {
        "schema": "QD_AUTO_NATIVE_CURRENT_V4",
        "request_digest": None,
        "scope": "DISPOSABLE_TEST",
        "revision": 0,
        "acknowledged_revision": 0,
        "high_water": 0,
        "generation": 1,
        "financial_digest": "d" * 64,
        "publication_ack": "SYNTHETIC-ACK",
        "status": "ACKNOWLEDGED",
        "observed_at": 1000,
        "expires_at": 1005,
    }
    intent = publication_intent(e)
    c["publication"] = {
        "schema": "QD_AUTO_NATIVE_PUBLICATION_V4",
        "intent_digest": digest(intent),
        "operation_id": intent["operation_id"],
        "status": "ACKNOWLEDGED",
        "ack_id": c["publication_ack"],
    }

    class Authority:
        def __init__(self, data):
            self.data = data

        @contextmanager
        def lease(self, request, stamp):
            data = {**self.data, "request_digest": digest(request)}
            yield SimpleNamespace(snapshot=data, check=lambda v, t: flags["valid"])

    class Clock:
        def sample(self):
            return {
                "schema": "QD_AUTO_NATIVE_CLOCK_V4",
                "utc": now[0],
                "monotonic_ns": (now[0] - 999) * 10**9,
                "uncertainty_ms": 0,
                "source": e["clock_source"],
            }

        def verify(self, s):
            return flags["clock"]

    class Sessions:
        def __init__(self):
            self.used = set()

        def reserve(self, request):
            identity = request["grant"]["session_id"]
            if identity in self.used:
                raise ValueError("DURABLE_SESSION_REPLAY")
            self.used.add(identity)
            return {
                "schema": "QD_AUTO_NATIVE_SESSION_RESERVATION_V4",
                "request_digest": digest(request),
                "status": "ACKNOWLEDGED",
            }

        def verify(self, request, receipt):
            return request["grant"]["session_id"] in self.used

    sessions = Sessions()
    deps = {
        "enrollment": e,
        "acceptance": Authority(a),
        "ownership": Authority(o),
        "custody": Authority(c),
        "clock": Clock(),
        "native": SimpleNamespace(verify=lambda *args, **kwargs: flags["native"]),
        "sessions": sessions,
        "scope": "DISPOSABLE_TEST",
    }
    adapter = AutonomousNativeEnrollment(**deps)
    return SimpleNamespace(**locals())


def test_default_refusal():
    with pytest.raises(ValueError, match="DEPENDENCIES"):
        AutonomousNativeEnrollment()


def test_valid_lease_and_no_implicit_session_resume():
    s = fixture()
    with s.adapter.admitted(s.g) as request:
        assert request["scope"] == "DISPOSABLE_TEST"
    assert not s.sessions.used
    assert s.adapter.reserve_session(s.g)["status"] == "ACKNOWLEDGED"
    restarted = AutonomousNativeEnrollment(**s.deps)
    with pytest.raises(ValueError, match="REPLAY"):
        restarted.reserve_session(s.g)


@pytest.mark.parametrize(
    "target,key,value",
    [
        ("a", "scope", "LOCAL_ENROLLED"),
        ("a", "revoked", True),
        ("a", "profile", "LOCAL_SUPERVISED_PAPER_V1"),
        ("a", "expires_at", 998),
        ("a", "gates", {"B1": "BLOCKED"}),
        ("a", "acceptance_id", "foreign"),
        ("c", "schema", "FS2_TEST_PIN_V1"),
        ("c", "status", "UNKNOWN"),
        ("c", "status", "PENDING"),
        ("c", "high_water", 1),
        ("c", "acknowledged_revision", 1),
        ("c", "revision", False),
        ("c", "financial_digest", "bad"),
        ("c", "publication_ack", None),
        ("c", "observed_at", 1001),
        ("c", "expires_at", 999),
        ("c", "expires_at", 1006),
        ("c", "scope", "LOCAL_ENROLLED"),
        ("o", "unknown_writers", ["foreign"]),
        ("o", "writers", {}),
        ("o", "resources", {}),
    ],
)
def test_unaccepted_bundle_refuses_before_action(target, key, value):
    s = fixture()
    getattr(s, target)[key] = value
    with pytest.raises((ValueError, TypeError)), s.adapter.admitted(s.g):
        pytest.fail("unverified evidence reached action")


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema", "QD_AUTO_SESSION_FIXTURE_V1"),
        ("enrollment_digest", "e" * 64),
        ("expires_at", 1000),
        ("expires_at", 999999),
        ("issued_at", True),
        ("capabilities", ["MANUAL"]),
        ("session_id", None),
    ],
)
def test_bad_grant(key, value):
    s = fixture()
    s.g[key] = value
    with pytest.raises((ValueError, TypeError)), s.adapter.admitted(s.g):
        pytest.fail("bad grant reached action")


@pytest.mark.parametrize(
    "damage",
    [
        "foreign_drive",
        "alias",
        "nested",
        "traversal",
        "extra_writer",
        "manual",
        "missing_root",
    ],
)
def test_enrollment_identity_validation(damage):
    e = fixture().e
    if damage == "foreign_drive":
        e["resources"]["source"]["path"] = "C:\\account"
    if damage == "alias":
        e["resources"]["source"] = e["resources"]["report"]
    if damage == "nested":
        e["resources"]["report"]["path"] = e["resources"]["source"]["path"] + "\\child"
    if damage == "traversal":
        e["resources"]["source"]["path"] = "D:\\x\\..\\y"
    if damage == "extra_writer":
        e["writers"]["foreign"] = e["writers"]["source"]
    if damage == "manual":
        e["schema"] = "QD_OP_ENROLLMENT_V1"
    if damage == "missing_root":
        del e["resources"]["custody"]
    with pytest.raises(ValueError):
        validate_enrollment(e)


@pytest.mark.parametrize("flag", ["clock", "native", "valid"])
def test_unverified_dependencies(flag):
    s = fixture()
    s.flags[flag] = False
    with pytest.raises(ValueError), s.adapter.admitted(s.g):
        pytest.fail("unverified dependency")


def test_fixture_authority_cannot_authenticate_default_operational_scope():
    s = fixture()
    deps = {k: v for k, v in s.deps.items() if k != "scope"}
    with (
        pytest.raises(ValueError, match="PROFILE_NOT_ACCEPTED"),
        AutonomousNativeEnrollment(**deps).admitted(s.g),
    ):
        pytest.fail("fixture became operational")


@pytest.mark.parametrize("change", ["revoked", "clock", "native", "expiry"])
def test_continuity_after_action(change):
    s = fixture()
    with pytest.raises(ValueError), s.adapter.admitted(s.g):
        if change == "revoked":
            s.flags["valid"] = False
        if change == "clock":
            s.now[0] -= 1
        if change == "native":
            s.flags["native"] = False
        if change == "expiry":
            s.now[0] += 30


def test_rollback_and_same_generation_conflict():
    s = fixture()
    s.c.update(revision=2, high_water=2, acknowledged_revision=2, generation=3)
    with s.adapter.admitted(s.g):
        pass
    for changes in (
        {"revision": 1, "high_water": 1, "acknowledged_revision": 1},
        {"financial_digest": "f" * 64},
        {"generation": 2},
    ):
        old = copy.deepcopy(s.c)
        s.c.update(changes)
        with (
            pytest.raises(ValueError, match="ROLLBACK_OR_CONFLICT"),
            s.adapter.admitted(s.g),
        ):
            pytest.fail("rollback")
        s.c.update(old)


def test_ambiguous_reservation_not_replayed():
    s = fixture()
    reserve = s.sessions.reserve

    def interrupted(request):
        reserve(request)
        raise ValueError("COMMIT_BEFORE_ACK_UNKNOWN")

    s.sessions.reserve = interrupted
    with pytest.raises(ValueError, match="UNKNOWN"):
        s.adapter.reserve_session(s.g)
    s.sessions.reserve = reserve
    with pytest.raises(ValueError, match="REPLAY"):
        s.adapter.reserve_session(s.g)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "QD_OP_PUBLICATION_WITNESS_V1"),
        ("status", "UNKNOWN"),
        ("status", "PENDING"),
        ("intent_digest", "f" * 64),
        ("operation_id", "foreign"),
        ("ack_id", "unacknowledged"),
    ],
)
def test_publication_witness_is_exact_autonomous_intent(field, value):
    s = fixture()
    s.c["publication"][field] = value
    with pytest.raises(ValueError), s.adapter.admitted(s.g):
        pytest.fail("publication witness accepted")


def test_clock_jump_and_mutable_input_cannot_change_bound_enrollment():
    s = fixture()
    s.e["epoch"] = "caller-substituted"
    assert s.adapter.enrollment["epoch"] == "SYNTHETIC-EPOCH"
    with s.adapter.admitted(s.g):
        pass
    original = s.deps["clock"].sample
    s.deps["clock"].sample = lambda: {**original(), "utc": 1005}
    with pytest.raises(ValueError, match="DISCONTINUITY"), s.adapter.admitted(s.g):
        pytest.fail("clock jump")


def test_concurrent_single_use_reservation():
    s = fixture()

    def attempt(_):
        try:
            return s.adapter.reserve_session(s.g)["status"]
        except ValueError:
            return "REFUSED"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == ["ACKNOWLEDGED", "REFUSED"]


def test_enrollment_adapter_wraps_existing_v3_without_promoting_its_scope(tmp_path):
    value = os.environ.get("ATLAS_AUTO_RUNTIME_ROOT")
    if not value:
        pytest.skip("NOT EXECUTED: existing V3 confined root required")
    from qd_autonomous_runtime_fixture import compose
    from test_quality_dips_autonomous_paper import STAMP

    root = Path(value)
    assert tmp_path.is_relative_to(root)
    runtime = compose(tmp_path, root, stamp=STAMP)
    s = fixture()
    try:
        # Synthetic enrollment acceptance is a separate outer lease. Existing
        # V3 remains explicitly disposable and still verifies its own authorities.
        with s.adapter.admitted(s.g):
            assert runtime.runtime.start(runtime.grant) == "RUNNING"
            runtime.n.now[0] += 1
            assert runtime.runtime.accept(runtime.frame(1))["filled"]
        s.flags["valid"] = False
        revision = runtime.n.engine.reconcile()["source_revision"]
        with pytest.raises(ValueError), s.adapter.admitted(s.g):
            runtime.runtime.accept(runtime.frame(2, "partial"))
        assert runtime.n.engine.reconcile()["source_revision"] == revision
        assert runtime.runtime.enrollment["scope"] == "DISPOSABLE"
    finally:
        runtime.runtime.stop()
        runtime.x.close()


@pytest.fixture
def native_system(tmp_path):
    value = os.environ.get("ATLAS_AUTO_ENROLLMENT_ROOT")
    if not value:
        pytest.skip("NOT EXECUTED: confined native enrollment root required")
    root = Path(value)
    repo = Path(__file__).resolve().parents[1]
    assert root.parent == repo / "logs/diagnostics" and root.name.startswith(
        "qd-auto-enrollment-"
    )
    tmp_path = root / "native" / uuid.uuid4().hex / tmp_path.name
    assert tmp_path.is_relative_to(root)
    spec = importlib.util.spec_from_file_location(
        "test_auto_bound_enrollment",
        repo / "scripts/volume_inspector/autonomous_enrollment_read.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    f = fixture()
    outputs, resources = {}, {}
    tmp_path.mkdir(parents=True, exist_ok=True)
    try:
        for role in ROLES:
            out = module.s.w.WindowsOutput.create_root(str(tmp_path / role))
            outputs[role] = out
            f.e["resources"][role].update(
                path=str(out.root),
                native_id=module.s.native.file_identity(out.root_handle),
            )
            resources[role] = {}
        doc = {
            "schema": "QD_AUTO_NATIVE_AUDIT_FIXTURE_V4",
            "purpose": "SYNTHETIC_NOT_FINANCIAL_AUTHORITY",
        }
        binding = outputs["source"].write_bound("audit.json", body(doc).encode())
        resources["source"]["audit.json"] = {
            "schema": "QD_AUTO_NATIVE_FILE_V4",
            "native_id": binding["id"],
            "sha256": binding["sha256"],
            "record_schema": doc["schema"],
        }
        cut = {
            "schema": "QD_AUTO_NATIVE_RESOURCE_CUT_V4",
            "enrollment_digest": digest(f.e),
            "scope": "DISPOSABLE_TEST",
            "resources": resources,
        }

        class Cuts:
            @contextmanager
            def lease(self, *args, **kwargs):
                yield SimpleNamespace(snapshot=cut, check=lambda v, t: True)

        # These native cases test namespace/binding only. Financial replay is
        # covered by the disjoint existing V3/FS1 selection, never this test double.
        financial = SimpleNamespace(verify_cut=lambda *args, **kwargs: True)
        port = module.BoundNativeEnrollmentEvidence(cuts=Cuts(), financial=financial)
        current = {"financial_digest": digest(cut)}
        yield SimpleNamespace(**locals())
    finally:
        for out in outputs.values():
            out.close()


def test_native_existing_only_identity_read_no_mutation(native_system):
    s = native_system
    before = {p: p.read_bytes() for p in s.tmp_path.rglob("*.json")}
    assert s.port.verify(s.f.e, s.current, 1000, scope="DISPOSABLE_TEST")
    assert before == {p: p.read_bytes() for p in s.tmp_path.rglob("*.json")}


@pytest.mark.parametrize(
    "damage",
    [
        "foreign_id",
        "missing_root",
        "tampered_digest",
        "omitted_file",
        "financial",
        "wrong_scope",
    ],
)
def test_native_evidence_refusal(native_system, damage):
    s = native_system
    if damage == "foreign_id":
        s.f.e["resources"]["source"]["native_id"][1] += 1
    if damage == "missing_root":
        s.f.e["resources"]["source"]["path"] += "-absent"
    if damage == "tampered_digest":
        s.cut["resources"]["source"]["audit.json"]["sha256"] = "f" * 64
    if damage == "omitted_file":
        s.cut["resources"]["source"].clear()
    if damage == "financial":
        s.financial.verify_cut = lambda *args, **kwargs: False
    if damage == "wrong_scope":
        s.cut["scope"] = "LOCAL_ENROLLED"
    s.cut["enrollment_digest"] = digest(s.f.e)
    s.current["financial_digest"] = digest(s.cut)
    with pytest.raises((ValueError, OSError)):
        s.port.verify(s.f.e, s.current, 1000, scope="DISPOSABLE_TEST")


def test_native_mutation_during_external_audit_refuses(native_system):
    s = native_system

    def mutate(*args, **kwargs):
        (s.tmp_path / "source/audit.json").write_bytes(b'{"schema":"tampered"}')
        return True

    s.financial.verify_cut = mutate
    with pytest.raises((ValueError, OSError)):
        s.port.verify(s.f.e, s.current, 1000, scope="DISPOSABLE_TEST")


def test_operational_reader_rejects_fixture_record_schema(native_system):
    s = native_system
    s.cut["scope"] = "LOCAL_ENROLLED"
    s.cut["resources"]["source"]["audit.json"]["record_schema"] = "FS2_TEST_PIN_V1"
    s.current["financial_digest"] = digest(s.cut)
    with pytest.raises(ValueError, match="OPERATIONAL_RECORD_REQUIRED"):
        s.port.verify(s.f.e, s.current, 1000, scope="LOCAL_ENROLLED")
