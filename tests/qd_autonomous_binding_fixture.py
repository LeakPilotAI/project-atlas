"""V5 confined physical resources; all authorities remain explicitly synthetic."""

import copy
import importlib.util
from contextlib import contextmanager
from types import SimpleNamespace

from app.services.paper_financial_replay import digest
from app.services.quality_dips_autonomous_binding import (
    EnrolledAutonomousRuntime,
    NativeFinancialBinding,
)
from app.services.quality_dips_autonomous_enrollment import (
    AutonomousNativeEnrollment,
    publication_intent,
)
from qd_autonomous_runtime_fixture import compose
from test_quality_dips_autonomous_enrollment import fixture
from test_quality_dips_autonomous_paper import STAMP


def build(root, confinement, *, stamp=STAMP, session_reports=False):
    spec = importlib.util.spec_from_file_location(
        "v5_fixture_native",
        confinement.parents[2] / "scripts/volume_inspector/snapshot_store.py",
    )
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    for name in ("coordination", "control", "custody"):
        with native.w.WindowsOutput.create_root(str(root / name)):
            pass
    x = compose(root, confinement, stamp=stamp, coordination_root=root / "coordination", session_reports=session_reports)
    f = fixture()
    e = f.e
    e.update(
        account_id=x.n.m["epoch"],
        epoch=x.n.m["epoch"],
        policy_digest=digest(x.n.m["autonomous_policy"]),
        inception_digest=digest(x.n.m),
        clock_source="EXPLICIT_SYNTHETIC_V5_CLOCK",
    )
    for role in e["resources"]:
        path = root / ("reports" if role == "report" else role)
        with native.w.WindowsOutput(str(path)) as out:
            e["resources"][role].update(
                path=str(path), native_id=native.native.file_identity(out.root_handle)
            )
    # The roster is synthetic acceptance, NOT real process ownership evidence.
    # V3 independently observes this test's real process as before.
    financial = NativeFinancialBinding(
        enrollment=e,
        runtime=x.runtime,
        test_root=confinement,
        release_digest=e["release_digest"],
    )
    x.n.engine.publication = financial
    clock = SimpleNamespace(
        sample=lambda: {
            "schema": "QD_AUTO_NATIVE_CLOCK_V4",
            "utc": x.n.now[0],
            "monotonic_ns": (x.n.now[0] - stamp) * 10**9,
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
            cut = financial.cut()
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

    admission = AutonomousNativeEnrollment(
        enrollment=e,
        acceptance=AcceptancePort(),
        custody=Custody(),
        clock=clock,
        ownership=Ownership(f.o),
        native=financial,
        sessions=f.sessions,
    )
    # Publish an initial *disposable* report; no operational inception writer used.
    from datetime import datetime
    from zoneinfo import ZoneInfo
    day = datetime.fromtimestamp(x.n.now[0], ZoneInfo(x.n.m["timezone"])).date().isoformat()
    x.x.service.publish(day, x.n.now[0])
    runtime = EnrolledAutonomousRuntime(
        runtime=x.runtime, admission=admission, financial=financial
    )
    inner_grant = copy.deepcopy(x.grant)
    inner_grant["engine_grant"].update(schema="QD_AUTO_ENGINE_SESSION_V5")
    native_grant = {
        "schema": "QD_AUTO_NATIVE_SESSION_V4",
        "session_id": inner_grant["engine_grant"]["session_id"],
        "enrollment_digest": digest(e),
        "issued_at": inner_grant["engine_grant"]["issued_at"],
        "expires_at": inner_grant["engine_grant"]["expires_at"],
        "capabilities": ["AUTO_PAPER"],
    }
    grant = {
        "schema": "QD_AUTO_NATIVE_RUNTIME_SESSION_V5",
        "enrollment_digest": digest(runtime.enrollment),
        "native_grant": native_grant,
        "runtime_grant": inner_grant,
    }
    return SimpleNamespace(**locals())
