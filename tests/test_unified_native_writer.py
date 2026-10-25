"""Actual native FS2/FS3 writers plus disposable durable coordination; no enrollment."""
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

import pytest
from app.services.paper_financial_replay import digest
from app.services.paper_writer_fixture import (
    _validated_operations,
    provision_fixture_writers,
)
from app.services.unified_native_writer import (
    CanonicalWriterLane,
    NativeFinancialWriter,
)
from app.services.unified_paper_runtime import UnifiedPaperRuntime
from test_fs3_financial_reporting_native import m
from test_perp_financial_v2 import entry, exit_command, funding, manifest
from test_quality_dips_financial_records_native import TestPins, f
from test_unified_paper_runtime import Installation, Lane, accounts, policy


class FixtureAuthority:
    def __init__(self, store, pins): self.store, self.pins, self.reserved = store, pins, None
    def verify_components(self, binding): return binding["store"] is self.store
    def verify_cut(self, binding, cut): return cut["root"] == self.pins.current()["root"]
    def verify_proposal(self, binding, proposal, observation, cut): return proposal["strategy_ref"] == "SYNTHETIC_EXISTING_PLANNER_INPUT"
    def verify_reservation(self, binding, proposal, reservation, cut): return reservation == self.reserved
    def verify_lane(self, binding, components): return components["writer"].store is self.store
    def verify_drain(self, binding, cut, result): return not any(Decimal(p["remaining"]) > 0 for p in cut["state"]["positions"].values())


