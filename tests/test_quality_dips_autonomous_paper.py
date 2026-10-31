"""Offline autonomous engine: disposable canonical stores and synthetic L1 only."""

import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from app.investment.quality_dips_candidate_evidence import CandidateEvidenceAdapter
from app.services.paper_epoch_fixture import EpochFixture, create_epoch_fixture
from app.services.paper_financial_replay import (
    apply_event,
    digest,
    number,
    strict,
)
from app.services.quality_dips_autonomous_paper import AutonomousPaper
from test_paper_epoch_fixture import manifest
from test_quality_dips_integration_v1 import bundle_for

STAMP = int(datetime(2026, 10, 26, 14, tzinfo=UTC).timestamp())


def setup(tmp_path, reopen=False, stamp=STAMP):
    now = [stamp]
    revoked = [False]
    m = manifest("synthetic-auto", "QUALITY_DIPS")
    m.update(
        schema="PAPER_EPOCH_AUTONOMOUS_QD_V1",
        opened_at=stamp,
        cost_policy="SIDE_NOTIONAL_FEE_SLIPPAGE_V1",
        autonomous_policy={
            "schema": "QD_AUTO_RISK_PARTIAL_THESIS_V1",
            "quote_age_seconds": 5,
            "max_spread_bps": "50",
            "participation": "0.5",
            "quantity_step": "0.001",
            "partial_fraction": "0.4",
            "max_session_seconds": 3600,
        },
    )
    ledger = (
        EpochFixture(tmp_path / "auto.sqlite", expected_manifest=m)
        if reopen
        else create_epoch_fixture(tmp_path / "auto.sqlite", m)
    )

    def proof(schema, payload):
        return {
            "schema": schema,
            "verified": True,
            "binding": digest(payload),
            "receipt_id": "EXPLICIT_SYNTHETIC_AUTHORITY",
        }

    adapter = CandidateEvidenceAdapter(
        ranking_authority=SimpleNamespace(
            verify_current=lambda v, now: proof("QD_RANKING_VERIFIED_V1", v)
        ),
        execution_authority=SimpleNamespace(
            verify=lambda v, now: proof("QD_EXECUTION_VERIFIED_V1", v)
        ),
    )
    session = SimpleNamespace(
        verify=lambda v, now: {
            **proof("QD_AUTO_SESSION_PROOF_V1", v),
            "verified": not revoked[0],
        }
    )
    source = SimpleNamespace(verify=lambda v, now: proof("QD_AUTO_SOURCE_PROOF_V1", v))

    def engine():
        return AutonomousPaper(
            ledger=EpochFixture(ledger.path, expected_manifest=m),
            candidates=adapter,
            session_authority=session,
            source_authority=source,
            clock=lambda: now[0],
        )

    n = SimpleNamespace(
        m=m,
        ledger=ledger,
        now=now,
        revoked=revoked,
        new=engine,
        grant={
            "schema": "QD_AUTO_SESSION_FIXTURE_V1",
            "session_id": "synthetic-session",
            "epoch": m["epoch"],
            "issued_at": stamp,
            "expires_at": stamp + 3600,
            "capabilities": ["AUTO_ENTRY", "AUTO_EXIT"],
            "feed_id": "synthetic-L1",
            "calendar_id": "synthetic-NYSE-2026",
        },
    )
    n.engine = engine()
    if not reopen:
        n.engine.start(n.grant)
    return n


def candidate(n, symbol="MSFT", asset="STOCK"):
    _, b, _ = bundle_for(symbol, asset)
    t = n.now[0]
    b["publication"].update(issued_at=t, expires_at=t + 300)
    b["quote"].update(
        effective_timestamp=datetime.fromtimestamp(t, UTC).isoformat(),
        execution_price="100",
    )
    b["observation"].update(
        source_timestamp=datetime.fromtimestamp(t, UTC).isoformat(),
        timestamp=datetime.fromtimestamp(t, UTC).isoformat(),
    )
    b["observation"]["prediction"].update(quality_score=80, fundamentals_score=80)
    b["observation"]["prediction"]["entry_ladder"]["levels"][0]["limit_price"] = 100.0
    return b


