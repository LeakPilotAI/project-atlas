"""FS3 fixed-plan tests: all native resources inside one authorized test root."""
import copy
import importlib.util
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal, localcontext
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
spec = importlib.util.spec_from_file_location("fs3", REPO / "scripts/volume_inspector/financial_reporting.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
f = m.f
GOLDEN = json.loads((REPO / "tests/fixtures/fs1/legacy-synthetic-golden.json").read_text())["cases"][0]


class Pins:
    def __init__(self, pin):
        self.pin, self.now, self.available = copy.deepcopy(pin), 0, True
    def current(self):
        if not self.available: raise f.Refused("Injected test custody unavailable")
        return copy.deepcopy(self.pin)
    def advance(self, old, new):
        if f.body(old) != f.body(self.current()): raise f.Refused("Stale test pin")
        self.pin = copy.deepcopy(new)
    def check_clock(self, timestamp):
        if type(timestamp) is not int or timestamp != self.now: raise f.Refused("Test clock mismatch")


@pytest.fixture(autouse=True)
def confinement(tmp_path):
    root = Path(os.environ["ATLAS_D1_RUN_ROOT"])
    assert root.parent == REPO / "logs/diagnostics" and root.name.startswith("qd-fs3-report-projection-")
    assert tmp_path.is_relative_to(root)
    assert all(not p.is_symlink() and not p.is_junction() for p in [tmp_path, *tmp_path.parents])


@pytest.fixture
def bundle(tmp_path):
    manifest = copy.deepcopy(GOLDEN["manifest"])
    commands = [f.strict(row[2]) for row in GOLDEN["sql_rows"]]
    target_id = m.ProjectionTarget.provision_disposable(str(tmp_path / "projection"))
    target = m.ProjectionTarget(str(tmp_path / "projection"), target_id)
    trust = Pins(f.FinancialRecordStore.provision_disposable(str(tmp_path / "financial"), manifest))
    store = f.FinancialRecordStore(str(tmp_path / "financial"), trust, projection=target)
    scope = {"schema": "FS3_REPORT_SCOPE_V1", "account_id": "disposable-msft", "epoch": manifest["epoch"],
             "policy_digest": f.digest(manifest), "timezone": "America/New_York"}
    report_trust = Pins(m.ReportArchive.provision_disposable(str(tmp_path / "reports"), scope, manifest))
    archive = m.ReportArchive(str(tmp_path / "reports"), report_trust)
    service = m.ReportService(store, archive)
    try:
        yield store, trust, target, archive, report_trust, service, commands, scope
    finally:
        store.close()
        target.close()
        archive.close()


def complete(bundle, count=3):
    store, trust, _, _, _, _, commands, _ = bundle
    for c in commands[:count]:
        trust.now = c["timestamp"]
        store.execute(c, projection_required=True)
    trust.now = 1792814400  # 2026-10-24 00:00 America/New_York, exclusive day end.


def test_projected_partial_full_report_idempotent_restart(bundle):
    store, trust, target, archive, rt, service, _, _ = bundle
    complete(bundle)
    first = service.publish("2026-10-23", trust.now)
    assert first == service.publish("2026-10-23", trust.now)
    report = first["report"]
    assert report["status"] == "COMPLETE" and report["projection_status"] == "FULLY_ACKNOWLEDGED"
    assert Decimal(report["cash"]["closing"]) == Decimal("1017.42")
    assert Decimal(report["realized"]["costs"]) == Decimal("0.08")
    assert not report["open_positions"] and report["valuation"] is None
    reopened = f.FinancialRecordStore(store.output.root, trust, projection=target)
    other = m.ReportArchive(archive.output.root, rt)
    try:
        assert m.ReportService(reopened, other).history() == [first]
    finally:
        reopened.close()
        other.close()


def test_open_overnight_not_falsely_liquidated_or_lifecycle_complete(bundle):
    complete(bundle, 1)
    _, trust, _, _, _, service, _, _ = bundle
    report = service.publish("2026-10-23", trust.now)["report"]
    assert report["status"] == "COMPLETE" and len(report["open_positions"]) == 1
    assert report["lifecycle_status"] == "NOT_EVALUATED" and report["valuation_status"] == "UNAVAILABLE"
    assert Decimal(report["cash"]["closing"]) == 900 and Decimal(report["realized"]["net"]) == 0


def test_intraday_report_is_incomplete_and_revisions_preserved(bundle):
    complete(bundle, 1)
    _, trust, _, archive, _, service, commands, _ = bundle
    trust.now = commands[0]["timestamp"] + 1
    early = service.publish("2026-10-23", trust.now)
    assert early["report"]["status"] == "INCOMPLETE"
    trust.now = 1792814400
    late = service.publish("2026-10-23", trust.now)
    assert late["revision"] == 2 and late["previous"] != early["previous"]
    assert service.history() == [early, late]
    assert len(list(Path(archive.output.root).glob("*-report.json"))) == 2


@pytest.mark.parametrize("phase", ["intent", "view", "ack"])
def test_projection_failure_is_unknown_and_not_retried(bundle, monkeypatch, phase):
    store, trust, target, _, _, service, commands, _ = bundle
    original = target.output.write_bound
    calls = []
    def fail(leaf, data):
        calls.append(leaf)
        binding = original(leaf, data)
        if leaf.endswith("-" + phase + ".json"): raise OSError("Injected lost projection acknowledgement")
        return binding
    monkeypatch.setattr(target.output, "write_bound", fail)
    trust.now = commands[0]["timestamp"]
    with pytest.raises(OSError): store.execute(commands[0], projection_required=True)
    before = len(calls)
    with pytest.raises(f.Refused): store.execute(commands[0], projection_required=True)
    assert len(calls) == before
    report = service.try_publish("2026-10-23", 1792814400)
    assert report["status"] == "UNKNOWN" and report["cash"] is None
    with pytest.raises(f.Refused): f.FinancialRecordStore(store.output.root, trust, projection=target)


@pytest.mark.parametrize("phase", ["intent", "view", "ack"])
def test_replaced_projection_file_refuses_reports(bundle, phase):
    complete(bundle, 1)
    _, trust, target, _, _, service, _, _ = bundle
    path = next(Path(target.output.root).glob("*-" + phase + ".json"))
    raw = path.read_bytes()
    path.rename(path.parent.parent / ("retained-" + phase))
    target.output.write_bound(path.name, raw)
    assert service.try_publish("2026-10-23", trust.now)["status"] == "UNKNOWN"


def test_missing_projection_verifier_and_external_projection_write_refused(bundle):
    complete(bundle, 1)
    store, trust, target, _, _, service, _, _ = bundle
    with pytest.raises(f.Refused): f.FinancialRecordStore(store.output.root, trust)
    target.output.write_bound("unexpected.json", b"{}")
    assert service.try_publish("2026-10-23", trust.now)["status"] == "UNKNOWN"


@pytest.mark.parametrize("damage", ["cash", "fees", "net", "quantity", "revision", "cutoff", "account", "epoch", "policy", "head", "lineage", "valuation", "duplicate", "report-version", "cash-type", "counts-type", "projection-status"])
def test_independent_report_audit_rejects_contradictions(bundle, damage):
    complete(bundle, 2)
    store, trust, _, _, _, service, _, scope = bundle
    report = copy.deepcopy(service.publish("2026-10-23", trust.now)["report"])
    pin, manifest, rows, state, _, _, _ = store._load()
    if damage == "cash": report["cash"]["closing"] = "10000"
    if damage == "fees": report["realized"]["fees"] = "0"
    if damage == "net": report["realized"]["net"] = "100"
    if damage == "quantity": next(iter(report["open_positions"].values()))["remaining"] = "0"
    if damage == "revision": report["source"]["revision"] = True
    if damage == "cutoff": report["period"]["end_exclusive"] += 1
    if damage == "account": report["account_id"] = "foreign"
    if damage == "epoch": report["epoch"] = "foreign"
    if damage == "policy": report["policy_digest"] = "0" * 64
    if damage == "head": report["source"]["head"] = "0" * 64
    if damage == "lineage": report["source"]["record_lineage"] = []
    if damage == "valuation": report["valuation"] = "1000"
    if damage == "duplicate": rows = [*rows, rows[-1]]
    if damage == "report-version": report["report_version"] = True
    if damage == "cash-type": report["cash"]["opening"] = 1000
    if damage == "counts-type": report["counts"]["entries"] = True
    if damage == "projection-status": report["projection_status"] = "UNVERIFIED"
    with pytest.raises((ValueError, KeyError)):
        m.audit_daily_report(report, scope, manifest, pin, rows, state)


def test_independent_auditor_does_not_call_replay_or_builder(bundle, monkeypatch):
    complete(bundle)
    store, trust, _, _, _, service, _, scope = bundle
    report = service.publish("2026-10-23", trust.now)["report"]
    pin, manifest, rows, state, _, _, _ = store._load()
    from app.services import paper_daily_report as pure
    monkeypatch.setattr(pure, "replay_verified_events", lambda *args: pytest.fail("Auditor called replay"))
    monkeypatch.setattr(pure, "build_daily_report", lambda *args: pytest.fail("Auditor called builder"))
    assert pure.audit_daily_report(report, scope, manifest, pin, rows, state)["financially_consistent"]


@pytest.mark.parametrize("damage", ["financial-stale", "report-stale", "missing-ack", "corrupt-report", "foreign-scope", "unavailable"])
def test_sources_and_archive_fail_closed(bundle, damage):
    store, trust, _, archive, rt, service, _, _ = bundle
    old = copy.deepcopy(trust.pin)
    complete(bundle)
    service.publish("2026-10-23", trust.now)
    if damage == "financial-stale": trust.pin = old
    if damage == "report-stale": rt.pin["reports"] = []
    if damage == "missing-ack":
        path = Path(store.output.root) / f.name(3, "ack")
        path.rename(path.parent.parent / "retained-financial-ack")
    if damage == "corrupt-report": (Path(archive.output.root) / "0001-report.json").write_bytes(b"corrupt")
    if damage == "foreign-scope": rt.pin["scope"] = trust.pin["inception"]
    if damage == "unavailable": trust.available = False
    assert service.try_publish("2026-10-23", trust.now)["status"] == "UNKNOWN"


@pytest.mark.parametrize("moment", ["before", "after", "pin"])
def test_report_publication_failure_retains_unknown(bundle, monkeypatch, moment):
    complete(bundle)
    _, trust, _, archive, rt, service, _, _ = bundle
    original = archive.output.write_bound
    def fail(leaf, raw):
        if leaf.endswith("-report.json") and moment == "before": raise OSError("Before report publication")
        binding = original(leaf, raw)
        if leaf.endswith("-report.json") and moment == "after": raise OSError("Lost report acknowledgement")
        return binding
    if moment == "pin": monkeypatch.setattr(rt, "advance", lambda *args: (_ for _ in ()).throw(OSError("Pin unavailable")))
    else: monkeypatch.setattr(archive.output, "write_bound", fail)
    assert service.try_publish("2026-10-23", trust.now)["status"] == "UNKNOWN"
    assert service.try_publish("2026-10-23", trust.now)["status"] == "UNKNOWN"
    with pytest.raises(f.Refused): m.ReportArchive(archive.output.root, rt)


def test_concurrent_report_retry_and_duplicate_financial_command(bundle):
    complete(bundle)
    store, trust, _, _, rt, service, commands, _ = bundle
    trust.now = commands[-1]["timestamp"]
    assert store.execute(commands[-1], projection_required=True)["source_revision"] == 3
    trust.now = 1792814400
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: service.publish("2026-10-23", trust.now), range(2)))
    assert results[0] == results[1] and len(rt.pin["reports"]) == 1


