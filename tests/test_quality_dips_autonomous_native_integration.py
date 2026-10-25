"""Actual native publication/read integration; authorized disposable roots only."""
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
from app.api.quality_dips_selected_paper import financial_view
from app.investment.quality_dips_read_capability import SelectedReadCapability
from app.services.paper_financial_replay import number
from qd_autonomous_native_fixture import REPO, build
from test_quality_dips_autonomous_paper import candidate, entry, monitor, quote


@pytest.fixture
def native(tmp_path):
    authorized = os.environ.get("ATLAS_AUTO_INTEGRATION_ROOT")
    if not authorized:
        pytest.skip("NOT EXECUTED: explicitly confined native integration root required")
    root = Path(authorized)
    assert root.parent == REPO / "logs/diagnostics" and root.name.startswith("qd-auto-integration-")
    assert tmp_path.is_relative_to(root)
    assert all(not p.is_symlink() and not p.is_junction() for p in [tmp_path, *tmp_path.parents])
    x = build(tmp_path)
    try:
        yield x
    finally:
        x.close()


def report(x):
    x.n.now[0] += 1
    return x.service.publish("2026-10-26", x.n.now[0])["report"]


def view(x):
    return financial_view(reader=x.cap, verifier=x.cap, clock=x.clock,
                          account_id=x.n.m["epoch"], epoch=x.n.m["epoch"])


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for part in ("source", "projection", "reports") for p in (root / part).rglob("*") if p.is_file()}


def test_native_auto_entry_partial_full_report_and_selected_view(native):
    x, n = native, native.n
    b = candidate(n)
    assert entry(n)["filled"]
    first = report(x)
    assert number(first["cash"]["closing"]) == number("899.96")
    assert number(next(iter(first["open_positions"].values()))["remaining"]) == 1
    v = view(x)
    assert v["status"] == "ACKNOWLEDGED", v
    assert v["autonomous"]["session_state"] == "RUNNING"
    assert number(v["cash_cost_evidence"]["fees"]) == number("0.02")
    assert number(v["cash_cost_evidence"]["unallocated_entry_costs"]) == number("0.04")
    assert v["autonomous"]["l1"]["ask"] == "100"
    assert monitor(n, b, "partial", "110", {"fundamentals_score": 60})["filled"]
    r = report(x)
    assert number(next(iter(r["open_positions"].values()))["remaining"]) == number("0.6")
    assert number(r["realized"]["costs"]) == number("0.0336")
    assert monitor(n, b, "full", "120", {"classification": "THESIS_BROKEN"})["filled"]
    final = report(x)
    assert not final["open_positions"]
    assert number(final["cash"]["closing"]) == number("1015.9136")
    assert number(final["realized"]["fees"]) == number("0.0432")
    assert number(final["realized"]["slippage"]) == number("0.0432")
    assert number(final["realized"]["net"]) == number("15.9136")
    assert final["status"] == "INCOMPLETE"  # Calendar cutoff not reached.
    before = hashes(x.root)
    v = view(x)
    assert v["status"] == "ACKNOWLEDGED" and not v["positions"]
    assert v["autonomous"]["decision"]["kind"] == "EXIT"
    assert v["realized"]["fees"] == final["realized"]["fees"]
    assert hashes(x.root) == before
    assert n.engine.stop() == "STOPPED"
    assert view(x)["autonomous"]["session_state"] == "STOPPED"
    assert n.new().status() == "STOPPED"
    assert len(x.pins.pin["entries"]) == 3


@pytest.mark.parametrize("kind", ["stale", "entitlement", "closed", "size"])
def test_native_no_fill_bad_l1_visible_refusal(native, kind):
    x, n = native, native.n
    b, q = candidate(n), quote(n, candidate(n))
    if kind == "stale": q["source_timestamp"] -= 30
    if kind == "entitlement": q["entitlement_id"] = ""
    if kind == "closed": q["calendar"]["is_open"] = False
    if kind == "size": q["ask_size"] = "0"
    result = n.engine.step("rejected", bundles=[b], quotes=[q])
    assert not result["filled"] and not x.pins.pin["entries"]
    report(x)
    v = view(x)
    assert v["status"] == "ACKNOWLEDGED", v
    assert v["autonomous"]["latest_refusal"]["status"] == "REFUSED"
    assert v["autonomous"]["l1"] is None and v["cash"] == "1000"


def test_duplicate_native_dispatch_and_restart_do_not_duplicate(native):
    x, n = native, native.n
    b, q = candidate(n), quote(n, candidate(n))
    entered, release = Event(), Event()
    def fault(phase):
        if phase == "before_ack":
            entered.set()
            assert release.wait(2)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(n.engine.step, "same", bundles=[b], quotes=[q], fault=fault)
        assert entered.wait(2)
        second = pool.submit(n.engine.step, "same", bundles=[b], quotes=[q])
        release.set()
        results = [first.result(), second.result()]
    assert all(r["filled"] for r in results), results
    assert len(x.pins.pin["entries"]) == 1
    assert n.new().status() == "STOP_INCOMPLETE"
    n.new().reconcile()
    assert len(x.pins.pin["entries"]) == 1


