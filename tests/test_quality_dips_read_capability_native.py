"""Confined disposable native reads. No operational enrollment or authority."""
import copy
import importlib.util
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
from app.investment.quality_dips_read_capability import SelectedReadCapability
from app.services.paper_financial_replay import digest, strict
from test_quality_dips_read_capability import FixtureAuthority, setup_read

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def native(tmp_path):
    authorized = os.environ.get("ATLAS_READ_ACCEPTANCE_ROOT")
    if not authorized:
        pytest.skip("NOT EXECUTED: explicit confined native test root required")
    root = Path(authorized)
    assert root.parent == REPO / "logs/diagnostics" and root.name.startswith("qd-read-capability-")
    assert tmp_path.is_relative_to(root)
    assert all(not p.is_symlink() and not p.is_junction() for p in [tmp_path, *tmp_path.parents])
    spec = importlib.util.spec_from_file_location("native_read_port_test", REPO / "scripts/volume_inspector/financial_read_port.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    m, f = module.m, module.m.f
    seed_root = tmp_path / "synthetic-seed"
    seed_root.mkdir()
    x = setup_read(seed_root)

    class Pins:
        # Only in-memory fixture custody, not an issuer or independent authority.
        def __init__(self, pin):
            self.pin = copy.deepcopy(pin)
        def current(self):
            return copy.deepcopy(self.pin)
        def advance(self, old, new):
            assert old == self.pin
            self.pin = copy.deepcopy(new)
        def check_clock(self, timestamp):
            assert type(timestamp) is int

    source, projection, reports = [tmp_path / name for name in ("source", "projection", "reports")]
    projection_id = m.ProjectionTarget.provision_disposable(str(projection))
    target = m.ProjectionTarget(str(projection), projection_id)
    trust = Pins(f.FinancialRecordStore.provision_disposable(str(source), x.manifest))
    store = f.FinancialRecordStore(str(source), trust, projection=target)
    rt = Pins(m.ReportArchive.provision_disposable(str(reports), x.scope, x.manifest))
    archive = m.ReportArchive(str(reports), rt)
    try:
        store.execute(strict(x.rows[0]["command"]), projection_required=True)
        m.ReportService(store, archive).publish(x.day, x.s.now[0])
    finally:
        store.close()
        target.close()
        archive.close()
    enrollment = {**x.enrollment, "source_root": trust.pin["root"], "projection_root": projection_id,
                  "report_root": rt.pin["root"], "inception": trust.pin["inception"]}
    current = {**x.current, "enrollment_digest": digest(enrollment), "source": trust.pin, "reports": rt.pin}
    authority = FixtureAuthority(enrollment, current)
    port = module.NativeFinancialReadPort(source_root=str(source), projection_root=str(projection), report_root=str(reports))
    cap = SelectedReadCapability(enrollment=enrollment, authority=authority, clock=lambda: x.s.now[0], port=port)
    return SimpleNamespace(**locals())


def capture(root):
    return {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_native_verified_snapshot_has_no_publication_or_repair(native, monkeypatch):
    n = native
    before = capture(n.tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError("READ ATTEMPTED PUBLICATION")
    monkeypatch.setattr(n.f.w.WindowsOutput, "write_bound", forbidden)
    monkeypatch.setattr(n.f.w.WindowsOutput, "create_root", forbidden)
    monkeypatch.setattr(n.f.FinancialRecordStore, "__init__", forbidden)
    monkeypatch.setattr(n.m.ReportArchive, "__init__", forbidden)
    view = n.cap.read_committed(n.x.s.service.account, n.x.s.service.epoch)
    assert view["state"]["cash"] == "900.0" and view["report_status"] == "INCOMPLETE"
    assert len(view["state"]["positions"]) == 1 and view["projection_revision"] == 1
    assert capture(n.tmp_path) == before


@pytest.mark.parametrize("kind", ["missing", "foreign", "tamper", "unknown_tail", "missing_ack",
                                  "report_tamper", "hard_link", "projection_tamper", "replaced_record", "report_rollback"])
def test_native_resource_and_source_refusals(native, kind):
    n = native
    if kind == "missing":
        n.port.paths = (str(n.tmp_path / "absent"), *n.port.paths[1:])
    elif kind == "foreign":
        n.port.paths = (str(n.reports), *n.port.paths[1:])
    elif kind == "tamper":
        (n.source / "0001-record.json").write_bytes(b"{}")
    elif kind == "unknown_tail":
        (n.source / "recovery-required.json").write_bytes(b"{}")
    elif kind == "missing_ack":
        # No deletion: substitute a pin missing its required acknowledgement.
        del n.authority.pin["source"]["entries"][0]["ack"]
    elif kind == "report_tamper":
        (n.reports / "0001-report.json").write_bytes(b"{}")
    elif kind == "projection_tamper":
        next(n.projection.glob("*-view.json")).write_bytes(b"{}")
    elif kind == "replaced_record":
        record = n.source / "0001-record.json"
        raw = record.read_bytes()
        record.rename(n.tmp_path / "retained-original-record.json")
        record.write_bytes(raw)
    elif kind == "report_rollback":
        n.authority.pin["reports"]["reports"] = []
    else:
        os.link(n.source / "0001-record.json", n.tmp_path / "linked-record.json")
    before = capture(n.tmp_path)
    with pytest.raises((OSError, ValueError, KeyError)):
        n.cap.read_committed(n.x.s.service.account, n.x.s.service.epoch)
    assert capture(n.tmp_path) == before
    assert not (n.tmp_path / "absent").exists()


def test_native_junction_refused(native):
    n = native
    junction = n.tmp_path / "junction"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(n.source)], capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    n.port.paths = (str(junction), *n.port.paths[1:])
    with pytest.raises((OSError, ValueError)):
        n.cap.read_committed(n.x.s.service.account, n.x.s.service.epoch)


def test_native_symlink_refused_when_privilege_available(native):
    n = native
    link = n.tmp_path / "symlink"
    try:
        link.symlink_to(n.source, target_is_directory=True)
    except OSError as exc:
        if exc.winerror == 1314:
            pytest.skip("NOT EXECUTED: Windows true-symlink privilege unavailable (1314)")
        raise
    n.port.paths = (str(link), *n.port.paths[1:])
    with pytest.raises((OSError, ValueError)):
        n.cap.read_committed(n.x.s.service.account, n.x.s.service.epoch)


def test_native_bound_read_checks_identity_before_payload(native, monkeypatch):
    n = native
    n.authority.pin["source"]["inception"]["id"][2] += 1
    n.cap.enrollment["inception"] = copy.deepcopy(n.authority.pin["source"]["inception"])
    n.authority.expected = copy.deepcopy(n.cap.enrollment)
    n.authority.pin["enrollment_digest"] = digest(n.cap.enrollment)
    calls = []
    original = n.f.w.read_file
    def read(*args):
        calls.append(True)
        return original(*args)
    monkeypatch.setattr(n.f.w, "read_file", read)
    with pytest.raises((OSError, ValueError)):
        n.cap.read_committed(n.x.s.service.account, n.x.s.service.epoch)
    assert calls == []


def test_native_uncoordinated_writer_tail_refuses_read_without_recovery_write(native, monkeypatch):
    n = native
    reading, written = Event(), Event()
    original = n.f.w.read_file
    def observe(*args):
        result = original(*args)
        if not reading.is_set():
            reading.set()
            assert written.wait(3)
        return result
    def writer():
        assert reading.wait(3)
        (n.source / "pending-intent.json").write_bytes(b"{}")
        written.set()
    monkeypatch.setattr(n.f.w, "read_file", observe)
    with ThreadPoolExecutor(max_workers=1) as pool:
        work = pool.submit(writer)
        with pytest.raises((OSError, ValueError)):
            n.cap.read_committed(n.x.s.service.account, n.x.s.service.epoch)
        work.result(timeout=3)
    assert (n.source / "pending-intent.json").exists()
    assert not (n.source / "recovery-required.json").exists()
