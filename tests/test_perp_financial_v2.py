"""Synthetic USDC evidence only; no operational authority or provider requests."""
import copy
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from app.services.paper_epoch_fixture import EpochFixture, create_epoch_fixture
from app.services.paper_financial_audit import audit_financial_events
from app.services.paper_financial_replay import event_stream_record


def manifest():
    return {"schema": "PAPER_EPOCH_PERP_FIXTURE_V2", "epoch": "synthetic-usdc", "strategy": "HYPERLIQUID_PAPER",
                "currency": "USDC", "opening_cash": "1000", "opened_at": 3601, "timezone": "UTC", "release": "test",
                "provenance": "SYNTHETIC", "initial_net_r": "0", "cost_policy": "PERP_QUOTE_PLUS_CASH_COST_V2",
                "perp_policy": {"symbols": ["BTC", "ETH", "SOL"], "max_positions": 3, "max_leverage": "2",
                                 "max_notional": "100", "risk_limit": "1", "session_stop": "-3", "participation": "0.1",
                                 "maintenance_rate": "0.05", "slippage_bps": "2", "maker_bps": "1", "taker_bps": "2",
                                 "fee_schedule_id": "synthetic-fees", "instrument_cut": "synthetic-meta",
                                 "market_source": "synthetic-book", "funding_source": "synthetic-funding"}}


def entry(op="entry", side="LONG"):
    return {"schema": "PAPER_PERP_COMMAND_V2", "epoch": "synthetic-usdc", "operation_id": op, "kind": "ENTRY",
                "expected_source_revision": 0, "timestamp": 3602, "symbol": "BTC", "side": side, "quantity": "0.5",
                "leverage": "2", "risk_price": "1", "origin_ref": op, "liquidity": "TAKER",
                "evidence": {"source": "synthetic-book", "instrument_cut": "synthetic-meta", "symbol": "BTC",
                              "observed_at": 3602, "sequence": "book-1", "bid": "99", "ask": "100", "bid_size": "10",
                              "ask_size": "10", "mark": "100", "fee_schedule_id": "synthetic-fees"}}


def action(store, kind, op, timestamp, **kw):
    s = store.snapshot()
    pid, p = next(iter(s["positions"].items()))
    return dict(schema="PAPER_PERP_COMMAND_V2", epoch=store.manifest["epoch"], operation_id=op, kind=kind,
                expected_source_revision=s["revision"], timestamp=timestamp, position_id=pid,
                expected_position_revision=p["revision"], **kw)


def exit_command(store, qty="0.5", timestamp=3603, op="exit", price="102"):
    q = entry()["evidence"]
    q.update(bid=price, ask=str(Decimal(price) + 1), observed_at=timestamp, sequence=op)
    return action(store, "EXIT", op, timestamp, quantity=qty, liquidity="TAKER", evidence=q)


def funding(store, at=7200, rate="0.001"):
    return action(store, "FUNDING", f"funding-{at}", at + 1,
                  evidence={"source": "synthetic-funding", "symbol": "BTC", "settlement_at": at,
                                "interval_seconds": 3600, "rate": rate, "oracle": "100", "source_id": f"hour-{at}"})


def audit(store):
    with store.connect(readonly=True) as db:
        rows = [event_stream_record(*r) for r in db.execute("SELECT * FROM events ORDER BY revision")]
    return audit_financial_events(store.manifest, rows, store.snapshot())