def quote(n, b, bid="99.9", ask="100"):
    day = datetime.fromtimestamp(n.now[0], UTC).date()
    return {
        "schema": "QD_AUTO_L1_V1",
        "provider_id": "SYNTHETIC_NOT_LIVE",
        "feed_id": "synthetic-L1",
        "entitlement_id": "FIXTURE_RIGHTS_NOT_REAL",
        "feed_scope": "VENUE",
        "delay_status": "REALTIME",
        "symbol": b["instrument"]["symbol"],
        "instrument_id": b["instrument"]["instrument_id"],
        "asset_class": b["instrument"]["asset_class"],
        "currency": "USD",
        "bid": bid,
        "ask": ask,
        "bid_size": "10",
        "ask_size": "10",
        "size_units": "SHARES",
        "source_timestamp": n.now[0],
        "received_timestamp": n.now[0],
        "sequence": str(n.now[0]),
        "session": "REGULAR",
        "calendar": {
            "id": "synthetic-NYSE-2026",
            "date": day.isoformat(),
            "open": int(datetime.combine(day, datetime.min.time(), UTC).timestamp())
            + 13 * 3600
            + 30 * 60,
            "close": int(datetime.combine(day, datetime.min.time(), UTC).timestamp())
            + 20 * 3600,
            "is_open": True,
        },
        "market_status": "TRADING",
        "connection_status": "CONNECTED",
        "clock_uncertainty_seconds": "0",
    }


def entry(n, decision="buy"):
    b = candidate(n)
    return n.engine.step(decision, bundles=[b], quotes=[quote(n, b)])


def monitor(n, b, decision, bid, current):
    n.now[0] += 1
    q = quote(n, b, bid, str(number(bid) + number("0.1")))
    obs = {
        "symbol": b["instrument"]["symbol"],
        "observed_at": n.now[0],
        "instrument": b["instrument"],
        "current": {"evidence_quality": "HIGH", **current},
    }
    return n.engine.step(decision, bundles=[], quotes=[q], observation=obs)


def test_end_to_end_automatic_entry_partial_full_and_report(tmp_path):
    n = setup(tmp_path)
    b = candidate(n)
    r = entry(n)
    assert r["filled"] and r["execution"] == "SIMULATED"
    s = n.ledger.snapshot()
    assert (
        number(s["cash"]) == number("899.9600")
        and number(next(iter(s["positions"].values()))["remaining"]) == 1
    )
    r = monitor(n, b, "partial", "110", {"fundamentals_score": 60})
    assert r["filled"], r
    s = n.ledger.snapshot()
    assert number(next(iter(s["positions"].values()))["remaining"]) == number("0.6")
    r = monitor(n, b, "full", "120", {"classification": "THESIS_BROKEN"})
    assert r["filled"], r
    s = n.ledger.snapshot()
    assert (
        number(s["cash"]) == number("1015.9136")
        and number(s["gross"]) == 16
        and number(s["costs"]) == number("0.0864")
    )
    assert number(s["net"]) == number("15.9136")
    n.engine.reconcile()
    report = n.ledger.daily_report("2026-10-26")
    assert number(report["closing_cash"]) == number("1015.9136")
    assert n.ledger.daily_report("2026-10-26") == report
    with n.ledger.connect(readonly=True) as db:
        commands = [strict(r[0]) for r in db.execute("SELECT body FROM events")]
    assert len(commands) == 3 and all(
        c["manual"] is False and c["schema"] == "QD_AUTO_COMMAND_V1" for c in commands
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("ask_size", None),
        ("bid", "101"),
        ("ask", "0"),
        ("market_status", "HALTED"),
        ("connection_status", "DISCONNECTED"),
        ("delay_status", "DELAYED"),
        ("size_units", "LOTS"),
        ("session", "AFTER_HOURS"),
        ("clock_uncertainty_seconds", "9"),
        ("instrument_id", "foreign"),
        ("source_timestamp", STAMP - 99),
    ],
)
def test_no_fill_inadequate_l1(tmp_path, field, value):
    n = setup(tmp_path)
    b = candidate(n)
    q = quote(n, b)
    q[field] = value
    r = n.engine.step("bad", bundles=[b], quotes=[q])
    assert not r["filled"]
    assert n.ledger.snapshot()["revision"] == 0


