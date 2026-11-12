"""Hyperliquid first PAPER native inception ONLY; synthetic offline test ports.

No real native account roots, issuer, market data, stop or order endpoints.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest, initial_state
from app.services.personal_native_coordination import PersonalNativeCoordination
from app.services.personal_paper_runtime import CHECKS
from test_personal_local_authority_memory import authority as qd_auth_fixture
from test_personal_local_authority_memory import owner as original_writer_fixture
from test_personal_paper_inception_memory import system

from scripts.observation_runtime import personal_installation_technical as technical
from scripts.observation_runtime.personal_coordination_store import (
    NativePersonalCoordinationImages,
)
from scripts.observation_runtime.personal_installation_technical import (
    NativePersonalTechnicalChecks,
)
from scripts.observation_runtime.personal_local_authority import (
    NativePersonalOperatorAuthority,
)
from scripts.observation_runtime.personal_paper_inception import (
    NativePersonalInceptionFiles,
)
from scripts.observation_runtime.personal_release_identity import (
    NativePersonalReleaseIdentity,
)
from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock
from scripts.observation_runtime.personal_writer_ownership import (
    NativePersonalWriterOwnership,
)


def test_hl_operator_exact_immutable_dual_lane_binding_and_init_only(monkeypatch):
    qd = qd_auth_fixture(monkeypatch)
    hl = system("HYPERLIQUID")
    try:
        pair = {
            "QUALITY_DIPS": digest(qd.f.e),
            "HYPERLIQUID": digest(hl.n),
        }
        qd.value["accounts"] = copy.deepcopy(pair)
        qd.value["actions"] = ["READ_ONLY", "INITIALIZE_SIMULATED_ACCOUNTS"]
        auth = NativePersonalOperatorAuthority(
            policy=qd.i.p, enrollment=hl.n,
            reader=qd.reader, clock=qd.clock,
            runtime_id="SYNTHETIC-RUNTIME", accounts=pair,
        )
        assert auth._lane == "HYPERLIQUID"
        assert auth.accounts == pair
        assert auth.activation("INITIALIZE_SIMULATED_ACCOUNTS")["actions"] == (
            ["READ_ONLY", "INITIALIZE_SIMULATED_ACCOUNTS"]
        )
        assert auth.activation("READ_ONLY")["accounts"] == pair
        for action in ("AUTO_PAPER", "SHUTDOWN_FLATTEN", "EMERGENCY_STOP",
                       "CONNECT_APPROVED_DATA", "PLACE_ORDER"):
            with pytest.raises(ValueError, match="HL_FIRST_INCEPTION_ONLY"):
                auth.activation(action)
        with pytest.raises(ValueError, match="HL_FIRST_INCEPTION_ONLY"):
            auth.verify({"scope":"LOCAL_ENROLLED", "enrollment":hl.n, "grant":{}})
        qd.value["accounts"]["HYPERLIQUID"] = "f" * 64
        with pytest.raises(ValueError):
            auth.activation("INITIALIZE_SIMULATED_ACCOUNTS")
    finally:
        hl.ledger.db.close()


def test_hl_operator_refuses_one_lane_or_foreign_sibling_account(monkeypatch):
    qd = qd_auth_fixture(monkeypatch)
    hl = system("HYPERLIQUID")
    try:
        for pair in (
            None,
            {"HYPERLIQUID": digest(hl.n)},
            {"QUALITY_DIPS": "a"*64, "HYPERLIQUID": "b"*64},
            {"QUALITY_DIPS": "not-hash", "HYPERLIQUID": digest(hl.n)},
        ):
            with pytest.raises(ValueError):
                NativePersonalOperatorAuthority(
                    policy=qd.i.p, enrollment=hl.n, reader=qd.reader,
                    clock=qd.clock, runtime_id="SYNTHETIC-RUNTIME",
                    accounts=pair,
                )
    finally:
        hl.ledger.db.close()


def test_hl_real_native_writer_class_accepts_only_genesis_and_read(monkeypatch):
    hl = system("HYPERLIQUID")
    try:
        port = original_writer_fixture(monkeypatch, enrollment=hl.n)
        assert port.port._lane == "HYPERLIQUID"
        initializer = {
            "schema": "PERSONAL_GENESIS_WRITER_V1",
            "intent_digest": digest(port.intent),
            "process": port.port.identity,
        }
        with port.port.lease(initializer,port.now[0]) as lease:
            assert lease.check(initializer,port.now[0]) is True
        read = {
            "schema": "PERP_AUTO_OP_READ_ENROLLMENT_V1",
            "account_id":port.e["account_id"], "epoch":port.e["epoch"],
            **{role+"_root":port.e["resources"][role]["native_id"]
               for role in ("source","projection","report")},
        }
        with port.port.lease({
                "schema":"PERSONAL_NATIVE_READ_LEASE_V1",
                "reader_enrollment":read,
        }, port.now[0]) as lease:
            assert lease.check(lease.snapshot,port.now[0]) is True
        for request in (
            port.request,
            {"enrollment":port.e, "grant":{}},
            {"scope":"LOCAL_ENROLLED","enrollment":port.e,"grant":{}},
        ):
            with (pytest.raises(ValueError,match="HL_FIRST_INCEPTION_ONLY"),
                  port.port.lease(request,port.now[0])):
                pytest.fail("HL_NATIVE_RUNTIME_WRITER_ADMITTED")
        port.port.close()
        assert not any(port.files.values())
    finally:
        hl.ledger.db.close()


def synthetic_hl_technical(monkeypatch):
    s = system("HYPERLIQUID")
    state = initial_state(s.m)
    old = s.ledger
    old.db.execute("CREATE TABLE projections(id TEXT,receipt TEXT)")
    old.db.commit()
    ledger = object.__new__(PersonalNativeCoordination)
    ledger.manifest, ledger.connect = s.m, old.connect
    ledger._load = lambda _db: (copy.deepcopy(state),digest(s.m),{})
    images = object.__new__(NativePersonalCoordinationImages)
    images.enrollment = digest(s.n)
    images.root_id = s.n["resources"]["coordination"]["native_id"]
    images._stop_capacity = None
    images._load = lambda: (b"SYNTHETIC_HL_IMAGE",{"revision":1})
    ledger.images = images
    s.b.publication.ledger = ledger
    clock = object.__new__(LocalWindowsClock)
    monkeypatch.setattr(LocalWindowsClock,"__call__",lambda self:s.now[0])
    monkeypatch.setattr(LocalWindowsClock,"require_operational",lambda *args:None)
    sample = {
        "schema":"QD_AUTO_CLOCK_V3",
        "utc":s.now[0],
        "monotonic_ns":12345,
        "source_id":"UNTRUSTED_TEST_ONLY",
        "uncertainty_ms":1,
    }
    monkeypatch.setattr(LocalWindowsClock,"runtime_sample",lambda self:copy.deepcopy(sample))
    monkeypatch.setattr(
        LocalWindowsClock,"verify_runtime_sample",
        lambda self,v:v == sample and v["uncertainty_ms"] <= 1000,
    )
    owner = object.__new__(NativePersonalWriterOwnership)
    owner._lane = "HYPERLIQUID"
    owner.read_only = False
    owner.enrollment, owner.ledger = s.n, ledger
    owner.authority = SimpleNamespace(clock=clock)
    owner._verify = lambda: True
    owner.outputs = {
        role:SimpleNamespace(root=role) for role in ("source","projection","report")
    }
    @contextmanager
    def hold(request,stamp):
        yield SimpleNamespace(
            snapshot=request,
            check=lambda row,now:row==request and stamp<=now<=stamp+30,
        )
    owner.lease = hold
    release = object.__new__(NativePersonalReleaseIdentity)
    release.artifact_digest = s.n["release_digest"]
    process = {
        k:v for k,v in next(iter(s.n["writers"].values())).items()
        if k != "schema"
    }
    release.verify = lambda **kwargs:{"process":process}
    files=NativePersonalInceptionFiles()
    monkeypatch.setattr(
        technical, "Path",
        lambda value:SimpleNamespace(iterdir=lambda:iter(())),
    )
    port = NativePersonalTechnicalChecks(
        bootstrap=s.b, release=release, clock=clock,
        runtime_id="SYNTHETIC", ownership=owner,
        ledger=ledger, files=files,
    )
    request = {
        "schema":"ATLAS_PERSONAL_INCEPTION_REQUEST_V1",
        "action":"INITIALIZE_SIMULATED_ACCOUNTS",
        "scope":s.b.scope(),
    }
    return SimpleNamespace(**locals())


def test_hl_inception_technical_all_gates_readonly_before_any_native_publication(monkeypatch):
    s=synthetic_hl_technical(monkeypatch)
    try:
        assert s.port._lane == "HYPERLIQUID"
        facts=s.port.inspect(s.request)
        assert set(facts)==set(CHECKS)
        assert all(facts.values()), (facts,s.port.last_failure)
        assert s.s.b.publication.row(s.request["scope"]["operation_id"]) is None
        assert s.files._active is None
        assert not all(s.port.inspect({"action":"AUTO_PAPER"}).values())
        assert not all(s.port.inspect({**s.request,"scope":{}}).values())
    finally:
        s.old.db.close()


@pytest.mark.parametrize("damage", [
    "policy_not_hl", "foreign_owner", "wrong_release", "wrong_schema",
    "expired_clock", "foreign_scope", "pending_unknown", "already_started",
])
def test_hl_inception_technical_refuses_fake_or_operational_authority(monkeypatch,damage):
    s=synthetic_hl_technical(monkeypatch)
    try:
        request=copy.deepcopy(s.request)
        if damage=="policy_not_hl":
            s.port.bootstrap.enrollment["parameters"]["perp_policy"]["max_positions"]=9
        elif damage=="foreign_owner":
            s.owner.enrollment=object()
        elif damage=="wrong_release":
            s.release.artifact_digest="f"*64
        elif damage=="wrong_schema":
            request["schema"]="ALPACA_LIVE"
        elif damage=="expired_clock":
            s.sample["uncertainty_ms"]=1001
        elif damage=="foreign_scope":
            request["scope"]={"bad":"foreign"}
        elif damage=="pending_unknown":
            s.s.b.publication.row=lambda *_:("x","y","UNKNOWN")
        elif damage=="already_started":
            s.port.current=object()
        assert not all(s.port.inspect(request).values())
    finally:
        s.old.db.close()