def test_unrelated_report_account_cannot_adopt_source(bundle, tmp_path):
    complete(bundle)
    store, trust, _, _, _, _, _, scope = bundle
    manifest = copy.deepcopy(GOLDEN["manifest"])
    manifest["epoch"] = "other-epoch"
    other_scope = {**scope, "epoch": manifest["epoch"], "policy_digest": f.digest(manifest)}
    pins = Pins(m.ReportArchive.provision_disposable(str(tmp_path / "other-reports"), other_scope, manifest))
    archive = m.ReportArchive(str(tmp_path / "other-reports"), pins)
    try:
        assert m.ReportService(store, archive).try_publish("2026-10-23", trust.now)["status"] == "UNKNOWN"
        assert not pins.pin["reports"]
    finally:
        archive.close()


@pytest.mark.parametrize("precision", [6, 28, 50])
def test_deterministic_report_under_ambient_precision(bundle, precision):
    complete(bundle)
    _, trust, _, _, _, service, _, _ = bundle
    baseline = service.publish("2026-10-23", trust.now)
    with localcontext() as c:
        c.prec = precision
        assert f.body(service.publish("2026-10-23", trust.now)) == f.body(baseline)
        assert c.prec == precision


@pytest.mark.parametrize("day,hours", [("2026-03-08", 23), ("2026-11-01", 25)])
def test_ny_dst_boundaries_and_midnight_partial_fill_attribution(tmp_path, day, hours):
    zone = ZoneInfo("America/New_York")
    start = int(datetime.fromisoformat(day).replace(tzinfo=zone).timestamp())
    end = start + hours * 3600
    manifest = copy.deepcopy(GOLDEN["manifest"])
    manifest.update(opened_at=start - 10, epoch="dst-" + day)
    trust = Pins(f.FinancialRecordStore.provision_disposable(str(tmp_path / "dst-financial"), manifest))
    store = f.FinancialRecordStore(str(tmp_path / "dst-financial"), trust)
    scope = {"schema": "FS3_REPORT_SCOPE_V1", "account_id": "dst-fixture", "epoch": manifest["epoch"],
             "policy_digest": f.digest(manifest), "timezone": manifest["timezone"]}
    rt = Pins(m.ReportArchive.provision_disposable(str(tmp_path / "dst-reports"), scope, manifest))
    archive = m.ReportArchive(str(tmp_path / "dst-reports"), rt)
    try:
        commands = [f.strict(row[2]) for row in GOLDEN["sql_rows"]]
        position = None
        for index, timestamp in enumerate([start - 1, start, end]):
            c = commands[index]
            c.update(epoch=manifest["epoch"], timestamp=timestamp)
            c["quote"]["observed_at"] = timestamp
            if index: c["position_id"] = position
            trust.now = timestamp
            position = store.execute(c)["position_id"]
        report = m.ReportService(store, archive).publish(day, end)["report"]
        assert report["period"]["end_exclusive"] - report["period"]["start"] == hours * 3600
        assert report["counts"] == {"entries": 0, "exits": 1}
        assert Decimal(next(iter(report["open_positions"].values()))["remaining"]) == Decimal("0.75")
        assert Decimal(report["realized"]["costs"]) == Decimal("0.02")
    finally:
        store.close()
        archive.close()