def test_duplicate_concurrent_decisions_and_restart(tmp_path):
    n = setup(tmp_path)
    b = candidate(n)
    q = quote(n, b)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(
            pool.map(lambda _: n.engine.step("same", bundles=[b], quotes=[q]), range(2))
        )
    # Concurrent acknowledgement may conservatively refuse one caller;never duplicate.
    assert n.ledger.snapshot()["revision"] == 1
    restarted = n.new()
    assert not restarted.step("same", bundles=[b], quotes=[q])["filled"]
    assert restarted.stop() == "STOPPED"
    g = copy.deepcopy(n.grant)
    g["session_id"] = "fresh-session"
    restarted.start(g)
    assert restarted.step("same", bundles=[b], quotes=[q])["filled"]
    assert n.ledger.snapshot()["revision"] == 1


def test_two_different_entry_attempts_cannot_scale_in(tmp_path):
    n = setup(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda i: entry(n, str(i)), range(2)))
    assert n.ledger.snapshot()["revision"] == 1
    assert (
        number(next(iter(n.ledger.snapshot()["positions"].values()))["quantity"]) == 1
    )


def test_pause_allows_protective_exit_stop_preserves_position(tmp_path):
    n = setup(tmp_path)
    assert n.engine.pause() == "PAUSED"
    assert not entry(n)["filled"]
    assert n.engine.stop() == "STOPPED"
    n.grant = {**n.grant, "session_id": "second-explicit-session"}
    n.engine.start(n.grant)
    assert entry(n)["filled"]
    b = candidate(n)
    n.engine.pause()
    assert monitor(n, b, "trim", "110", {"fundamentals_score": 60})["filled"]
    before = n.ledger.snapshot()
    assert n.engine.stop() == "STOPPED"
    after = n.ledger.snapshot()
    assert before == after
    assert not monitor(n, b, "sell", "120", {"classification": "THESIS_BROKEN"})[
        "filled"
    ]


@pytest.mark.parametrize(
    "phase", ["before_event", "before_commit", "after_commit", "before_ack"]
)
def test_interrupted_financial_effect_never_replays_or_cleanly_stops_unknown(
    tmp_path, phase
):
    n = setup(tmp_path)
    b = candidate(n)
    q = quote(n, b)

    def fault(p):
        if p == phase:
            raise OSError("INJECTED_BOUNDARY")

    r = n.engine.step("interrupt", bundles=[b], quotes=[q], fault=fault)
    assert not r["filled"] and n.engine.status() == "STOP_INCOMPLETE"
    if phase in ("after_commit", "before_ack"):
        assert (
            n.ledger.snapshot()["revision"] == 1
            and n.engine.stop() == "STOP_INCOMPLETE"
        )
        assert not n.new().step("interrupt", bundles=[b], quotes=[q])["filled"]
    else:
        assert n.ledger.snapshot()["revision"] == 0


def test_cash_guard_and_nonfractional_support(tmp_path):
    n = setup(tmp_path)
    b = candidate(n)
    b["instrument"]["fractional"] = False
    q = quote(n, b)
    q["ask_size"] = "1"
    assert not n.engine.step("small", bundles=[b], quotes=[q])["filled"]
    assert n.ledger.snapshot()["revision"] == 0


def test_session_expiry_and_clock_rollback_refuse(tmp_path):
    n = setup(tmp_path)
    n.now[0] = STAMP + 3601
    assert not entry(n)["filled"]
    n.now[0] = STAMP - 1
    assert not entry(n)["filled"]
    assert n.ledger.snapshot()["revision"] == 0


