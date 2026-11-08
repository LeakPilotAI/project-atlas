"""Operational codec in confined new resources, with synthetic trust only."""

import copy
import importlib.util
import os
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import body, digest, number, strict
from test_quality_dips_autonomous_enrollment import fixture
from test_quality_dips_autonomous_paper import candidate, entry, monitor, setup


@pytest.fixture
def system(tmp_path):
    root = Path(os.environ["ATLAS_OP_CODEC_TEST_ROOT"])
    repo = Path(__file__).resolve().parents[1]
    assert root.parent == repo / "logs/diagnostics" and root.name.startswith(
        "qd-op-codec-"
    )
    assert tmp_path.is_relative_to(root)
    spec = importlib.util.spec_from_file_location(
        "test_op_autonomous",
        repo / "scripts/volume_inspector/operational_autonomous_store.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    e = fixture().e
    n = setup(tmp_path)
    parameters = copy.deepcopy(n.m)
    parameters.update(
        release=e["release_digest"],
        provenance="ACCEPTED_AUTONOMOUS_PAPER_PARAMETERS_V1",
    )
    e.update(
        epoch=parameters["epoch"],
        account_id=parameters["epoch"],
        inception_digest=digest(parameters),
        policy_digest=digest(parameters["autonomous_policy"]),
    )
    w, native = module.fs2.w, module.fs2.native
    for role in e["resources"]:
        with w.WindowsOutput.create_root(str(tmp_path / role)) as out:
            e["resources"][role].update(
                path=str(out.root), native_id=native.file_identity(out.root_handle)
            )
    document = {
        "schema": "QD_AUTO_OP_INCEPTION_V1",
        "enrollment_digest": digest(e),
        "execution": "SIMULATED",
        "parameters": parameters,
    }
    with w.WindowsOutput(str(tmp_path / "source")) as out:
        inception = out.write_bound("inception.json", body(document).encode())
    pin = {
        "schema": "QD_AUTO_OP_PIN_V1",
        "root": e["resources"]["source"]["native_id"],
        "inception": inception,
        "epoch": e["epoch"],
        "entries": [],
    }

    class Custody:
        def current(self):
            return copy.deepcopy(pin)

        def check_clock(self, stamp):
            if stamp != n.now[0]:
                raise ValueError("SYNTHETIC_CLOCK_REFUSAL")

        def advance(self, old, new):
            if old != pin:
                raise ValueError("SYNTHETIC_STALE_CUSTODY")
            pin.clear()
            pin.update(copy.deepcopy(new))

    flags = {"accepted": True, "ack": True, "unknown": False}

    class Authority:
        @contextmanager
        def lease(self, request, now):
            witness = {
                "schema": "QD_AUTO_OP_ADMISSION_V1",
                "request_digest": digest(request),
                "status": "READ_ACCEPTED" if request["command"] is None else "PENDING",
                "reservation_id": "SYNTHETIC_NOT_INSTALLED",
                "expires_at": now + 5,
                "revoked": False,
            }
            yield SimpleNamespace(
                snapshot=witness,
                check=lambda p, t: flags["accepted"] and not flags["unknown"],
                acknowledge=lambda req, receipt, pin: {
                    "schema": "QD_AUTO_OP_RESERVATION_ACK_V1",
                    "request_digest": digest(req),
                    "receipt_digest": digest(receipt),
                    "status": "ACKNOWLEDGED" if flags["ack"] else "UNKNOWN",
                },
                verify_ack=lambda ack: flags["ack"],
                mark_unknown=lambda req: flags.update(unknown=True),
            )

    report_spec = importlib.util.spec_from_file_location(
        "op_codec_projection", repo / "scripts/volume_inspector/financial_reporting.py"
    )
    reports = importlib.util.module_from_spec(report_spec)
    report_spec.loader.exec_module(reports)
    projection = reports.ProjectionTarget(
        str(tmp_path / "projection"), e["resources"]["projection"]["native_id"]
    )
    dependencies = {
        "enrollment": e,
        "trust": Custody(),
        "authority": Authority(),
        "clock": lambda: n.now[0],
        "projection": projection,
    }
    store = module.OperationalAutonomousStore(**dependencies)
    try:
        yield SimpleNamespace(**locals())
    finally:
        store.close()
        projection.close()


def test_distinct_operational_records_and_idempotent_native_append(system):
    s = system
    assert entry(s.n)["filled"]
    with s.n.ledger.connect(readonly=True) as db:
        command = strict(db.execute("SELECT body FROM events").fetchone()[0])
    receipt = s.store.execute(command)
    assert s.store.execute(command) == receipt
    assert len(s.pin["entries"]) == 1
    raw = (s.tmp_path / "source/0001-record.json").read_bytes()
    assert strict(raw)["schema"] == "QD_AUTO_OP_RECORD_V1"
    assert b"FS2_RECORD_V1" not in raw and s.pin["schema"] == "QD_AUTO_OP_PIN_V1"
    assert s.store.snapshot()["state"]["cash"] == "899.96"


@pytest.mark.parametrize("schema", ["FS2_TEST_PIN_V1", "QD_OP_CURRENT_V1"])
def test_test_manual_pin_refusal(system, schema):
    s = system
    s.pin["schema"] = schema
    with pytest.raises(ValueError, match="NO_TEST_OR_MANUAL"):
        s.module.OperationalAutonomousStore(**s.dependencies)


def test_missing_authority_and_no_provisioning(system):
    with pytest.raises(ValueError):
        system.module.OperationalAutonomousStore()
    with pytest.raises(ValueError):
        system.module.OperationalAutonomousStore.provision_disposable("unused", {})


def test_authority_refusal_no_files(system):
    s = system
    before = {p: p.read_bytes() for p in (s.tmp_path / "source").iterdir()}
    s.flags["accepted"] = False
    with pytest.raises(ValueError):
        s.store.snapshot()
    assert before == {p: p.read_bytes() for p in (s.tmp_path / "source").iterdir()}


def test_commit_ack_unknown_cannot_replay(system):
    s = system
    assert entry(s.n)["filled"]
    with s.n.ledger.connect(readonly=True) as db:
        command = strict(db.execute("SELECT body FROM events").fetchone()[0])
    s.flags["ack"] = False
    with pytest.raises(ValueError, match="ACK_UNKNOWN"):
        s.store.execute(command)
    assert s.flags["unknown"] and len(s.pin["entries"]) == 1
    with pytest.raises(ValueError):
        s.store.execute(command)
    assert len(s.pin["entries"]) == 1
    with pytest.raises(ValueError):
        s.module.OperationalAutonomousStore(**s.dependencies)


def test_partial_final_reuse_original_arithmetic(system):
    s = system
    b = candidate(s.n)
    assert entry(s.n)["filled"]

    def append_latest():
        with s.n.ledger.connect(readonly=True) as db:
            command = strict(
                db.execute("SELECT body FROM events ORDER BY revision DESC").fetchone()[
                    0
                ]
            )
        return s.store.execute(command)

    append_latest()
    assert monitor(s.n, b, "partial", "110", {"fundamentals_score": 60})["filled"]
    append_latest()
    assert s.store.snapshot()["state"]["positions"]
    assert monitor(s.n, b, "final", "120", {"classification": "THESIS_BROKEN"})[
        "filled"
    ]
    append_latest()
    assert s.store.snapshot()["state"]["cash"] == "1015.9136"
    assert all(
        number(p["remaining"]) == 0
        for p in s.store.snapshot()["state"]["positions"].values()
    )


def test_original_fixture_inception_not_adopted(system):
    s = system
    import hashlib

    path = s.tmp_path / "source/inception.json"
    raw = body(s.n.m).encode()
    path.write_bytes(raw)
    s.pin["inception"]["sha256"] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError):
        s.store.snapshot()