def test_fs2_review_typed_root_identity_refused(bundle):
    store, trust, target, _, _, _, _, _ = bundle
    trust.pin["root"][0] = float(trust.pin["root"][0])
    with pytest.raises(f.Refused):
        f.FinancialRecordStore(store.output.root, trust, projection=target)


@pytest.mark.parametrize("identity", ["float", "bool", "short", "negative"])
def test_projection_root_identity_is_strict(bundle, identity):
    _, _, target, _, _, _, _, _ = bundle
    pin = copy.deepcopy(target.expected_root)
    if identity == "float": pin[0] = float(pin[0])
    if identity == "bool": pin[0] = True
    if identity == "short": pin = pin[:2]
    if identity == "negative": pin[0] = -1
    with pytest.raises(f.Refused): m.ProjectionTarget(target.output.root, pin)


def test_report_root_float_refused_before_coordinator(bundle):
    _, _, _, archive, pins, _, _, _ = bundle
    pins.pin["root"][0] = float(pins.pin["root"][0])
    with pytest.raises(f.Refused): m.ReportArchive(archive.output.root, pins)


def test_duplicate_conflicting_command_does_not_publish_projection(bundle):
    complete(bundle, 1)
    store, trust, target, _, _, _, commands, _ = bundle
    before = set(Path(target.output.root).iterdir())
    trust.now = commands[0]["timestamp"]
    altered = {**commands[0], "quantity": "0.5"}
    with pytest.raises(f.Refused): store.execute(altered, projection_required=True)
    assert set(Path(target.output.root).iterdir()) == before


