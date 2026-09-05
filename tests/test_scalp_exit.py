"""Paper scalp exits: bank 1.0R, BE after 0.5R MFE. Entry gates unchanged."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.core.config import get_settings
from app.services.funnel_research import EXT_LOCK, RR_LOCK, RSI_LONG_LOCK, RSI_SHORT_LOCK
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


def _open_scalp(tid, symbol="AAA", side="LONG", entry=100.0, stop=99.0, mfe=0.0):
    risk = abs(entry - stop)
    return {
        "event": "open",
        "trade_type": "PAPER",
        "trade_id": tid,
        "symbol": symbol,
        "side": side,
        "actual_entry_price": entry,
        "stop_price": stop,
        "initial_stop": stop,
        "working_stop": stop,
        "tp1_price": entry + risk if side == "LONG" else entry - risk,
        "risk_price": risk,
        "mark": entry,
        "mfe_r": mfe,
        "mae_r": 0.0,
        "exit_mode": "SCALP",
        "scalp_tp_r": 1.0,
        "be_after_r": 0.5,
        "be_armed": False,
        "entry_timestamp": datetime(2026, 8, 1, 12, tzinfo=timezone.utc).isoformat(),
        "status": "open",
    }


def test_entry_gates_still_locked() -> None:
    s = get_settings()
    assert s.perp_micro_rsi_long == 28.0
    assert s.perp_micro_rsi_short == 72.0
    assert s.perp_micro_min_extension_pct == 1.4
    assert s.perp_micro_min_rr == 1.8
    assert RSI_LONG_LOCK == 28.0
    assert RSI_SHORT_LOCK == 72.0
    assert EXT_LOCK == 1.4
    assert RR_LOCK == 1.8
    assert s.perp_micro_scalp_tp_r == 1.0
    assert s.perp_micro_be_after_r == 0.5


def test_scalp_tp_at_1r_not_18(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_scalp("t1"))
    j.reload()
    c = PerpMicroCoach()
    c._rehydrate_open(reason="startup")
    _run(c._manage_open({"AAA": 101.0}))
    assert "t1" not in c._open
    stats = _run(j.stats())
    assert stats["wins"] == 1
    assert stats["losses"] == 0
    assert stats["scalp_cohort"]["n"] == 1
    assert stats["scalp_cohort"]["wins"] == 1


def test_1_8_target_no_longer_required_to_win(tmp_path, monkeypatch):
    """Old bot waited for 102 (1.8R). Scalp banks at 101 (1.0R)."""
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_scalp("t1"))
    j.reload()
    c = PerpMicroCoach()
    c._rehydrate_open(reason="startup")
    _run(c._manage_open({"AAA": 101.5}))  # between 1.0R and 1.8R
    assert "t1" not in c._open
    closed = [r for r in j._open.values()]  # empty
    assert _run(j.stats())["wins"] == 1


def test_be_after_half_r_prevents_full_loss(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_scalp("t1", mfe=0.6))
    j.reload()
    c = PerpMicroCoach()
    c._rehydrate_open(reason="startup")
    assert c._open["t1"]["mfe_r"] >= 0.5
    _run(c._manage_open({"AAA": 100.6}))  # arm BE, do not TP yet
    assert "t1" in c._open
    assert c._open["t1"]["be_armed"] is True
    assert c._open["t1"]["working_stop"] == 100.0
    _run(c._manage_open({"AAA": 99.5}))  # would have been -1R; now BE at entry
    assert "t1" not in c._open
    stats = _run(j.stats())
    assert stats["losses"] == 0
    assert stats["scratches"] == 1
    assert stats["sum_r"] == 0.0


def test_never_reached_half_r_still_full_stop(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_scalp("t1", mfe=0.1))
    j.reload()
    c = PerpMicroCoach()
    c._rehydrate_open(reason="startup")
    _run(c._manage_open({"AAA": 99.0}))
    assert "t1" not in c._open
    stats = _run(j.stats())
    assert stats["losses"] == 1
    assert stats["scratches"] == 0


def test_short_scalp_tp_and_be(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    j._append(p, _open_scalp("s1", symbol="BBB", side="SHORT", entry=50.0, stop=51.0, mfe=0.6))
    j.reload()
    c = PerpMicroCoach()
    c._rehydrate_open(reason="startup")
    _run(c._manage_open({"BBB": 49.6}))
    assert c._open["s1"]["be_armed"] is True
    _run(c._manage_open({"BBB": 49.0}))  # 1.0R TP
    stats = _run(j.stats())
    assert stats["wins"] == 1


def test_legacy_setup_18_keeps_old_tp(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)
    row = _open_scalp("old")
    row["exit_mode"] = "SETUP_18"
    row["tp1_price"] = 101.8
    row["be_after_r"] = 99.0
    j._append(p, row)
    j.reload()
    c = PerpMicroCoach()
    c._rehydrate_open(reason="startup")
    _run(c._manage_open({"AAA": 101.0}))  # 1.0R would scalp-close; legacy stays open
    assert "old" in c._open
    _run(c._manage_open({"AAA": 101.8}))
    assert "old" not in c._open
