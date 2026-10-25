"""Explicit confined synthetic local dependencies. Never imported by production."""
import importlib.util
import os
from contextlib import contextmanager
from types import SimpleNamespace

from app.services.paper_financial_replay import digest
from app.services.quality_dips_autonomous_runtime import PROFILE, AutonomousRuntime
from qd_autonomous_native_fixture import REPO, build
from test_quality_dips_autonomous_paper import candidate, quote


def compose(root, confinement, *, stamp, identity_observer=None, coordination_root=None):
    if identity_observer is None:
        spec = importlib.util.spec_from_file_location("runtime_self_identity", REPO / "scripts/observation_runtime/disposable_host_owner.py")
        identity = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(identity)
        identity_observer = lambda: identity.observe_pid(os.getpid())
    x = build(root, stamp=stamp, coordination_root=coordination_root)
    n = x.n
    assert n.engine.stop() == "STOPPED"
    n.now[0] += 1
    flags = {"authority": True, "owner": True, "clock": True, "custody": True, "pending": 0}
    enrollment = {"schema": "QD_AUTO_LOCAL_RUNTIME_V3", "profile": PROFILE, "scope": "DISPOSABLE",
                  "reader_enrollment": x.enrollment, "process_identity": identity_observer(),
                  "writer_roster": ["decision", "source", "projection", "report", "coordination"],
                  "disposable_root": str(confinement)}

    class Authority:
        def verify(self, kind, request, now):
            return {"schema": "QD_AUTO_LOCAL_AUTHORITY_V3", "kind": kind, "verified": flags["authority"],
                    "binding": digest(request), "scope": "DISPOSABLE", "issuer_id": "SYNTHETIC_NOT_INSTALLED"}

    class Ownership:
        @contextmanager
        def lease(self, request, now):
            data = {"schema": "QD_AUTO_WRITERS_V3", "verified": flags["owner"] and (identity_observer is None or identity_observer() == enrollment["process_identity"]),
                    "process_identity": enrollment["process_identity"], "writer_roster": enrollment["writer_roster"],
                    "resources": enrollment["reader_enrollment"], "unknown_writers": []}
            yield SimpleNamespace(snapshot=data, check=lambda data, now: flags["owner"] and (identity_observer is None or identity_observer() == enrollment["process_identity"]))

        def drain(self, request, now):
            return {"enrollment_digest": digest(enrollment), "session_id": request["grant"]["engine_grant"]["session_id"],
                    "pending": flags["pending"], "unknown": False}

    class Clock:
        def sample(self):
            return {"schema": "QD_AUTO_CLOCK_V3", "utc": n.now[0], "monotonic_ns": (n.now[0] - stamp) * 1_000_000_000,
                    "uncertainty_ms": 0 if flags["clock"] else 2000, "source_id": "VIRTUAL_FIXTURE_CLOCK_NOT_UTC_AUTHORITY"}

    class Custody:
        def current(self, request, now):
            return {"schema": "QD_AUTO_CURRENT_V3", "status": "ACKNOWLEDGED" if flags["custody"] else "UNKNOWN",
                    "source": x.pins.current(), "reports": x.report_pins.current(),
                    "enrollment_digest": digest(enrollment), "observed_at": now, "expires_at": now + 5}

    deps = {"enrollment": enrollment, "engine": n.engine, "reader": x.cap, "reports": x.service,
            "authority": Authority(), "ownership": Ownership(), "clock": Clock(), "custody": Custody()}
    runtime = AutonomousRuntime(**deps)
    grant = {"schema": "QD_AUTO_LOCAL_SESSION_V3", "profile": PROFILE, "enrollment_digest": digest(enrollment),
             "engine_grant": {**n.grant, "session_id": "continuous-disposable-session"}, "max_observations": 32}

    def frame(sequence, kind="entry"):
        b = candidate(n)
        q = quote(n, b)
        observation = None
        if kind in ("partial", "final", "hold"):
            bid = "110" if kind == "partial" else "120"
            q.update(bid=bid, ask=str(int(bid) + 1))
            # Keep spread within the already accepted model.
            q["ask"] = bid + ".1"
            observation = {"symbol": b["instrument"]["symbol"], "instrument": b["instrument"],
                           "observed_at": n.now[0], "current": {"evidence_quality": "HIGH", **(
                               {"fundamentals_score": 60} if kind == "partial" else
                               {"classification": "THESIS_BROKEN"} if kind == "final" else {})}}
        return {"schema": "QD_AUTO_OBSERVATION_V3", "session_id": grant["engine_grant"]["session_id"],
                "sequence": sequence, "observed_at": n.now[0], "connected": True,
                "request": {"bundles": [b] if kind == "entry" else [], "quotes": [q], "observation": observation}}

    return SimpleNamespace(**locals())