def test_failed_projection_ack_cannot_be_forged_by_success_dict(bundle, monkeypatch):
    store, trust, target, _, _, service, commands, _ = bundle
    monkeypatch.setattr(target, "publish", lambda *args: {"status": "SUCCESS"})
    trust.now = commands[0]["timestamp"]
    with pytest.raises(f.Refused): store.execute(commands[0], projection_required=True)
    assert service.try_publish("2026-10-23", trust.now)["status"] == "UNKNOWN"


def test_report_untrusted_clock_and_preinception_date_refused(bundle):
    complete(bundle)
    _, trust, _, _, _, service, _, _ = bundle
    assert service.try_publish("2026-10-23", trust.now + 1)["status"] == "UNKNOWN"
    assert service.try_publish("2026-10-22", trust.now)["status"] == "UNKNOWN"


def test_unrequired_projection_is_explicit_not_projection_success(bundle):
    store, trust, _, _, _, service, commands, _ = bundle
    trust.now = commands[0]["timestamp"]
    store.execute(commands[0])
    trust.now = 1792814400
    report = service.publish("2026-10-23", trust.now)["report"]
    assert report["projection_status"] == "NOT_REQUIRED"
    assert report["projection_counts"] == {"required": 0, "acknowledged": 0, "not_required": 1}