class FixtureCustody:
    """Existing cooperative writer registry, not independent operational custody."""
    def __init__(self, path, writer, authority, clock):
        self.path, self.writer, self.authority, self.clock = path, writer, authority, clock
        self.policy = policy()
        self.policy.update(schema="ATLAS_PAPER_PORTFOLIO_RISK_V2", perp_collateral_model="INITIAL_RESERVE_CASH_SETTLED_FUNDING_V2")
        self.fail_ack = False

    def cut(self, state, head):
        rows = accounts()
        for row in rows: row["at"] = self.clock()
        target = rows[1]
        target.update(epoch=manifest()["epoch"], head=head, revision=state["revision"])
        for ident, p in state["positions"].items():
            qty = Decimal(p["remaining"])
            if not qty: continue
            # Explicit synthetic USD/USDC conversion at 1 for this fixture only.
            # Nothing here establishes real parity or provider fee acceptance.
            mark, reserve = Decimal(p["mark"]), Decimal(p["margin"])
            gain = (mark - Decimal(p["entry"])) * qty * (1 if p["side"] == "LONG" else -1)
            funded = Decimal(p["remaining_funding"])
            d = {"schema": "ATLAS_PERP_RISK_EVIDENCE_V2", "margin_mode": "INITIAL_RESERVE_CASH_SETTLED_FUNDING_V2",
                 "leverage": p["leverage"], "max_leverage": "2", "notional": str(mark * qty), "collateral": str(reserve),
                 "maintenance_margin": str(mark * qty * Decimal(".05")), "unrealized_pnl": str(gain),
                 "funding_cash": str(funded), "fees_cash": p["fees"], "slippage_cash": p["slippage"],
                 "equity": str(reserve + gain + funded), "stress_loss_cash": str(qty * Decimal(p["risk_price"])),
                 "funding_complete": p["next_funding"] > self.clock(), "fee_schedule_id": "synthetic-fees",
                 "funding_cut": str(p["next_funding"]), "mark_id": str(p["mark_at"]), "book_id": "synthetic-book"}
            target["positions"].append({"id": ident, "instrument_id": "HL:" + p["symbol"], "side": p["side"],
                "quantity": str(qty), "gross_usd": str(mark * qty), "loss_usd": str(qty * Decimal(p["risk_price"])),
                "reserved_usd": str(reserve), "derivatives": d})
        target["committed_usd"] = str(sum(Decimal(p["reserved_usd"]) for p in target["positions"]))
        return rows

    def verify_restart(self, grant):
        with sqlite3.connect(self.path) as db:
            return db.execute("SELECT stopped FROM control").fetchall() == [(0,)] and all(r[3] == 1 for r in _validated_operations(db))

    def close_entry_admission(self, grant):
        with sqlite3.connect(self.path) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT stopped FROM control").fetchall() not in ([(0,)], [(1,)]): return False
            db.execute("UPDATE control SET stopped=1")
        return True

    def verify_drain(self, grant):
        with sqlite3.connect(self.path) as db:
            roster = db.execute("SELECT id,incarnation,uncertain FROM writer_roster ORDER BY id").fetchall()
            return (roster == [("perp", "fixture-incarnation", 0), ("qd", "fixture-incarnation", 0)]
                    and db.execute("SELECT stopped FROM control").fetchall() == [(1,)]
                    and all(row[3] == 1 for row in _validated_operations(db)))

    @contextmanager
    def lease(self, request):
        with sqlite3.connect(self.path, timeout=2) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            self.db, self.request = db, request
            yield self

    def verify(self, request):
        rows = _validated_operations(self.db)
        if any(r[3] == 0 for r in rows): return False
        if request["proposal"]["kind"] == "ENTRY" and self.db.execute("SELECT stopped FROM control").fetchall() != [(0,)]:
            return False
        prior = self.db.execute("SELECT acked,payload FROM writer_operations WHERE id=?", (request["proposal"]["operation_id"],)).fetchone()
        if prior:
            if prior != (1, digest(request)): raise ValueError("Conflicting acknowledged request")
            return True
        self.preview = self.writer.preview(request["proposal"], None)
        self.before = self.cut(self.preview["before"], self.preview["head"])
        self.projected = self.cut(self.preview["after"], digest(self.preview["after"]))
        return True

    def acknowledged(self, request):
        row = self.db.execute("SELECT acked,payload FROM writer_operations WHERE id=?", (request["proposal"]["operation_id"],)).fetchone()
        return {"state": "ACKNOWLEDGED", "binding": row[1]} if row and row[0] == 1 else None

    def verify_accounting(self, request):
        return self.preview["receipt"]["payload_digest"] == digest(request["proposal"]["command"])

    def reserve(self, request):
        key, payload = request["proposal"]["operation_id"], digest(request)
        prior = self.db.execute("SELECT acked,payload FROM writer_operations WHERE id=?", (key,)).fetchone()
        if prior:
            if prior[1] != payload: raise ValueError("Conflicting durable reservation")
            return {"state": "ACKNOWLEDGED" if prior[0] == 1 else "UNKNOWN", "binding": payload}
        self.db.execute("INSERT INTO writer_operations VALUES(?,?,?,0,?)", (key, "perp", "fixture-incarnation", payload))
        self.db.commit()  # PENDING is durable before any native financial effect.
        self.db.execute("BEGIN IMMEDIATE")
        result = {"state": "RESERVED", "binding": payload}
        self.authority.reserved = result
        return result

    def verify_receipt(self, request, receipt):
        return self.writer.store.operation_receipt(request["proposal"]["operation_id"], digest(request["proposal"]["command"])) == receipt

    def acknowledge(self, request, receipt):
        if self.fail_ack: return False
        self.db.execute("UPDATE writer_operations SET acked=1 WHERE id=?", (request["proposal"]["operation_id"],))
        self.db.commit()
        return True

    def replay(self, request, reservation):
        return self.writer.store.operation_receipt(request["proposal"]["operation_id"], digest(request["proposal"]["command"]))