@pytest.mark.parametrize("boundary", ["before_commit", "before_native_ack", "after_native_ack"])
def test_native_unknown_does_not_replay_or_report_clean(native, boundary, monkeypatch):
    x, n = native, native.n
    if boundary == "before_native_ack":
        original = x.target.publish
        def fail(*args):
            original(*args)
            raise OSError("Injected native commit-before-ACK interruption")
        monkeypatch.setattr(x.target, "publish", fail)
    def fault(phase):
        if phase == boundary: raise OSError("Injected boundary")
    result = n.engine.step("uncertain", bundles=[candidate(n)], quotes=[quote(n, candidate(n))], fault=fault)
    assert not result["filled"]
    count = len(x.pins.pin["entries"])
    if boundary == "before_commit":
        assert count == 0 and n.engine.stop() == "STOPPED"
    else:
        assert n.engine.stop() == "STOP_INCOMPLETE"
        with pytest.raises(ValueError): n.new().reconcile()
        assert view(x)["status"] == "UNKNOWN"
        assert not n.engine.step("uncertain", bundles=[], quotes=[])["filled"]
        assert len(x.pins.pin["entries"]) == count


@pytest.mark.parametrize("kind", ["missing_ack", "foreign_root", "stale_pin", "missing_report", "corrupt_record"])
def test_native_missing_or_conflicting_evidence_never_exposes_clean_financials(native, kind):
    x, n = native, native.n
    assert entry(n)["filled"]
    report(x)
    if kind == "missing_ack":
        (x.root / "source/0001-ack.json").unlink()
    if kind == "foreign_root": x.cap.enrollment["source_root"] = x.projection_id
    if kind == "stale_pin": x.pins.pin["entries"] = []
    if kind == "missing_report": next((x.root / "reports").glob("*.json")).unlink()
    if kind == "corrupt_record": (x.root / "source/0001-record.json").write_bytes(b"{}")
    before = hashes(x.root)
    assert view(x)["status"] in ("UNKNOWN", "UNAVAILABLE")
    assert hashes(x.root) == before


def test_pause_stop_overnight_and_strict_reader_separation(native):
    x, n = native, native.n
    assert entry(n)["filled"]
    n.engine.pause()
    report(x)
    assert view(x)["autonomous"]["session_state"] == "PAUSED"
    strict_reader = SelectedReadCapability(enrollment=x.enrollment, authority=x.Authority(), clock=x.clock, port=x.port)
    with pytest.raises(ValueError): strict_reader.read_committed(n.m["epoch"], n.m["epoch"])
    assert n.engine.stop() == "STOPPED"
    v = view(x)
    assert len(v["positions"]) == 1 and v["autonomous"]["session_state"] == "STOPPED"
    n.now[0] += 10
    assert view(x)["autonomous"]["l1_state"] == "STALE"


def test_report_substitution_and_concurrent_read_cannot_repair(native, monkeypatch):
    x = native
    assert entry(x.n)["filled"]
    report(x)
    before = hashes(x.root)
    def forbidden(*args, **kwargs): raise AssertionError("GET attempted write")
    monkeypatch.setattr(x.f.w.WindowsOutput, "write_bound", forbidden)
    monkeypatch.setattr(x.f.w.WindowsOutput, "create_root", forbidden)
    monkeypatch.setattr(x.f.FinancialRecordStore, "__init__", forbidden)
    with ThreadPoolExecutor(3) as pool:
        assert all(v["status"] == "ACKNOWLEDGED" for v in pool.map(lambda _: view(x), range(6)))
    assert hashes(x.root) == before


def test_overnight_daily_cost_allocation_and_report_lineage(native):
    x, n = native, native.n
    b = candidate(n)
    assert entry(n)["filled"]
    assert monitor(n, b, "partial", "110", {"fundamentals_score": 60})["filled"]
    early = report(x)
    assert early["report_version"] == 2
    assert n.engine.stop() == "STOPPED"
    n.now[0] += 86400
    grant = {**n.grant, "session_id": "explicit-next-day-fixture", "issued_at": n.now[0],
             "expires_at": n.now[0] + 3600}
    n.engine.start(grant)
    assert monitor(n, b, "overnight-final", "120", {"classification": "THESIS_BROKEN"})["filled"]
    n.now[0] += 1
    late = x.service.publish("2026-10-26", n.now[0])["report"]
    day2 = x.service.publish("2026-10-27", n.now[0])["report"]
    assert late["status"] == "COMPLETE" and late["source"]["revision"] == 3
    assert number(late["cash"]["closing"]) == number("943.9424")
    assert number(day2["cash"]["opening"]) == number("943.9424")
    assert number(day2["realized"]["costs"]) == number("0.0528")
    assert number(day2["realized"]["net"]) == number("11.9472")
    assert x.service.history()[0]["report"] == early