def test_no_price_only_exit_or_repeated_partial_target(tmp_path):
    n = setup(tmp_path)
    assert entry(n)["filled"]
    b = candidate(n)
    assert not monitor(n, b, "drop", "50", {"fundamentals_score": 80})["filled"]
    assert monitor(n, b, "trim", "110", {"fundamentals_score": 60})["filled"]
    assert not monitor(n, b, "trim-again", "110", {"fundamentals_score": 60})["filled"]


def test_strict_manual_contract_does_not_admit_autonomous_command(tmp_path):
    n = setup(tmp_path)
    entry(n)
    with n.ledger.connect(readonly=True) as db:
        command = strict(db.execute("SELECT body FROM events").fetchone()[0])
    old = manifest("strict", "QUALITY_DIPS")
    with pytest.raises(ValueError):
        apply_event(
            old,
            {
                "positions": {},
                "cash": "1000",
                "gross": "0",
                "costs": "0",
                "net": "0",
                "net_r": "0",
                "revision": 0,
                "last_clock": STAMP,
            },
            command,
        )


def test_ranked_etf_preferred_over_other_stock(tmp_path):
    n = setup(tmp_path)
    stock = candidate(n)
    etf = candidate(n, "SPY", "ETF")
    board = [etf["board"][0], stock["board"][0]]
    stock["board"] = copy.deepcopy(board)
    etf["board"] = copy.deepcopy(board)
    result = n.engine.step(
        "ranked", bundles=[stock, etf], quotes=[quote(n, stock), quote(n, etf)]
    )
    assert result["filled"], result
    assert next(iter(n.ledger.snapshot()["positions"].values()))["symbol"] == "SPY"


def test_actual_cash_reserves_costs_before_entry(tmp_path):
    from app.services.paper_financial_replay import initial_state

    n = setup(tmp_path)
    assert entry(n)["filled"]
    with n.ledger.connect(readonly=True) as db:
        command = strict(db.execute("SELECT body FROM events").fetchone()[0])
    state = initial_state(n.m)
    state["cash"] = "100.03"
    with pytest.raises(ValueError, match="Insufficient"):
        apply_event(n.m, state, command)
    assert state["cash"] == "100.03" and state["positions"] == {}


def test_stop_requires_new_session_authorization(tmp_path):
    n = setup(tmp_path)
    assert n.engine.stop() == "STOPPED"
    with pytest.raises(ValueError, match="GRANT_REUSE"):
        n.engine.start(n.grant)


@pytest.mark.parametrize("phase,code", [("after_commit", 61), ("after_ack", 62)])
def test_abrupt_process_exit_and_recovery_do_not_duplicate(tmp_path, phase, code):
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    program = "from pathlib import Path;import os,sys;from test_quality_dips_autonomous_paper import setup,candidate,quote;n=setup(Path(sys.argv[1]));b=candidate(n);n.engine.step('crash',bundles=[b],quotes=[quote(n,b)],fault=lambda p:os._exit(int(sys.argv[3])) if p==sys.argv[2] else None)"
    env = {
        **os.environ,
        "PYTHONPATH": str(root / "backend") + ";" + str(root / "tests"),
    }
    result = subprocess.run(
        [sys.executable, "-B", "-c", program, str(tmp_path), phase, str(code)],
        env=env,
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )
    assert result.returncode == code, result.stderr
    n = setup(tmp_path, reopen=True)
    b = candidate(n)
    q = quote(n, b)
    assert not n.engine.step("crash", bundles=[b], quotes=[q])["filled"]
    assert n.ledger.snapshot()["revision"] == 1
    if phase == "after_commit":
        assert n.engine.stop() == "STOP_INCOMPLETE"
    else:
        assert n.engine.stop() == "STOPPED"
        n.grant = {**n.grant, "session_id": "after-reboot-explicit"}
        n.engine.start(n.grant)
        assert n.engine.step("crash", bundles=[b], quotes=[q])["filled"]
        assert n.ledger.snapshot()["revision"] == 1