@pytest.fixture
def bundle(tmp_path):
    root = Path(os.environ["ATLAS_D1_RUN_ROOT"])
    assert root.parent == Path(__file__).resolve().parents[1] / "logs/diagnostics"
    assert root.name.startswith("qd-fs3-report-projection-") and tmp_path.is_relative_to(root)
    source, projection = str(tmp_path / "source"), str(tmp_path / "projection")
    pins = TestPins(f.FinancialRecordStore.provision_disposable(source, manifest()))
    target = m.ProjectionTarget(projection, m.ProjectionTarget.provision_disposable(projection))
    store = f.FinancialRecordStore(source, pins, projection=target)
    authority = FixtureAuthority(store, pins)
    writer = NativeFinancialWriter(store=store, authority=authority, manifest=manifest(), execution_domain="DISPOSABLE_TEST")
    dbpath = str(tmp_path / "writers.sqlite")
    with sqlite3.connect(dbpath) as db: db.execute("CREATE TABLE control(stopped INTEGER)"); db.execute("INSERT INTO control VALUES(0)")
    provision_fixture_writers(dbpath, {"perp": "fixture-incarnation", "qd": "fixture-incarnation"})
    now = [3602]
    custody = FixtureCustody(dbpath, writer, authority, lambda: now[0])
    scope = {"schema": "FS3_REPORT_SCOPE_V1", "account_id": "synthetic", "epoch": manifest()["epoch"],
             "policy_digest": digest(manifest()), "timezone": "UTC"}
    report_path = str(tmp_path / "reports")
    report_pins = TestPins(m.ReportArchive.provision_disposable(report_path, scope, manifest()))
    archive = m.ReportArchive(report_path, report_pins)
    reports = m.ReportService(store, archive)
    lane = CanonicalWriterLane(writer=writer, observer=Lane("HYPERLIQUID"), planner=object(), shutdown=Lane("HYPERLIQUID"), reports=reports)
    r = UnifiedPaperRuntime(lanes={"QUALITY_DIPS": Lane("QUALITY_DIPS", closed=True), "HYPERLIQUID": lane},
                            installation=Installation(), portfolio=custody, clock=lambda: now[0])
    r.start({"test_only": True})
    try: yield r, store, pins, now, writer, custody
    finally: store.close(); target.close(); archive.close()


def submit(bundle, command):
    r, store, pins, now, _, _ = bundle
    now[0] = pins.now = command["timestamp"]
    r.observations["HYPERLIQUID"] = {"at": now[0], "connection": "CONNECTED", "session": "OPEN"}
    proposal = {"operation_id": command["operation_id"], "kind": command["kind"], "command": command,
                "source_head": store.verified_cut()["head"], "strategy_ref": "SYNTHETIC_EXISTING_PLANNER_INPUT"}
    return r.dispatch("HYPERLIQUID", proposal)


def test_acknowledged_native_retry_never_invokes_execute_again(bundle, monkeypatch):
    r, store, pins, now, _, _ = bundle
    now[0] = pins.now = 3602
    r.observations["HYPERLIQUID"] = {"at": 3602, "connection": "CONNECTED", "session": "OPEN"}
    proposal = {"operation_id": "entry", "kind": "ENTRY", "command": entry(), "source_head": store.verified_cut()["head"],
                "strategy_ref": "SYNTHETIC_EXISTING_PLANNER_INPUT"}
    first = r.dispatch("HYPERLIQUID", proposal)
    def forbidden(*args, **kwargs): raise AssertionError("Acknowledged retry invoked a writer")
    monkeypatch.setattr(store, "execute", forbidden)
    assert r.dispatch("HYPERLIQUID", proposal) == first


def test_native_writer_default_refuses():
    with pytest.raises(ValueError): NativeFinancialWriter()


@pytest.mark.parametrize("method,args", [("verified_cut", ()), ("preview", ({},)), ("operation_receipt", ("id", "digest"))])
def test_new_test_inspection_methods_cannot_bypass_operational_admission(method, args):
    # Constructor-free: refusal must precede every handle, authority and file read.
    op = f.FinancialRecordStore.__new__(f.FinancialRecordStore)
    op.record_versions = {"pin": "QD_AUTO_OP_PIN_V1"}
    with pytest.raises(ValueError, match="NOT_ENROLLED"): getattr(op, method)(*args)


