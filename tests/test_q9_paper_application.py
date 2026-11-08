import copy
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from app.services.paper_dashboard_demo import PaperDashboardDemo
from app.services.paper_epoch_fixture import create_epoch_fixture
from app.services.paper_portfolio_fixture import account_summary_fixture
from app.services.paper_runtime_boundary import (
    PaperBoundaryRefused,
    PaperRuntimeBoundary,
)
from app.services.paper_strategy_fixture import exit_command, quality_entry
from app.services.paper_summary_contract import body, portfolio_payload_fixture
from app.services.paper_write_request_contract import PaperWriteRequestContract
from app.services.paper_writer_fixture import (
    close_fixture_writers,
    drain_fixture_writers,
    fixture_writer_operation,
    provision_fixture_writers,
    run_fixture_writer,
)
from test_durable_partial_shutdown import fixture
from test_paper_epoch_fixture import STAMP, entry, manifest, quote
from test_paper_strategy_fixture import observation
from test_q7_paper_workflows import q7_native


def request(app, path="/", method="GET", query=""):
    response = []
    raw = b"".join(app({"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query},
                       lambda status, headers: response.append((status, dict(headers)))))
    return response[0][0], response[0][1], raw


def application(tmp_path):
    quality = create_epoch_fixture(tmp_path / "quality.sqlite", manifest("quality", "QUALITY_DIPS"))
    ack = quality.execute(quality_entry(quality, observation(), level="L1", notional="100",
                                       operation_id="quality-entry", timestamp=STAMP, manual=True))
    quality.execute(exit_command(quality, operation_id="partial", position_id=ack["position_id"], quantity="0.25",
                                quote=quote("110", "MSFT"), timestamp=STAMP, manual=True))
    perps, native, _, _ = q7_native(tmp_path)
    native.apply(entry(perps))
    def independently_read():
        return portfolio_payload_fixture([account_summary_fixture(quality, now=STAMP, max_age=30),
            account_summary_fixture(perps, reader=native, now=STAMP, max_age=30)])
    candidate = [independently_read()]
    boundary = PaperRuntimeBoundary(source=lambda: copy.deepcopy(candidate[0]), clock=lambda: STAMP,
        expected_accounts=[("QUALITY_DIPS", "quality"), ("HYPERLIQUID_MANUAL", "q7-perps")])
    def verify(raw):
        # Re-read and independently audit original fixture events/native projections,
        # not a signature or copied caller hash. Any concurrent change refuses.
        expected = body(independently_read()).encode()
        return hashlib.sha256(expected).hexdigest() if expected == raw else None
    return PaperDashboardDemo(boundary=boundary, verify=verify), candidate, quality, perps, native


def files(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_two_strategy_application_reads_are_pure_and_reconciled(tmp_path):
    app, _, quality, perps, _ = application(tmp_path)
    before = files(tmp_path)
    for _ in range(2):
        status, headers, html = request(app)
        assert status == "200 OK" and headers["Cache-Control"] == "no-store"
        assert "default-src 'none'" in headers["Content-Security-Policy"]
        for text in (b"QUALITY_DIPS / quality", b"HYPERLIQUID_MANUAL / q7-perps", b"MSFT:0.75", b"BTC:0.5",
                     b"Gross P&amp;L", b"INCOMPLETE", b"1000", b"927.48", b"separate allocations unavailable"):
            assert text in html
        status, _, raw = request(app, "/summary.json")
        assert status == "200 OK"
        payload = json.loads(raw)
        assert payload["portfolio_totals"] is None
        assert all(r["total_equity"] is None and not r["startup_authorized"] for r in payload["accounts"])
    assert files(tmp_path) == before
    assert quality.snapshot()["revision"] == 2 and perps.snapshot()["revision"] == 1


@pytest.mark.parametrize("damage", ["forged-cash", "version", "missing-head", "consolidation", "stale", "account"])
def test_untrusted_or_inconsistent_summaries_refuse(tmp_path, damage):
    app, candidate, _, _, _ = application(tmp_path)
    row = candidate[0]["accounts"][0]
    if damage == "forged-cash": row["reconciled_cash"] = "9000"  # Valid shape, fails independent source audit.
    if damage == "version": candidate[0]["schema"] = "V999"
    if damage == "missing-head": row["source_head"] = None
    if damage == "consolidation": candidate[0]["portfolio_totals"] = "2000"
    if damage == "stale": row["observed_at"] -= 60
    if damage == "account": row["epoch"] = "foreign"
    status, _, raw = request(app)
    assert status.startswith("503") and b"UNKNOWN" in raw and b"9000" not in raw


@pytest.mark.parametrize("method,path,query", [("POST", "/", ""), ("DELETE", "/summary.json", ""),
    ("GET", "/api/investments/quality-dips", ""), ("GET", "/start", ""), ("GET", "/", "refresh=1")])
def test_forbidden_requests_never_invoke_read_or_writer(method, path, query):
    class Forbidden:
        def snapshot(self):
            pytest.fail("No dependency invocation allowed")
    status, _, _ = request(PaperDashboardDemo(boundary=Forbidden()), path, method, query)
    assert status.startswith(("404", "405"))


def test_unbound_application_and_failed_verifier_never_cache_success(tmp_path):
    assert request(PaperDashboardDemo())[0].startswith("503")
    app, _, _, _, _ = application(tmp_path)
    assert request(app)[0] == "200 OK"
    app.verify = lambda raw: True  # A boolean approval is not a bound receipt.
    assert request(app)[0].startswith("503")
    def fail(raw):
        raise OSError("private fixture storage detail")
    app.verify = fail
    status, _, raw = request(app)
    assert status.startswith("503") and b"private" not in raw
    assert isinstance(app.last_failure, OSError)


def test_unknown_projection_remains_unknown_after_dashboard_read(tmp_path):
    app, candidate, _, perps, native = application(tmp_path)
    with perps.connect() as db:
        db.execute("UPDATE projections SET receipt=NULL")
    candidate[0]["accounts"][0] = account_summary_fixture(perps, reader=native, now=STAMP, max_age=30)
    before = files(tmp_path)
    status, _, raw = request(app)
    assert status == "200 OK" and b"UNKNOWN" in raw and b"Unavailable" in raw
    assert files(tmp_path) == before
    with pytest.raises(ValueError): native.apply(entry(perps))


@pytest.mark.parametrize("strategy", ["QUALITY_DIPS", "HYPERLIQUID_MANUAL"])
@pytest.mark.parametrize("action", ["ENTRY", "PARTIAL_EXIT", "FULL_EXIT"])
def test_valid_inert_write_contract_always_refuses(strategy, action):
    command = {"schema": "PAPER_WRITE_REQUEST_INERT_V1", "strategy": strategy, "epoch": "demo",
               "operation_id": "demo:op", "action": action, "position_id": None if action == "ENTRY" else "demo:position",
               "expected_source_revision": 1, "expected_source_head": "a" * 64, "receipt_schema": "PAPER_RECEIPT_FIXTURE_V1"}
    with pytest.raises(PaperBoundaryRefused, match="EXECUTION_DISABLED"):
        PaperWriteRequestContract(strategy=strategy, epoch="demo").submit(command)


@pytest.mark.parametrize("damage", ["missing", "authority", "foreign", "revision", "head", "position", "operation", "schema"])
def test_inert_write_expectations_cannot_be_substituted(damage):
    c = {"schema": "PAPER_WRITE_REQUEST_INERT_V1", "strategy": "QUALITY_DIPS", "epoch": "demo",
         "operation_id": "demo:op", "action": "FULL_EXIT", "position_id": "demo:p",
         "expected_source_revision": 1, "expected_source_head": "a" * 64, "receipt_schema": "PAPER_RECEIPT_FIXTURE_V1"}
    if damage == "missing": del c["operation_id"]
    if damage == "authority": c["approved"] = True
    if damage == "foreign": c["epoch"] = "other"
    if damage == "revision": c["expected_source_revision"] = True
    if damage == "head": c["expected_source_head"] = None
    if damage == "position": c["position_id"] = "foreign:p"
    if damage == "operation": c["operation_id"] = "foreign:op"
    if damage == "schema": c["receipt_schema"] = "UNVERSIONED"
    with pytest.raises(PaperBoundaryRefused) as error:
        PaperWriteRequestContract(strategy="QUALITY_DIPS", epoch="demo").submit(c)
    assert "EXECUTION_DISABLED" not in str(error.value)


@pytest.mark.parametrize("damage", ["pending", "missing-owner", "competitor", "restart"])
def test_disposable_shutdown_requires_complete_writer_roster(tmp_path, damage):
    path, _ = fixture(tmp_path)
    roster = {"manual": "one", "journal": "two"}
    provision_fixture_writers(path, roster)
    if damage == "pending":
        fixture_writer_operation(path, writer="manual", incarnation="one", operation="unack", payload="a" * 64)
        assert drain_fixture_writers(path, roster, timeout=0)["status"] == "TIMED_OUT"
        with pytest.raises(ValueError):
            fixture_writer_operation(path, writer="journal", incarnation="two", operation="late", payload="b" * 64)
        assert close_fixture_writers(path, roster)["status"] == "INCOMPLETE"
        return
    with sqlite3.connect(path) as db:
        if damage == "missing-owner": db.execute("DELETE FROM writer_roster WHERE id='journal'")
        if damage == "competitor": db.execute("INSERT INTO writer_roster VALUES('foreign','other',0)")
        if damage == "restart": db.execute("UPDATE writer_roster SET incarnation='new' WHERE id='manual'")
    with pytest.raises(ValueError): close_fixture_writers(path, roster)


def test_demo_and_write_contract_not_registered_in_operational_code():
    root = Path(__file__).resolve().parents[1] / "backend/app"
    for p in [root / "main.py", *(root / "api").glob("*.py")]:
        text = p.read_text(encoding="utf-8-sig")
        assert "paper_dashboard_demo" not in text and "paper_write_request_contract" not in text
    for name in ("paper_dashboard_demo.py", "paper_write_request_contract.py"):
        tree = (root / "services" / name).read_text(encoding="utf-8")
        for forbidden in ("paper_epoch_fixture", "paper_journal", "perp_manual_service", "investment_board", "uvicorn", "subprocess"):
            assert forbidden not in tree


def test_writer_projection_unknown_blocks_drain_report_restart_and_read_recovery(tmp_path):
    control, _ = fixture(tmp_path)
    roster = {"native-projection": "retained-fixture"}
    provision_fixture_writers(control, roster)
    store, bridge, _, _ = q7_native(tmp_path)
    command = entry(store)
    calls = []
    def mutation():
        calls.append(1)
        def interrupted(phase):
            if phase == "before_projection":
                raise OSError("fixture interruption")
        bridge.apply(command, fault=interrupted)
    args = {"writer": "native-projection", "incarnation": "retained-fixture", "operation": "entry",
            "payload": hashlib.sha256(body(command).encode()).hexdigest(), "mutation": mutation}
    with pytest.raises(OSError): run_fixture_writer(control, **args)
    assert close_fixture_writers(control, roster)["status"] == "INCOMPLETE"
    with pytest.raises(ValueError): run_fixture_writer(control, **args)
    assert calls == [1]
    summary = account_summary_fixture(store, reader=bridge, now=STAMP, max_age=30)
    assert summary["state"] == "UNKNOWN" and summary["reconciled_cash"] is None
    with pytest.raises(ValueError): store.daily_report("2026-10-23")
    with pytest.raises(ValueError):
        fixture_writer_operation(control, **{k: v for k, v in args.items() if k != "mutation" and k != "operation"}, operation="restart")
    with store.connect(readonly=True) as db:
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
    assert close_fixture_writers(control, roster)["status"] == "INCOMPLETE"


def test_clean_fixture_report_read_requires_all_fills_and_never_authorizes_shutdown(tmp_path):
    app, candidate, quality, perps, native = application(tmp_path)
    for store, reader in ((quality, quality), (perps, native)):
        for ident, position in reader.snapshot()["positions"].items():
            command = exit_command(store, operation_id="final", position_id=ident, quantity=position["remaining"],
                                   quote=quote("120", position["symbol"]), timestamp=STAMP, manual=True)
            if store is perps: native.apply(command)
            else: store.execute(command)
        assert store.daily_report("2026-10-23")["state"] == "RECONCILED_FIXTURE_ONLY"
    candidate[0] = portfolio_payload_fixture([account_summary_fixture(quality, now=STAMP, max_age=30),
        account_summary_fixture(perps, reader=native, now=STAMP, max_age=30)])
    status, _, raw = request(app, "/summary.json")
    assert status == "200 OK"
    for row in json.loads(raw)["accounts"]:
        assert row["state"] == "RECONCILED_FIXTURE_ONLY" and not row["remaining_positions"]
        assert not row["startup_authorized"] and not row["shutdown_authorized"]