def test_shared_quote_liquidity_is_not_invented_across_exits(tmp_path):
    n = setup(tmp_path)
    entry(n)
    b = candidate(n)
    n.now[0] += 1
    q = quote(n, b, "110", "110.1")
    q["bid_size"] = "1"
    obs = {
        "symbol": "MSFT",
        "observed_at": n.now[0],
        "instrument": b["instrument"],
        "current": {"evidence_quality": "HIGH", "fundamentals_score": 60},
    }
    assert n.engine.step("partial", bundles=[], quotes=[q], observation=obs)["filled"]
    obs["current"] = {"classification": "THESIS_BROKEN", "evidence_quality": "HIGH"}
    assert n.engine.step("terminal-part", bundles=[], quotes=[q], observation=obs)[
        "filled"
    ]
    assert number(
        next(iter(n.ledger.snapshot()["positions"].values()))["remaining"]
    ) == number("0.5")
    assert not n.engine.step(
        "no-more-liquidity", bundles=[], quotes=[q], observation=obs
    )["filled"]
    n.engine.reconcile()


def test_conflicting_decision_and_quote_snapshot_refuse(tmp_path):
    n = setup(tmp_path)
    b = candidate(n)
    q = quote(n, b)
    assert not n.engine.step("ambiguous", bundles=[b], quotes=[q, q])["filled"]
    assert entry(n, "once")["filled"]
    changed = quote(n, b)
    changed["ask"] = "100.1"
    assert not n.engine.step("once", bundles=[b], quotes=[changed])["filled"]
    assert n.ledger.snapshot()["revision"] == 1


def test_revoked_session_and_market_holiday_refuse(tmp_path):
    n = setup(tmp_path)
    b = candidate(n)
    q = quote(n, b)
    q["calendar"]["is_open"] = False
    assert not n.engine.step("holiday", bundles=[b], quotes=[q])["filled"]
    n.revoked[0] = True
    assert not entry(n)["filled"]
    assert n.ledger.snapshot()["revision"] == 0


def test_financial_corruption_cannot_be_clean_shutdown(tmp_path):
    n = setup(tmp_path)
    entry(n)
    with n.ledger.connect() as db:
        db.execute("UPDATE events SET receipt='{}'")
    assert n.engine.stop() == "STOP_INCOMPLETE"
    with pytest.raises((ValueError, KeyError)):
        n.engine.reconcile()


def test_stop_race_closes_dispatch_before_waiting_for_writer(tmp_path):
    import time
    from threading import Event

    n = setup(tmp_path)
    b = candidate(n)
    q = quote(n, b)
    entered = Event()
    release = Event()

    def fault(phase):
        if phase == "before_event":
            entered.set()
            assert release.wait(3)

    with ThreadPoolExecutor(max_workers=3) as pool:
        accepted = pool.submit(
            n.engine.step, "accepted", bundles=[b], quotes=[q], fault=fault
        )
        assert entered.wait(2)
        stopped = pool.submit(n.engine.stop)
        until = time.monotonic() + 2
        while not n.engine.dispatch_closed and time.monotonic() < until:
            time.sleep(0.001)
        assert n.engine.dispatch_closed
        refused = pool.submit(n.engine.step, "after-stop", bundles=[b], quotes=[q])
        release.set()
        accepted.result()
        stopped.result()
        assert not refused.result()["filled"]
    assert n.ledger.snapshot()["revision"] == 1
    assert n.engine.stop() == "STOPPED"
    assert (
        number(next(iter(n.ledger.snapshot()["positions"].values()))["remaining"]) == 1
    )


def test_malformed_price_is_no_fill_not_invented_value(tmp_path):
    n = setup(tmp_path)
    b = candidate(n)
    q = quote(n, b)
    q["ask"] = "invalid-decimal"
    assert not n.engine.step("bad-price", bundles=[b], quotes=[q])["filled"]
    assert n.ledger.snapshot()["revision"] == 0


def test_fractional_participation_rounds_down_and_reconciles(tmp_path):
    n = setup(tmp_path)
    b = candidate(n)
    q = quote(n, b)
    q["ask_size"] = "1.333"
    result = n.engine.step("fractional", bundles=[b], quotes=[q])
    assert result["filled"]
    assert number(
        next(iter(n.ledger.snapshot()["positions"].values()))["quantity"]
    ) == number("0.666")
    n.engine.reconcile()