@pytest.mark.parametrize("method", ["verified_cut", "preview", "operation_receipt"])
def test_source_inspection_never_consumes_abandonment_or_publishes_latch(method, bundle, monkeypatch):
    _, store, _, _, _, _ = bundle
    root = Path(store.output.root)
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    def forbidden(*args): raise AssertionError("Read must not touch writer admission or publish a latch")
    monkeypatch.setattr(store.coordinator, "wait", forbidden)
    monkeypatch.setattr(store, "_latch", forbidden)
    if method == "operation_receipt":
        with pytest.raises(ValueError): store.operation_receipt("missing", "digest")
    elif method == "preview": store.preview(entry())
    else: store.verified_cut()
    assert {p.name: p.read_bytes() for p in root.iterdir()} == before


def test_unified_native_entry_partial_funding_exit(bundle):
    r, store, _, _, _, _ = bundle
    class View:
        manifest = globals()["manifest"]()
        def snapshot(self): return store.snapshot()["state"]
    view = View()
    submit(bundle, entry())
    submit(bundle, exit_command(view, "0.2"))
    r.pause()
    submit(bundle, funding(view))
    submit(bundle, exit_command(view, "0.3", 7202, "final", "104"))
    assert Decimal(store.snapshot()["state"]["cash"]) == Decimal("1001.52936")
    assert r.portfolio.verify_restart(r.grant)


def test_native_preview_and_receipt_reads_do_not_publish(bundle):
    _, store, _, _, writer, _ = bundle
    root = Path(store.output.root)
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    cut = store.verified_cut()
    proposal = {"operation_id": "entry", "kind": "ENTRY", "command": entry(), "source_head": cut["head"],
                "strategy_ref": "SYNTHETIC_EXISTING_PLANNER_INPUT"}
    writer.preview(proposal, None)
    assert {p.name: p.read_bytes() for p in root.iterdir()} == before
    with pytest.raises(ValueError): store.operation_receipt("entry", digest(entry()))
    with pytest.raises(ValueError): NativeFinancialWriter(store=store, authority=writer.authority, manifest=manifest(), execution_domain="LOCAL_ENROLLED")


def test_lost_cross_store_ack_never_reapplies_native_effect(bundle):
    r, store, _, _, _, custody = bundle
    custody.fail_ack = True
    with pytest.raises(ValueError, match="UNCERTAIN"): submit(bundle, entry())
    assert store.snapshot()["state"]["revision"] == 1 and not custody.verify_restart(r.grant)
    with pytest.raises(ValueError): submit(bundle, entry())
    assert store.snapshot()["state"]["revision"] == 1


def test_false_flat_shutdown_and_component_substitution_refuse(bundle):
    r, _, _, _, _, _ = bundle
    submit(bundle, entry())
    assert r.stop()["state"] == "STOP_INCOMPLETE"
    lane = r.lanes["HYPERLIQUID"]
    lane.planner = object()
    with pytest.raises(ValueError, match="REPLACED"): lane.verify_proposal({}, None)


def test_native_late_funding_needs_separate_recovery_verifier(bundle):
    from test_perp_funding_recovery import recovery
    r, store, pins, now, writer, _ = bundle
    submit(bundle, entry())
    class View:
        manifest = globals()["manifest"]()
        def snapshot(self): return store.snapshot()["state"]
    command = recovery(View())
    pins.now = now[0] = command["timestamp"]
    proposal = {"operation_id": command["operation_id"], "kind": "FUNDING", "command": command,
                "source_head": store.verified_cut()["head"], "strategy_ref": "SYNTHETIC_EXISTING_PLANNER_INPUT"}
    with pytest.raises(ValueError, match="RECOVERY_AUTHORITY"): r.dispatch("HYPERLIQUID", proposal)
    assert store.snapshot()["state"]["revision"] == 1
    writer.authority.verify_recovery = lambda binding, p, cut: p["command"]["recovery"]["state_digest"] == digest(cut["state"])
    r.dispatch("HYPERLIQUID", proposal)
    assert store.snapshot()["state"]["funding"] == "-0.0500"


