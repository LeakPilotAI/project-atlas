"""Explicit synthetic disposable fixture builder; never used by the HTTP host."""
import copy
import hashlib
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import test_quality_dips_integration_v1 as seed
from app.services.paper_financial_replay import digest, strict

REPO = Path(__file__).resolve().parents[1]


def shifted(value):
    if type(value) is dict:
        return {k: shifted(v) for k, v in value.items()}
    if type(value) is list:
        return [shifted(v) for v in value]
    if type(value) is int and value > 1_000_000_000:
        return value - 172800
    if type(value) is str and value.startswith("2026-") and "T" in value:
        return (datetime.fromisoformat(value) - timedelta(days=2)).isoformat()
    return value


def build_fixture(root):
    """Three precommitted immutable views; host has no financial write code."""
    root = Path(root)
    spec = importlib.util.spec_from_file_location("fixture_native_fs3", REPO / "scripts/volume_inspector/financial_reporting.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    f = m.f
    seed_root = root / "seed"
    seed_root.mkdir()
    original = seed.bundle_for
    def earlier(*args, **kwargs):
        manifest, bundle, now = original(*args, **kwargs)
        return shifted(manifest), shifted(bundle), now - 172800
    seed.bundle_for = earlier
    try:
        s = seed.system(seed_root, "SPY", "ETF")
    finally:
        seed.bundle_for = original
    s.service.execute(s.approve(s.entry()))
    sequences = [("entry", s.store._load()[2])]
    s.now[0] += 86400
    s.service.execute(s.approve(s.exit_request("1")))
    sequences.append(("partial", s.store._load()[2]))
    s.now[0] += 1
    s.service.execute(s.approve(s.exit_request("1.5", "final")))
    sequences.append(("final", s.store._load()[2]))
    scope = {"schema": "FS3_REPORT_SCOPE_V1", "account_id": s.service.account, "epoch": s.service.epoch,
             "policy_digest": digest(s.manifest), "timezone": s.manifest["timezone"]}

    class Pins:
        def __init__(self, pin):
            self.pin = copy.deepcopy(pin)
        def current(self):
            return copy.deepcopy(self.pin)
        def advance(self, old, new):
            assert old == self.pin
            self.pin = copy.deepcopy(new)
        def check_clock(self, stamp):
            assert type(stamp) is int

    phases = {}
    for phase, rows in sequences:
        base = root / phase
        base.mkdir()
        projection_id = m.ProjectionTarget.provision_disposable(str(base / "projection"))
        target = m.ProjectionTarget(str(base / "projection"), projection_id)
        pins = Pins(f.FinancialRecordStore.provision_disposable(str(base / "source"), s.manifest))
        store = f.FinancialRecordStore(str(base / "source"), pins, projection=target)
        rp = Pins(m.ReportArchive.provision_disposable(str(base / "reports"), scope, s.manifest))
        archive = m.ReportArchive(str(base / "reports"), rp)
        try:
            for row in rows:
                store.execute(strict(row["command"]), projection_required=True)
            # Explicit fixed historical local reporting day, not today's balance.
            day = datetime.fromtimestamp(strict(rows[-1]["command"])["timestamp"], ZoneInfo(scope["timezone"])).date().isoformat()
            m.ReportService(store, archive).publish(day, strict(rows[-1]["command"])["timestamp"] + 1)
        finally:
            store.close()
            target.close()
            archive.close()
        enrollment = {"schema": "QD_READ_ENROLLMENT_V1", "account_id": s.service.account, "epoch": s.service.epoch,
            "manifest_digest": digest(s.manifest), "policy_digest": digest(s.manifest["account_policy"]),
            "source_root": pins.pin["root"], "projection_root": projection_id, "report_root": rp.pin["root"],
            "inception": pins.pin["inception"]}
        current = {"schema": "QD_READ_CURRENT_V1", "enrollment_digest": digest(enrollment),
            "observed_at": 0, "expires_at": 0, "generation": 1, "source": pins.pin, "reports": rp.pin,
            "high_water": len(rows), "acknowledged_revision": len(rows), "status": "ACKNOWLEDGED"}
        phases[phase] = {"enrollment": enrollment, "current": current}
    raw = json.dumps({"schema": "QD_HTTP_SYNTHETIC_ONLY_V1", "phases": phases}, sort_keys=True).encode()
    (root / "fixture.json").write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def financial_hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for phase in ("entry", "partial", "final") for p in (Path(root) / phase).rglob("*") if p.is_file()}