@pytest.mark.parametrize("role", ["source", "projection"])
def test_resource_binding_refuses_before_access(system, role):
    s = system
    e = copy.deepcopy(s.e)
    e["resources"][role]["native_id"][1] += 1
    with pytest.raises(ValueError, match="RESOURCE_BINDING_BEFORE_ACCESS"):
        s.module.OperationalAutonomousStore(**{**s.dependencies, "enrollment": e})


def test_revocation_after_native_ack_stays_unknown(system):
    s = system
    assert entry(s.n)["filled"]
    with s.n.ledger.connect(readonly=True) as db:
        command = strict(db.execute("SELECT body FROM events").fetchone()[0])
    original = s.dependencies["authority"].lease

    @contextmanager
    def lease(request, now):
        with original(request, now) as admitted:
            acknowledge = admitted.acknowledge

            def revoked(*args):
                result = acknowledge(*args)
                s.flags["accepted"] = False
                return result

            admitted.acknowledge = revoked
            yield admitted

    s.dependencies["authority"].lease = lease
    with pytest.raises(ValueError, match="CONTINUITY_LOST"):
        s.store.execute(command)
    assert s.store.poisoned and s.flags["unknown"] and len(s.pin["entries"]) == 1


def test_operational_existing_only_reader_no_mutation(system):
    s = system
    before = {p: p.read_bytes() for p in s.tmp_path.rglob("*.json")}
    reader = s.module.OperationalAutonomousReader(**s.dependencies)
    assert reader.read_committed()["state"]["cash"] == "1000"
    assert before == {p: p.read_bytes() for p in s.tmp_path.rglob("*.json")}