@pytest.mark.parametrize("boundary", ["before_commit", "after_native_ack", "after_ack"])
def test_abrupt_process_native_cross_store_boundary(native, boundary):
    x, n = native, native.n
    assert n.engine.stop() == "STOPPED"
    x.store.close()
    pin_file = x.root / "synthetic-custody.json"
    pin_file.write_text(json.dumps(x.pins.current()))
    child = r'''
import json, os, sys
from pathlib import Path
repo, root, pin_path, boundary = sys.argv[1:]
sys.path[:0] = [str(Path(repo)/"backend"), str(Path(repo)/"tests")]
from qd_autonomous_native_fixture import Pins
from test_quality_dips_autonomous_paper import setup, candidate, quote
from app.services.quality_dips_autonomous_integration import AutonomousNativePublication
import importlib.util
spec=importlib.util.spec_from_file_location("child_native",Path(repo)/"scripts/volume_inspector/financial_reporting.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
n=setup(Path(root),reopen=True)
class DurableTestPins(Pins):
 def advance(self,old,new):
  super().advance(old,new)
  Path(pin_path).write_text(json.dumps(self.pin))
pins=DurableTestPins(json.loads(Path(pin_path).read_text()),lambda:n.now[0])
# Projection root identity was enrolled explicitly in the parent fixture.
projection=m.ProjectionTarget(str(Path(root)/"projection"),json.loads((Path(root)/"synthetic-projection.json").read_text()))
store=m.f.FinancialRecordStore(str(Path(root)/"source"),pins,projection=projection)
n.engine.publication=AutonomousNativePublication(store=store,manifest=n.m)
grant={**n.grant,"session_id":"explicit-abrupt-child-session"}
n.engine.start(grant)
def fault(phase):
 if phase==boundary: os._exit(83)
n.engine.step("abrupt",bundles=[candidate(n)],quotes=[quote(n,candidate(n))],fault=fault)
raise RuntimeError("Boundary not reached")
'''
    (x.root / "synthetic-projection.json").write_text(json.dumps(x.projection_id))
    proc = subprocess.run([sys.executable, "-B", "-c", child, str(REPO), str(x.root), str(pin_file), boundary],
                          capture_output=True, text=True, timeout=25, check=False)
    assert proc.returncode == 83, proc.stderr
    x.pins.pin = json.loads(pin_file.read_text())
    reopened = x.f.FinancialRecordStore(str(x.root / "source"), x.pins, projection=x.target)
    x.publication.store = reopened
    try:
        restarted = n.new()
        assert restarted.status() == "STOP_INCOMPLETE"
        if boundary == "after_native_ack":
            with pytest.raises(ValueError): restarted.reconcile()
            assert restarted.stop() == "STOP_INCOMPLETE"
        else:
            restarted.reconcile()
            assert restarted.stop() == "STOPPED"
        expected = 0 if boundary == "before_commit" else 1
        assert len(x.pins.pin["entries"]) == expected
        assert reopened.snapshot()["state"]["revision"] == expected
    finally:
        reopened.close()


def test_missing_versioned_coordination_refuses_before_financial_intent(native):
    x = native
    with x.n.ledger.connect() as db:
        db.execute("DROP TABLE autonomous_activity")  # Disposable retained-V1 equivalent.
    result = entry(x.n)
    assert result["reason"] == "NATIVE_COORDINATION_VERSION_REQUIRED"
    assert not x.pins.pin["entries"] and x.n.ledger.snapshot()["revision"] == 0
    assert view(x)["status"] == "UNKNOWN"


@pytest.mark.parametrize("change_mode", [False, True])
def test_read_clock_tick_allows_only_observation_time_renewal(native, change_mode):
    x = native
    assert entry(x.n)["filled"]
    report(x)
    original = x.cap.coordination.read_status
    calls = [0]
    def ticking():
        result = original()
        calls[0] += 1
        x.n.now[0] += 1
        if change_mode and calls[0] == 2:
            result["activity"]["session_state"] = "STOPPED"
        return result
    x.cap.coordination.read_status = ticking
    if change_mode:
        with pytest.raises(ValueError, match="CHANGED_OR_UNKNOWN"):
            x.cap.read_committed(x.n.m["epoch"], x.n.m["epoch"])
    else:
        payload = x.cap.read_committed(x.n.m["epoch"], x.n.m["epoch"])
        assert payload["status"] == "ACKNOWLEDGED"
        assert payload["autonomous"]["observed_at"] == payload["observed_at"]