def test_native_margin_policy_is_not_authorized_by_metadata_alone(bundle):
    from test_perp_margin_tiers import tier_policy
    _, store, _, _, writer, _ = bundle
    c = entry()
    c["schema"] = "PAPER_PERP_MARGIN_ENTRY_V1"
    c["evidence"]["margin_policy"] = tier_policy()
    with pytest.raises(ValueError, match="MARGIN_AUTHORITY"): submit(bundle, c)
    assert store.snapshot()["state"]["revision"] == 0
    writer.authority.verify_margin_policy = lambda binding, proposal, cut: proposal["command"]["evidence"]["margin_policy"] == tier_policy()
    submit(bundle, c)
    assert Decimal(store.snapshot()["state"]["maintenance_margin"]) == Decimal("1.5")


def test_competing_native_writer_leaves_reservation_unknown(bundle, monkeypatch):
    r, store, _, _, writer, custody = bundle
    original = writer.dispatch
    def interfere(proposal, reservation):
        store.execute(entry("foreign-synthetic-writer"), projection_required=True)
        return original(proposal, reservation)
    monkeypatch.setattr(writer, "dispatch", interfere)
    with pytest.raises(ValueError, match="RESERVATION"): submit(bundle, entry())
    assert store.snapshot()["state"]["revision"] == 1
    assert r.uncertain and not custody.verify_restart(r.grant)
    assert r.stop()["state"] == "STOP_INCOMPLETE"


def test_two_supervisors_cannot_duplicate_a_native_effect(bundle):
    r, store, pins, now, writer, custody = bundle
    other_custody = FixtureCustody(custody.path, writer, writer.authority, r.clock)
    other = UnifiedPaperRuntime(lanes=r.lanes, installation=Installation(), portfolio=other_custody, clock=r.clock)
    other.start({"test_only": True})
    pins.now = now[0] = 3602
    proposal = {"operation_id": "entry", "kind": "ENTRY", "command": entry(), "source_head": store.verified_cut()["head"],
                "strategy_ref": "SYNTHETIC_EXISTING_PLANNER_INPUT"}
    for runtime in (r, other):
        runtime.observations["HYPERLIQUID"] = {"at": 3602, "connection": "CONNECTED", "session": "OPEN"}
    def execute(runtime):
        try: return runtime.dispatch("HYPERLIQUID", proposal)
        except ValueError as exc: return exc
    with ThreadPoolExecutor(2) as pool: results = list(pool.map(execute, (r, other)))
    assert any(type(result) is dict for result in results)
    assert store.snapshot()["state"]["revision"] == 1
    assert custody.verify_restart(r.grant)


def test_native_partial_ioc_requires_explicit_execution_model(bundle):
    from test_perp_ioc_partial_entry import ioc
    r, store, _, _, writer, _ = bundle
    with pytest.raises(ValueError, match="EXECUTION_POLICY"): submit(bundle, ioc())
    assert store.snapshot()["state"]["revision"] == 0
    writer.authority.verify_execution_policy = lambda binding, proposal, cut: proposal["command"]["evidence"]["ioc"]["schema"] == "PAPER_IOC_CANCEL_REMAINDER_V1"
    submit(bundle, ioc())
    assert next(iter(store.snapshot()["state"]["positions"].values()))["ioc"]["cancelled_quantity"] == "0.4"
    assert r.stop()["state"] == "STOP_INCOMPLETE"


