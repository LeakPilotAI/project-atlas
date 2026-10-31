"""Confined synthetic authorities and actual autonomous-to-native test wiring."""
import copy
import hashlib
import importlib.util
import json
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from app.services.paper_financial_replay import digest
from app.services.quality_dips_autonomous_integration import (
    AutonomousCoordinationRead,
    AutonomousNativePublication,
    AutonomousSelectedRead,
)
from test_quality_dips_autonomous_paper import STAMP, setup

REPO = Path(__file__).resolve().parents[1]


class Pins:
    """Synthetic CAS test dependency, NOT independent or operational custody."""
    def __init__(self, pin, clock):
        self.pin, self.clock = copy.deepcopy(pin), clock

    def current(self):
        return copy.deepcopy(self.pin)

    def advance(self, old, new):
        if old != self.pin:
            raise ValueError("TEST_STALE_CUSTODY")
        self.pin = copy.deepcopy(new)

    def check_clock(self, stamp):
        if type(stamp) is not int or stamp != self.clock():
            raise ValueError("TEST_CLOCK_MISMATCH")


def build(root, stamp=STAMP, *, coordination_root=None, session_reports=False):
    n = setup(coordination_root if coordination_root is not None else root, stamp=stamp)
    spec = importlib.util.spec_from_file_location("auto_native_read", REPO / "scripts/volume_inspector/financial_read_port.py")
    port_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(port_module)
    m, f = port_module.m, port_module.m.f
    clock = lambda: n.now[0]
    projection_id = m.ProjectionTarget.provision_disposable(str(root / "projection"))
    target = m.ProjectionTarget(str(root / "projection"), projection_id)
    pins = Pins(f.FinancialRecordStore.provision_disposable(str(root / "source"), n.m), clock)
    store = f.FinancialRecordStore(str(root / "source"), pins, projection=target)
    scope = {"schema": "FS3_REPORT_SCOPE_V1", "account_id": n.m["epoch"], "epoch": n.m["epoch"],
             "policy_digest": digest(n.m), "timezone": n.m["timezone"]}
    if session_reports:
        scope.update(schema='FS3_QD_REPORT_SCOPE_V2', session_reporting_policy='ACKNOWLEDGED_EVENT_TIME_INCLUSIVE_CUT_V1')
    report_pins = Pins(m.ReportArchive.provision_disposable(str(root / "reports"), scope, n.m), clock)
    archive = m.ReportArchive(str(root / "reports"), report_pins)
    publication = AutonomousNativePublication(store=store, manifest=n.m)
    n.engine.publication = publication
    original_new = n.new
    def new():
        engine = original_new()
        engine.publication = publication
        return engine
    n.new = new
    service = m.ReportService(store, archive)
    enrollment = {"schema": "QD_AUTO_READ_ENROLLMENT_V1", "account_id": n.m["epoch"], "epoch": n.m["epoch"],
                  "manifest_digest": digest(n.m), "policy_digest": digest(n.m["autonomous_policy"]),
                  "source_root": pins.pin["root"], "projection_root": projection_id,
                  "report_root": report_pins.pin["root"], "inception": pins.pin["inception"]}
    def current():
        now = clock()
        return {"schema": "QD_READ_CURRENT_V1", "enrollment_digest": digest(enrollment),
                "observed_at": now, "expires_at": now + 30, "generation": 1, "source": pins.current(),
                "reports": report_pins.current(), "high_water": len(pins.pin["entries"]),
                "acknowledged_revision": len(pins.pin["entries"]), "status": "ACKNOWLEDGED"}
    class Authority:
        @contextmanager
        def lease(self, e, now):
            if e != enrollment:
                raise ValueError("FOREIGN_FIXTURE")
            snap = current()
            yield SimpleNamespace(snapshot=snap, check=lambda p, t: p == current())
    port = port_module.NativeFinancialReadPort(source_root=str(root / "source"),
        projection_root=str(root / "projection"), report_root=str(root / "reports"))
    cap = AutonomousSelectedRead(enrollment=enrollment, authority=Authority(), clock=clock, port=port,
                                coordination=AutonomousCoordinationRead(n.engine))
    def close():
        store.close()
        target.close()
        archive.close()
    return SimpleNamespace(**locals())


def build_http_fixture(root):
    """Execute automatic trades before starting an existing read-only test host."""
    from test_quality_dips_autonomous_paper import candidate, entry, monitor
    phases = {}
    stamp = int(datetime(2026, 10, 19, 14, tzinfo=UTC).timestamp())
    for count, phase in enumerate(("entry", "partial", "final"), 1):
        base = root / phase
        base.mkdir()
        x = build(base, stamp=stamp)
        try:
            n = x.n
            b = candidate(n)
            assert entry(n)["filled"]
            if count >= 2:
                assert monitor(n, b, "partial", "110", {"fundamentals_score": 60})["filled"]
            if count == 3:
                assert monitor(n, b, "final", "120", {"classification": "THESIS_BROKEN"})["filled"]
            assert n.engine.stop() == "STOPPED"
            n.now[0] += 1
            x.service.publish("2026-10-19", n.now[0])
            phases[phase] = {"enrollment": x.enrollment, "current": x.current(),
                             "coordination": AutonomousCoordinationRead(n.engine).read_status()}
        finally:
            x.close()
    raw = json.dumps({"schema": "QD_HTTP_AUTO_SYNTHETIC_ONLY_V2", "phases": phases}, sort_keys=True).encode()
    (root / "fixture.json").write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()