REPORT_CHILD = r"""
import sys,os,json,importlib.util
from pathlib import Path
repo=Path(sys.argv[1]);sys.path.insert(0,str(repo/'backend'))
spec=importlib.util.spec_from_file_location('fs3',repo/'scripts/volume_inspector/financial_reporting.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
base=Path(sys.argv[2]);point=sys.argv[3]
class Pins:
 def __init__(self,path):self.path=path
 def current(self):return json.loads(self.path.read_text())
 def check_clock(self,t):
  if t!=1792814400:raise ValueError('Test clock')
 def advance(self,old,new):
  if old!=self.current():raise ValueError('Test CAS')
  self.path.write_text(json.dumps(new))
  if self.path.name=='report-pin.json' and point=='afterpin':os._exit(24)
fp=Pins(base/'financial-pin.json');rp=Pins(base/'report-pin.json')
target=m.ProjectionTarget(str(base/'projection'),json.loads((base/'projection-id.json').read_text()))
store=m.f.FinancialRecordStore(str(base/'financial'),fp,projection=target)
archive=m.ReportArchive(str(base/'reports'),rp)
original=archive.output.write_bound
def write(leaf,raw):
 if leaf.endswith('-report.json') and point=='before':os._exit(24)
 binding=original(leaf,raw)
 if leaf.endswith('-report.json') and point=='after':os._exit(24)
 return binding
archive.output.write_bound=write
m.ReportService(store,archive).publish('2026-10-23',1792814400)
os._exit(25)
"""


