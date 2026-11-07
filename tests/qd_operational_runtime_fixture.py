"""Synthetic confined operational-codec components, never an installed authority."""

import copy
from contextlib import contextmanager
from types import SimpleNamespace

from app.services.paper_epoch_fixture import create_epoch_fixture
from app.services.paper_financial_replay import body, digest
from app.services.quality_dips_autonomous_integration import (
    AutonomousCoordinationRead,
    AutonomousNativePublication,
)
from app.services.quality_dips_autonomous_paper import AutonomousPaper
from app.services.quality_dips_autonomous_runtime import PROFILE
from app.services.quality_dips_operational_presentation import (
    OperationalAutonomousSelectedRead,
)
from qd_autonomous_native_fixture import Pins


def components(s):
    clock = lambda: s.n.now[0]
    ledger = create_epoch_fixture(
        s.tmp_path / "coordination" / "op-coordination.sqlite", s.parameters
    )
    engine = AutonomousPaper(
        ledger=ledger,
        candidates=s.n.engine.candidates,
        session_authority=s.n.engine.session_authority,
        source_authority=s.n.engine.source_authority,
        clock=clock,
        publication=AutonomousNativePublication(store=s.store, manifest=s.parameters),
    )
    s.n.engine = engine
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
    return SimpleNamespace(**locals())


def runtime_dependencies(s, c):
    n, stamp = s.n, s.n.now[0]
    identity_observer = lambda: {
        "pid": 123,
        "created": 456,
        "image": "D:\\test-owned.exe",
    }
    confinement = None
    x = SimpleNamespace(
        enrollment=c.enrollment,
        pins=s.dependencies["trust"],
        report_pins=c.pins,
        cap=c.cap,
        service=c.s.reports.ReportService(s.store, c.archive),
    )
    flags = {
        "authority": True,
        "owner": True,
        "clock": True,
        "custody": True,
        "pending": 0,
    }
    enrollment = {
        "schema": "QD_AUTO_LOCAL_RUNTIME_V3",
        "profile": PROFILE,
        "scope": "LOCAL_ENROLLED",
        "reader_enrollment": x.enrollment,
        "process_identity": identity_observer(),
        "writer_roster": ["decision", "source", "projection", "report", "coordination"],
        "disposable_root": None,
    }

    class Authority:
        def verify(self, kind, request, now):
            return {
                "schema": "QD_AUTO_LOCAL_AUTHORITY_V3",
                "kind": kind,
                "verified": flags["authority"],
                "binding": digest(request),
                "scope": "LOCAL_ENROLLED",
                "issuer_id": "SYNTHETIC_NOT_INSTALLED",
            }

    class Ownership:
        @contextmanager
        def lease(self, request, now):
            data = {
                "schema": "QD_AUTO_WRITERS_V3",
                "verified": flags["owner"]
                and (
                    identity_observer is None
                    or identity_observer() == enrollment["process_identity"]
                ),
                "process_identity": enrollment["process_identity"],
                "writer_roster": enrollment["writer_roster"],
                "resources": enrollment["reader_enrollment"],
                "unknown_writers": [],
            }
            yield SimpleNamespace(
                snapshot=data,
                check=lambda data, now: (
                    flags["owner"]
                    and (
                        identity_observer is None
                        or identity_observer() == enrollment["process_identity"]
                    )
                ),
            )

        def drain(self, request, now):
            return {
                "enrollment_digest": digest(enrollment),
                "session_id": request["grant"]["engine_grant"]["session_id"],
                "pending": flags["pending"],
                "unknown": False,
            }

    class Clock:
        def sample(self):
            return {
                "schema": "QD_AUTO_CLOCK_V3",
                "utc": n.now[0],
                "monotonic_ns": (n.now[0] - stamp) * 1_000_000_000,
                "uncertainty_ms": 0 if flags["clock"] else 2000,
                "source_id": "VIRTUAL_FIXTURE_CLOCK_NOT_UTC_AUTHORITY",
            }

    class Custody:
        def current(self, request, now):
            return {
                "schema": "QD_AUTO_CURRENT_V3",
                "status": "ACKNOWLEDGED" if flags["custody"] else "UNKNOWN",
                "source": x.pins.current(),
                "reports": x.report_pins.current(),
                "enrollment_digest": digest(enrollment),
                "observed_at": now,
                "expires_at": now + 5,
            }

    deps = {
        "enrollment": enrollment,
        "engine": n.engine,
        "reader": x.cap,
        "reports": x.service,
        "authority": Authority(),
        "ownership": Ownership(),
        "clock": Clock(),
        "custody": Custody(),
    }
    return SimpleNamespace(**locals())


def native_dependencies(s, holder):
    from app.services.quality_dips_autonomous_enrollment import publication_intent
    from test_quality_dips_autonomous_enrollment import fixture

    f, e = fixture(), s.e
    origin = s.n.now[0]
    clock = SimpleNamespace(
        sample=lambda: {
            "schema": "QD_AUTO_NATIVE_CLOCK_V4",
            "utc": s.n.now[0],
            "monotonic_ns": (s.n.now[0] - origin) * 10**9,
            "uncertainty_ms": 0,
            "source": e["clock_source"],
        },
        verify=lambda sample: f.flags["clock"],
    )
    f.a.update(scope="LOCAL_ENROLLED")
    f.o.update(
        resources=copy.deepcopy(e["resources"]), writers=copy.deepcopy(e["writers"])
    )
    Acceptance = type(f.deps["acceptance"])
    Ownership = type(f.deps["ownership"])
    intent = publication_intent(e)
    generation, last_cut = [0], [None]
    flags = {"custody": True, "unknown": False}

    class AcceptancePort:
        @contextmanager
        def lease(self, request, now):
            f.a.update(issued_at=now, expires_at=now + 30)
            with Acceptance(f.a).lease(request, now) as lease:
                yield lease

    class Custody:
        @contextmanager
        def lease(self, request, now):
            cut = holder[0].financial.cut()
            value = digest(cut)
            if value != last_cut[0]:
                generation[0] += 1
                last_cut[0] = value
            revision = cut["source_revision"]
            data = {
                "schema": "QD_AUTO_NATIVE_CURRENT_V4",
                "scope": "LOCAL_ENROLLED",
                "request_digest": digest(request),
                "revision": revision,
                "acknowledged_revision": revision,
                "high_water": revision,
                "generation": generation[0],
                "financial_digest": value,
                "status": "UNKNOWN" if flags["unknown"] else "ACKNOWLEDGED",
                "observed_at": now,
                "expires_at": now + 5,
                "publication_ack": "SYNTHETIC_V5_INCEPTION_ACK",
                "publication": {
                    "schema": "QD_AUTO_NATIVE_PUBLICATION_V4",
                    "intent_digest": digest(intent),
                    "operation_id": intent["operation_id"],
                    "status": "ACKNOWLEDGED",
                    "ack_id": "SYNTHETIC_V5_INCEPTION_ACK",
                },
            }
            yield SimpleNamespace(
                snapshot=data, check=lambda v, t: flags["custody"] and f.flags["valid"]
            )

    return {
        "acceptance": AcceptancePort(),
        "custody": Custody(),
        "clock": clock,
        "ownership": Ownership(f.o),
        "sessions": f.sessions,
    }