def test_operational_reader_refuses_test_pin(system):
    s = system
    s.pin["schema"] = "FS2_TEST_PIN_V1"
    reader = s.module.OperationalAutonomousReader(**s.dependencies)
    with pytest.raises(ValueError):
        reader.read_committed()


def test_operational_codec_engine_report_selected_read_wiring(system):
    from app.services.paper_epoch_fixture import create_epoch_fixture
    from app.services.quality_dips_autonomous_integration import (
        AutonomousCoordinationRead,
        AutonomousNativePublication,
    )
    from app.services.quality_dips_autonomous_paper import AutonomousPaper
    from app.services.quality_dips_operational_presentation import (
        OperationalAutonomousSelectedRead,
    )
    from qd_autonomous_native_fixture import Pins

    s = system
    clock = lambda: s.n.now[0]
    ledger = create_epoch_fixture(s.tmp_path / "op-coordination.sqlite", s.parameters)
    engine = AutonomousPaper(
        ledger=ledger,
        candidates=s.n.engine.candidates,
        session_authority=s.n.engine.session_authority,
        source_authority=s.n.engine.source_authority,
        clock=clock,
        publication=AutonomousNativePublication(store=s.store, manifest=s.parameters),
    )
    assert (
        engine.start({**s.n.grant, "schema": "QD_AUTO_ENGINE_SESSION_V5"}) == "RUNNING"
    )
    s.n.engine = engine
    assert entry(s.n)["filled"]
    scope = {
        "schema": "FS3_REPORT_SCOPE_V1",
        "account_id": s.e["account_id"],
        "epoch": s.e["epoch"],
        "policy_digest": digest(s.parameters),
        "timezone": s.parameters["timezone"],
    }
    with s.w.WindowsOutput(str(s.tmp_path / "report")) as out:
        bound = out.write_bound("scope.json", body(scope).encode())
    pins = Pins(
        {
            "schema": "FS3_REPORT_PIN_V1",
            "root": s.e["resources"]["report"]["native_id"],
            "scope": bound,
            "reports": [],
        },
        clock,
    )
    archive = s.reports.ReportArchive(str(s.tmp_path / "report"), pins)
    try:
        s.n.now[0] += 1  # Advance the explicit synthetic clock past inception/fill.
        s.reports.ReportService(s.store, archive).publish("2026-10-26", clock())
        enrollment = {
            "schema": "QD_AUTO_OP_READ_ENROLLMENT_V1",
            "account_id": s.e["account_id"],
            "epoch": s.e["epoch"],
            "manifest_digest": digest(s.parameters),
            "policy_digest": s.e["policy_digest"],
            "source_root": s.pin["root"],
            "projection_root": s.e["resources"]["projection"]["native_id"],
            "report_root": pins.current()["root"],
            "inception": s.pin["inception"],
        }

        class ReadAuthority:
            @contextmanager
            def lease(self, e, now):
                current = {
                    "schema": "QD_READ_CURRENT_V1",
                    "enrollment_digest": digest(enrollment),
                    "observed_at": now,
                    "expires_at": now + 30,
                    "generation": 1,
                    "source": copy.deepcopy(s.pin),
                    "reports": pins.current(),
                    "high_water": len(s.pin["entries"]),
                    "acknowledged_revision": len(s.pin["entries"]),
                    "status": "ACKNOWLEDGED",
                }
                yield SimpleNamespace(snapshot=current, check=lambda p, t: True)

        cap = OperationalAutonomousSelectedRead(
            enrollment=enrollment,
            authority=ReadAuthority(),
            clock=clock,
            port=s.module.OperationalAutonomousReader(**s.dependencies),
            coordination=AutonomousCoordinationRead(engine),
        )
        before = {p: p.read_bytes() for p in s.tmp_path.rglob("*.json")}
        view = cap.read_committed(s.e["account_id"], s.e["epoch"])
        assert view["state"]["cash"] == "899.96"
        assert cap.verify(
            view, account_id=s.e["account_id"], epoch=s.e["epoch"], now=clock()
        )["verified"]
        assert before == {p: p.read_bytes() for p in s.tmp_path.rglob("*.json")}
    finally:
        archive.close()