@pytest.mark.parametrize("point", ["before", "after", "afterpin", "complete"])
def test_abrupt_report_process_restart_never_falsely_clean(bundle, tmp_path, point):
    from test_quality_dips_financial_records_native import helper
    complete(bundle)
    store, trust, target, _archive, rp, service, _, _ = bundle
    (tmp_path / "financial-pin.json").write_text(json.dumps(trust.pin))
    (tmp_path / "report-pin.json").write_text(json.dumps(rp.pin))
    (tmp_path / "projection-id.json").write_text(json.dumps(target.expected_root))
    before = len(list(Path(store.output.root).glob("*-record.json")))
    code, _, err = helper([sys.executable, "-I", "-B", "-c", REPORT_CHILD, str(REPO), str(tmp_path), point], tmp_path)
    assert code == (25 if point == "complete" else 24), err
    rp.pin = json.loads((tmp_path / "report-pin.json").read_text())
    if point == "complete":
        reports = service.history()
        assert reports == [service.publish("2026-10-23", trust.now)]
    else:
        result = service.try_publish("2026-10-23", trust.now)
        assert result["status"] == "UNKNOWN" and result["cash"] is None
        assert service.try_publish("2026-10-23", trust.now)["status"] == "UNKNOWN"
    assert len(list(Path(store.output.root).glob("*-record.json"))) == before


def test_report_capacity_refuses_without_overwriting_versions(bundle, monkeypatch):
    complete(bundle)
    _, trust, _, archive, _, service, _, _ = bundle
    first = service.publish("2026-10-23", trust.now)
    monkeypatch.setattr(m, "MAX_REPORTS", 1)
    trust.now += 1
    assert service.try_publish("2026-10-23", trust.now)["status"] == "UNKNOWN"
    assert service.history() == [first]
    assert len(list(Path(archive.output.root).glob("*-report.json"))) == 1



def test_fractional_quantity_and_exact_fee_remainder_accounting(bundle):
    store, trust, _, _, _, service, commands, _ = bundle
    position = None
    for index, (quantity, price) in enumerate([("0.125", "100.01"), ("0.03125", "101.17"), ("0.09375", "98.58")]):
        c = copy.deepcopy(commands[index])
        c["quantity"] = quantity
        c["quote"]["price"] = price
        trust.now = c["timestamp"]
        if index: c["position_id"] = position
        position = store.execute(c, projection_required=True)["position_id"]
    trust.now = 1792814400
    report = service.publish("2026-10-23", trust.now)["report"]
    assert Decimal(report["realized"]["costs"]) == Decimal("0.010001")
    assert Decimal(report["realized"]["net"]) == Decimal("-0.1078135")
    assert Decimal(report["cash"]["closing"]) == Decimal("999.8921865")
    assert Decimal(report["realized"]["fees"]) + Decimal(report["realized"]["slippage"]) == Decimal(report["realized"]["costs"])
    assert not report["open_positions"]


def test_perpetual_report_has_separate_cash_semantics(tmp_path):
    case = json.loads((REPO / "tests/fixtures/fs1/legacy-synthetic-golden.json").read_text())["cases"][1]
    manifest = case["manifest"]
    trust = Pins(f.FinancialRecordStore.provision_disposable(str(tmp_path / "perps"), manifest))
    store = f.FinancialRecordStore(str(tmp_path / "perps"), trust)
    scope = {"schema": "FS3_REPORT_SCOPE_V1", "account_id": "separate-perps-fixture", "epoch": manifest["epoch"],
             "policy_digest": f.digest(manifest), "timezone": manifest["timezone"]}
    rp = Pins(m.ReportArchive.provision_disposable(str(tmp_path / "perps-reports"), scope, manifest))
    archive = m.ReportArchive(str(tmp_path / "perps-reports"), rp)
    try:
        for row in case["sql_rows"]:
            c = f.strict(row[2])
            trust.now = c["timestamp"]
            store.execute(c)
        trust.now = int(datetime(2026, 10, 24, tzinfo=ZoneInfo(manifest["timezone"])).timestamp())
        report = m.ReportService(store, archive).publish("2026-10-23", trust.now)["report"]
        assert Decimal(report["cash"]["closing"]) == Decimal(case["snapshot"]["cash"])
        assert report["account_id"] == "separate-perps-fixture" and report["strategy"] == "HYPERLIQUID_MANUAL"
    finally:
        store.close()
        archive.close()
