"""Paper open-position recovery across restart. Does not change TP/SL math."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.services.paper_journal import PaperJournal
from app.services.perp_micro_coach import PerpMicroCoach


def _run(coro):
    return asyncio.run(coro)


def _bind(tmp_path, monkeypatch):
    p = tmp_path / "paper_journal.jsonl"
    monkeypatch.setattr("app.services.paper_journal.JOURNAL_PATH", p)
    import app.services.paper_journal as pj

    j = PaperJournal()
    monkeypatch.setattr(pj, "paper_journal", j)
    return j, p


def _open_row(tid, symbol="AAA", side="LONG", entry=100.0, stop=99.0, tp1=102.0, mfe=0.0):
    return {
        "event": "open",
        "trade_type": "PAPER",
        "trade_id": tid,
        "symbol": symbol,
        "side": side,
        "actual_entry_price": entry,
        "stop_price": stop,
        "tp1_price": tp1,
        "risk_price": abs(entry - stop),
        "mark": entry,
        "mfe_r": mfe,
        "mae_r": 0.0,
        "entry_timestamp": datetime(2026, 8, 1, 12, tzinfo=timezone.utc).isoformat(),
        "status": "open",
    }


def test_restart_one_open_then_tp_close(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_row("t1", mfe=0.4))
    j.reload()
    c1 = PerpMicroCoach()
    assert c1._rehydrate_open(reason="startup") == 1
    assert c1._open["t1"]["entry"] == 100.0
    assert c1._open["t1"]["opened_at"]
    # simulated process death: new coach, same journal
    c2 = PerpMicroCoach()
    c2._rehydrate_open(reason="startup")
    assert "t1" in c2._open
    assert c2._open["t1"]["mfe_r"] == 0.4
    _run(c2._manage_open({"AAA": 102.0}))
    assert "t1" not in c2._open
    j.reload()
    assert j.list_open() == []
    stats = _run(j.stats())
    assert stats["closed"] == 1
    assert stats["wins"] == 1


def test_restart_multiple_long_short_markets(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_row("l1", symbol="AAA", side="LONG", entry=100, stop=99, tp1=102))
    j._append(p, _open_row("s1", symbol="BBB", side="SHORT", entry=50, stop=51, tp1=48))
    j.reload()
    c = PerpMicroCoach()
    c._rehydrate_open(reason="startup")
    assert set(c._open) == {"l1", "s1"}
    _run(c._manage_open({"AAA": 102.0, "BBB": 48.0}))
    assert c._open == {}


def test_missing_market_data_keeps_open(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_row("t1"))
    j.reload()
    c = PerpMicroCoach()
    c._rehydrate_open(reason="startup")
    _run(c._manage_open({}))
    assert "t1" in c._open
    assert c._open["t1"]["lifecycle"] == "MARKET_DATA_UNAVAILABLE"
    assert c._open["t1"]["stale_quote"] is True
    j.reload()
    assert len(j.list_open()) == 1


def test_duplicate_rehydrate_idempotent(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_row("t1"))
    j.reload()
    c = PerpMicroCoach()
    assert c._rehydrate_open() == 1
    assert c._rehydrate_open() == 0
    assert list(c._open) == ["t1"]


def test_truncated_line_does_not_drop_other_opens(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_row("keep"))
    with p.open("a", encoding="utf-8") as f:
        f.write('{"event":"open","trade_id":"partial"')
    j.reload()
    assert any(r["trade_id"] == "keep" for r in j.list_open())
    assert j.recovery_report()["malformed"] >= 1
    c = PerpMicroCoach()
    c._rehydrate_open(reason="startup")
    assert "keep" in c._open


def test_close_idempotent_no_duplicate_pnl(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_row("t1"))
    j.reload()
    first = _run(j.close_trade("t1", exit_price=102.0, result="TP1", pnl_r=2.0))
    second = _run(j.close_trade("t1", exit_price=102.0, result="TP1", pnl_r=2.0))
    assert first["trade_id"] == "t1"
    assert second.get("event") == "close"
    stats = _run(j.stats())
    assert stats["closed"] == 1


def test_restart_while_exit_triggered_same_logic(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_row("t1", entry=100, stop=99, tp1=102, mfe=1.1))
    j.reload()
    c = PerpMicroCoach()
    c._rehydrate_open()
    _run(c._manage_open({"AAA": 99.0}))  # stop
    assert "t1" not in c._open
    stats = _run(j.stats())
    assert stats["losses"] == 1


def test_repeated_restart_cycles(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_row("t1"))
    j.reload()
    for _ in range(5):
        c = PerpMicroCoach()
        c._rehydrate_open(reason="startup")
        assert list(c._open) == ["t1"]
        assert c._open["t1"]["entry"] == 100.0
        _run(c._manage_open({}))
    assert len(j.list_open()) == 1


def test_restart_immediately_after_entry(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_row("t1"))
    j.reload()
    c = PerpMicroCoach()
    c._rehydrate_open(reason="startup")
    assert c._open["t1"]["opened_at"] == "2026-08-01T12:00:00+00:00"
    assert c._open["t1"]["entry"] == 100.0
    assert c._open["t1"]["stop"] == 99.0
    assert c._open["t1"]["tp1"] == 102.0
    _run(c._manage_open({"AAA": 100.0}))
    assert "t1" in c._open
    assert c._open["t1"]["lifecycle"] == "MANAGED"


def test_restart_while_profitable_not_at_tp(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_row("t1", mfe=0.4))
    j.reload()
    c = PerpMicroCoach()
    c._rehydrate_open(reason="startup")
    _run(c._manage_open({"AAA": 100.6}))
    assert "t1" in c._open
    assert c._open["t1"]["lifecycle"] == "MANAGED"
    assert float(c._open["t1"]["mfe_r"]) >= 0.4


def test_restart_while_losing_not_at_stop(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_row("t1"))
    j.reload()
    c = PerpMicroCoach()
    c._rehydrate_open(reason="startup")
    _run(c._manage_open({"AAA": 99.4}))
    assert "t1" in c._open
    assert j.list_open()


def test_restart_same_exit_as_never_restarted(tmp_path, monkeypatch):
    """Recovered trade must use the same TP/SL comparison as a no-restart twin."""
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_row("live", entry=100, stop=99, tp1=102))
    j._append(p, _open_row("rec", symbol="BBB", entry=100, stop=99, tp1=102))
    j.reload()
    live = PerpMicroCoach()
    live._rehydrate_open(reason="startup")
    _run(live._manage_open({"AAA": 102.0, "BBB": 100.0}))
    rec = PerpMicroCoach()
    rec._rehydrate_open(reason="startup")
    assert "rec" in rec._open
    _run(rec._manage_open({"BBB": 102.0}))
    assert "live" not in live._open
    assert "rec" not in rec._open
    stats = _run(j.stats())
    assert stats["closed"] == 2
    assert stats["wins"] == 2


def test_graceful_shutdown_persists_mfe_keeps_open(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_row("t1"))
    j.reload()
    c = PerpMicroCoach()
    c._rehydrate_open(reason="startup")
    _run(c._manage_open({"AAA": 100.6}))
    _run(c.stop())
    assert len(j.list_open()) == 1
    c2 = PerpMicroCoach()
    c2._rehydrate_open(reason="startup")
    assert "t1" in c2._open
    assert float(c2._open["t1"]["mfe_r"]) > 0
    assert c2._open["t1"]["opened_at"] == "2026-08-01T12:00:00+00:00"


def test_crash_before_shutdown_persist_does_not_invent_exit(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_row("t1", mfe=0.2))
    j.reload()
    c1 = PerpMicroCoach()
    c1._rehydrate_open(reason="startup")
    c1._open["t1"]["mark"] = 100.3
    c1._open["t1"]["mfe_r"] = 0.3
    # process dies without stop()
    c2 = PerpMicroCoach()
    c2._rehydrate_open(reason="startup")
    assert "t1" in c2._open
    assert len(j.list_open()) == 1
    stats = _run(j.stats())
    assert stats["closed"] == 0


def test_corrupt_open_is_review_not_closed(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    bad = _open_row("bad1")
    bad["actual_entry_price"] = None
    bad["stop_price"] = None
    j._append(p, bad)
    j.reload()
    c = PerpMicroCoach()
    c._rehydrate_open(reason="startup")
    assert "bad1" in c._open
    assert c._open["bad1"]["lifecycle"] == "ERROR_REQUIRES_REVIEW"
    _run(c._manage_open({"AAA": 102.0}))
    assert "bad1" in c._open
    assert len(j.list_open()) == 1
    stats = _run(j.stats())
    assert stats["closed"] == 0


def test_reconcile_recovers_disk_only_orphan(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_row("orphan"))
    j.reload()
    j._open.pop("orphan", None)  # memory lost, disk still open
    assert j.list_open() == []
    rec = j.reconcile_from_disk()
    assert rec["added"] == 1
    assert any(r["trade_id"] == "orphan" for r in j.list_open())
    c = PerpMicroCoach()
    c._rehydrate_open(reason="cycle")
    assert "orphan" in c._open


def test_close_after_append_is_idempotent(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_row("t1"))
    j.reload()
    first = _run(j.close_trade("t1", exit_price=102.0, result="TP1", pnl_r=2.0))
    # crash window: memory still thinks open, disk already closed
    j._open["t1"] = _open_row("t1")
    second = _run(j.close_trade("t1", exit_price=99.0, result="STOP", pnl_r=-1.0))
    assert first["trade_id"] == "t1"
    assert second.get("result") == "TP1"
    stats = _run(j.stats())
    assert stats["closed"] == 1
    assert stats["wins"] == 1