def test_margin_cash_and_partial_funding_conservation(tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    st.execute(entry())
    s = st.snapshot()
    assert Decimal(s["cash"]) == Decimal("999.98")
    assert Decimal(s["reserved_margin"]) == 25
    assert Decimal(s["available_cash"]) == Decimal("974.98")
    st.execute(exit_command(st, "0.2"))
    st.execute(funding(st))
    st.execute(exit_command(st, "0.3", 7202, "final", "104"))
    s = st.snapshot()
    assert Decimal(s["gross"]) == Decimal("1.6")
    assert Decimal(s["funding"]) == Decimal("-0.03")
    assert Decimal(s["fees"]) == Decimal("0.02032")
    assert Decimal(s["slippage"]) == Decimal("0.02032")
    assert Decimal(s["cash"]) == Decimal("1001.52936")
    assert Decimal(s["reserved_margin"]) == 0
    assert audit(st)["source_revision"] == 4
    report = st.daily_report("1970-01-01")
    assert Decimal(report["realized_net"]) == Decimal(s["net"])
    assert report["currency"] == "USDC"


@pytest.mark.parametrize("side", ["LONG", "SHORT"])
def test_idempotent_restart_and_independent_audit(side, tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    c = entry(side=side)
    with ThreadPoolExecutor(2) as pool:
        receipts = list(pool.map(st.execute, [c, c]))
    assert receipts[0] == receipts[1]
    restarted = EpochFixture(st.path, expected_manifest=manifest())
    restarted.execute(funding(restarted))
    restarted.execute(exit_command(restarted, timestamp=7202))
    assert audit(restarted)["position_count"] == 1
    assert restarted.snapshot()["positions"][receipts[0]["position_id"]]["remaining"] == "0.0"


@pytest.mark.parametrize("damage", ["missing-funding", "stale-book", "wrong-source", "fee-substitution",
    "size", "leverage", "risk", "boundary", "unknown-field"])
def test_incomplete_evidence_refuses_without_mutation(damage, tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    c = entry()
    if damage == "missing-funding":
        st.execute(c)
        c = exit_command(st, timestamp=7202)
    elif damage == "stale-book": c["timestamp"] += 31
    elif damage == "wrong-source": c["evidence"]["source"] = "foreign"
    elif damage == "fee-substitution": c["evidence"]["fee_schedule_id"] = "free"
    elif damage == "size": c["evidence"]["ask_size"] = "0.1"
    elif damage == "leverage": c["leverage"] = "3"
    elif damage == "risk": c["risk_price"] = "3"
    elif damage == "boundary": c["timestamp"] = c["evidence"]["observed_at"] = 7200
    else: c["authority"] = True
    before = st.snapshot()
    with pytest.raises(ValueError): st.execute(c)
    assert st.snapshot() == before


def test_unknown_projection_blocks_replay_and_reporting(tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    c = entry()
    st.execute(c, projection_required=True)
    with pytest.raises(ValueError, match="UNKNOWN"): st.execute(c)
    with pytest.raises(ValueError, match="UNKNOWN"): st.daily_report("1970-01-01")


@pytest.mark.parametrize("phase,committed", [("before_event", False), ("before_commit", False), ("after_commit", True)])
def test_transaction_failure_boundaries(phase, committed, tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    def crash(where):
        if where == phase: raise OSError("synthetic interruption")
    with pytest.raises(OSError): st.execute(entry(), fault=crash)
    assert st.snapshot()["revision"] == int(committed)
    st.execute(entry())
    assert st.snapshot()["revision"] == 1
    audit(st)


def test_independent_audit_rejects_altered_margin_and_funding(tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    st.execute(entry())
    st.execute(funding(st))
    with st.connect(readonly=True) as db:
        rows = [event_stream_record(*r) for r in db.execute("SELECT * FROM events ORDER BY revision")]
    for field in ("cash", "reserved_margin", "available_cash", "funding", "fees", "net"):
        damaged = copy.deepcopy(st.snapshot())
        damaged[field] = "99999"
        with pytest.raises(ValueError): audit_financial_events(st.manifest, rows, damaged)


def test_mark_warning_never_fabricates_liquidation(tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    st.execute(entry())
    mark = action(st, "MARK", "mark", 3603, evidence={"source": "synthetic-book", "instrument_cut": "synthetic-meta",
                  "symbol": "BTC", "observed_at": 3603, "mark": "40", "source_id": "mark-2"})
    st.execute(mark)
    assert st.snapshot()["margin_warning"] is True
    assert Decimal(st.snapshot()["positions"][mark["position_id"]]["remaining"]) == Decimal("0.5")
    audit(st)
    c = exit_command(st)
    c["kind"] = "LIQUIDATION"
    with pytest.raises(ValueError, match="liquidation"): st.execute(c)


@pytest.mark.parametrize("rate", ["0", "-0.001", "0.001"])
def test_explicit_signed_funding_and_duplicate_interval(rate, tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    st.execute(entry())
    c = funding(st, rate=rate)
    receipt = st.execute(c)
    assert st.execute(c) == receipt
    second = funding(st, rate=rate)
    second["operation_id"] = "duplicated-settlement"
    with pytest.raises(ValueError): st.execute(second)
    assert Decimal(st.snapshot()["funding"]) == -Decimal(50) * Decimal(rate)
    audit(st)


def test_fs3_report_preserves_funding_and_refuses_omitted_intervals(tmp_path):
    from app.services.paper_daily_report import audit_daily_report, build_daily_report
    from app.services.paper_financial_replay import digest, replay_verified_events

    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    st.execute(entry())
    st.execute(funding(st))
    with st.connect(readonly=True) as db:
        rows = [event_stream_record(*r) for r in db.execute("SELECT * FROM events ORDER BY revision")]
    scope = {"schema": "FS3_REPORT_SCOPE_V1", "account_id": "synthetic", "epoch": st.manifest["epoch"],
             "policy_digest": digest(st.manifest), "timezone": "UTC"}
    pin = {"epoch": st.manifest["epoch"], "entries": ["synthetic-pin"] * len(rows), "root": [1, 2, 3], "inception": "synthetic"}
    report = build_daily_report(scope, st.manifest, pin, rows, "1970-01-01", 86400)
    assert report["status"] == "INCOMPLETE" and "FUNDING_HISTORY_INCOMPLETE" in report["reasons"]
    assert Decimal(report["realized"]["funding"]) == Decimal("-0.05")
    assert report["currency"] == "USDC" and report["valuation"] is None
    damaged = copy.deepcopy(report)
    damaged["realized"]["funding"] = "0"
    with pytest.raises(ValueError):
        audit_daily_report(damaged, scope, st.manifest, pin, rows, replay_verified_events(st.manifest, rows)[0])


@pytest.mark.parametrize("damage", ["boolean-position-revision", "missing-record", "duplicate-record", "wrong-funding-quantity", "hidden-margin-warning"])
def test_independent_source_and_position_completeness(damage, tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    st.execute(entry())
    with st.connect(readonly=True) as db:
        rows = [event_stream_record(*r) for r in db.execute("SELECT * FROM events ORDER BY revision")]
    snapshot = st.snapshot()
    if damage == "boolean-position-revision": next(iter(snapshot["positions"].values()))["revision"] = True
    elif damage == "missing-record": rows = []
    elif damage == "duplicate-record": rows += copy.deepcopy(rows)
    elif damage == "wrong-funding-quantity": next(iter(snapshot["positions"].values()))["remaining"] = "0.1"
    else: snapshot["margin_warning"] = True
    with pytest.raises(ValueError): audit_financial_events(st.manifest, rows, snapshot)


def test_fractional_partial_exit_uses_exact_risk_ratio_not_rounded_admission(tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    c = entry()
    c["quantity"] = "0.333"
    st.execute(c)
    st.execute(exit_command(st, "0.111"))
    result = st.snapshot()
    assert Decimal(result["positions"][next(iter(result["positions"]))]["remaining"]) == Decimal("0.222")
    assert result["net_r_display_only"] is True
    audit(st)


def test_settled_funding_loss_participates_in_remaining_position_margin_risk(tmp_path):
    st = create_epoch_fixture(tmp_path / "perp.db", manifest())
    st.execute(entry())
    st.execute(funding(st, rate="0.04"))
    st.execute(action(st, "MARK", "funded-mark", 7202,
                      evidence={"source": "synthetic-book", "instrument_cut": "synthetic-meta", "symbol": "BTC",
                                "observed_at": 7202, "mark": "55", "source_id": "mark-funding-risk"}))
    assert st.snapshot()["margin_warning"] is True
    audit(st)


@pytest.mark.parametrize("day,hours", [("2026-03-08", 23), ("2026-11-01", 25)])
def test_fs3_perp_calendar_dst_and_explicit_zero_funding(day, hours, tmp_path):
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    from app.services.paper_daily_report import build_daily_report
    from app.services.paper_financial_replay import digest

    local = datetime.fromisoformat(day).replace(tzinfo=ZoneInfo("America/New_York"))
    start, end = int(local.timestamp()), int((local + timedelta(days=1)).timestamp())
    m = manifest()
    m.update(opened_at=start + 1, timezone="America/New_York")
    st = create_epoch_fixture(tmp_path / "perp.db", m)
    c = entry()
    c["timestamp"] = c["evidence"]["observed_at"] = start + 2
    st.execute(c)
    for at in range(start + 3600, end, 3600):
        st.execute(funding(st, at, "0"))
    st.execute(exit_command(st, timestamp=end - 1, price="100"))
    with st.connect(readonly=True) as db:
        rows = [event_stream_record(*r) for r in db.execute("SELECT * FROM events ORDER BY revision")]
    pin = {"epoch": m["epoch"], "entries": ["synthetic"] * len(rows), "root": [1, 2, 3], "inception": "synthetic"}
    scope = {"schema": "FS3_REPORT_SCOPE_V1", "account_id": "synthetic", "epoch": m["epoch"],
             "policy_digest": digest(m), "timezone": m["timezone"]}
    report = build_daily_report(scope, m, pin, rows, day, end)
    assert report["period"]["end_exclusive"] - report["period"]["start"] == hours * 3600
    assert report["counts"]["funding"] == hours - 1
    assert report["status"] == "COMPLETE" and report["realized"]["funding"] == "0.0"
    assert report["cash"]["closing"] == st.snapshot()["cash"]
    audit(st)