def test_combined_ioc_tiers_funding_exit_and_drain(bundle):
    from test_perp_ioc_partial_entry import ioc
    from test_perp_margin_tiers import tier_policy
    r, store, pins, now, writer, _ = bundle
    writer.authority.verify_execution_policy = lambda *args: True  # Synthetic, confined authority.
    writer.authority.verify_margin_policy = lambda *args: True
    c = ioc()
    c["schema"] = "PAPER_PERP_IOC_MARGIN_ENTRY_V1"
    c["evidence"]["margin_policy"] = tier_policy()
    submit(bundle, c)
    assert Decimal(store.snapshot()["state"]["maintenance_margin"]) == Decimal("0.25")
    class View:
        manifest = globals()["manifest"]()
        def snapshot(self): return store.snapshot()["state"]
    view = View()
    submit(bundle, funding(view))
    submit(bundle, exit_command(view, "0.1", 7202, "final", "104"))
    pins.now = now[0] = 86400
    r.lanes["HYPERLIQUID"].reports.publish("1970-01-01", 86400)
    assert r.stop()["state"] == "STOPPED"
    assert store.snapshot()["state"]["positions"][next(iter(store.snapshot()["state"]["positions"]))]["remaining"] == "0.0"


def test_flat_without_report_is_incomplete_and_restart_requires_new_admission(bundle):
    r, store, _, _, _, _ = bundle
    submit(bundle, entry())
    class View:
        manifest = globals()["manifest"]()
        def snapshot(self): return store.snapshot()["state"]
    submit(bundle, exit_command(View()))
    assert r.stop()["state"] == "STOP_INCOMPLETE"
    assert not r.portfolio.verify_restart(r.grant)


def test_failed_global_closure_never_calls_lane_shutdown(bundle, monkeypatch):
    r, _, _, _, _, custody = bundle
    custody.close_entry_admission = lambda grant: False
    def forbidden(**kw): raise AssertionError("Unverified admission must precede shutdown")
    for lane in r.lanes.values(): monkeypatch.setattr(lane, "stop", forbidden)
    assert r.stop()["state"] == "STOP_INCOMPLETE"


def test_historical_report_with_current_head_cannot_certify_current_cash(bundle):
    r, store, pins, now, _, _ = bundle
    class View:
        manifest = globals()["manifest"]()
        def snapshot(self):
            state = store.snapshot()["state"]
            return {**state, "positions": {key: p for key, p in state["positions"].items() if Decimal(p["remaining"]) > 0}}
    view = View()
    submit(bundle, entry())
    submit(bundle, exit_command(view))
    c = entry("second-day-entry")
    c["expected_source_revision"] = store.snapshot()["state"]["revision"]
    c["timestamp"] = c["evidence"]["observed_at"] = 90001
    c["evidence"]["sequence"] = "second-day-book"
    submit(bundle, c)
    submit(bundle, exit_command(view, timestamp=90002, op="second-day-exit"))
    pins.now = now[0] = 172800
    doc = r.lanes["HYPERLIQUID"].reports.publish("1970-01-01", 172800)
    assert doc["report"]["status"] == "COMPLETE"
    assert doc["report"]["source"]["head"] == store.verified_cut()["head"]
    assert doc["report"]["source"]["cutoff_revision"] < store.snapshot()["state"]["revision"]
    assert r.stop()["state"] == "STOP_INCOMPLETE"


@pytest.mark.parametrize("mode", ["maker", "liquidation"])
def test_native_special_execution_needs_its_own_evidence_verifier(mode, bundle):
    from test_perp_execution_evidence import liquidation, maker
    _, store, _, _, writer, _ = bundle
    if mode == "liquidation":
        submit(bundle, entry())
        class View:
            manifest = globals()["manifest"]()
            def snapshot(self): return store.snapshot()["state"]
        command = liquidation(View())
    else: command = maker()
    before = store.snapshot()
    with pytest.raises(ValueError, match="EVIDENCE_REQUIRED"): submit(bundle, command)
    assert store.snapshot() == before
    setattr(writer.authority, "verify_maker_execution" if mode == "maker" else "verify_liquidation", lambda *args: True)
    submit(bundle, command)
    assert store.snapshot()["state"]["revision"] == before["state"]["revision"] + 1
