"""Session stats reset without deleting journal rows."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.services.paper_journal import PaperJournal
from app.investment.buy_prep import classify_buy_prep


def _run(coro):
    return asyncio.run(coro)


def _bind(tmp_path, monkeypatch):
    p = tmp_path / "paper_journal.jsonl"
    monkeypatch.setattr("app.services.paper_journal.JOURNAL_PATH", p)
    monkeypatch.setattr("app.services.paper_journal.CANDIDATE_PATH", tmp_path / "c.jsonl")
    return PaperJournal(), p


def test_session_hides_prior_closes_but_keeps_rows(tmp_path, monkeypatch):
    j, p = _bind(tmp_path, monkeypatch)

    async def _go():
        tid = await j.open_trade(
            symbol="OLD",
            side="LONG",
            entry=100.0,
            stop=99.0,
            tp1=101.0,
            tp2=102.0,
            trade_type="PAPER",
        )
        await j.close_trade(tid, exit_price=101.0, result="WIN")
        before = await j.stats()
        assert before["closed"] == 1
        assert before["session"]["session_id"] == "all-time"
        boot = j.bootstrap_session(session_id="scalp-v1", label="test")
        assert boot["created"] is True
        assert boot["prior_closed_archived"] == 1
        after = await j.stats()
        assert after["closed"] == 0
        assert after["winrate"] == 0.0
        assert after["all_time"]["closed"] == 1
        assert after["session"]["session_id"] == "scalp-v1"
        again = j.bootstrap_session(session_id="scalp-v1")
        assert again["created"] is False
        text = p.read_text(encoding="utf-8")
        assert '"event": "close"' in text
        assert "OLD" in text
        tid2 = await j.open_trade(
            symbol="NEW",
            side="SHORT",
            entry=10.0,
            stop=10.1,
            tp1=9.9,
            tp2=9.8,
            trade_type="PAPER",
        )
        await j.close_trade(tid2, exit_price=9.9, result="WIN")
        now = await j.stats()
        assert now["closed"] == 1
        assert now["wins"] == 1
        assert now["all_time"]["closed"] == 2

    _run(_go())


def test_bootstrap_idempotent(tmp_path, monkeypatch):
    j, _p = _bind(tmp_path, monkeypatch)
    a = j.bootstrap_session(session_id="scalp-v1")
    b = j.bootstrap_session(session_id="scalp-v1")
    assert a["created"] is True
    assert b["created"] is False
    assert a["session_id"] == b["session_id"] == "scalp-v1"


def test_buy_prep_stand_down_on_broken_thesis():
    r = classify_buy_prep(thesis="BROKEN", drawdown=0.2, ret_1d=-0.08)
    assert r["action"] == "STAND_DOWN"
    assert r["notify"] is False


def test_buy_prep_prepare_on_momentary_dip():
    r = classify_buy_prep(thesis="INTACT", drawdown=0.10, ret_1d=-0.04, investment_class="NO_ACTION")
    assert r["action"] == "PREPARE"
    assert r["notify"] is True


def test_buy_prep_accumulate_state():
    r = classify_buy_prep(thesis="STRONG", investment_class="ACCUMULATION", drawdown=0.12)
    assert r["action"] == "ACCUMULATE"


def test_buy_prep_quiet_when_flat():
    r = classify_buy_prep(thesis="INTACT", drawdown=0.01, ret_1d=-0.002)
    assert r["action"] == "QUIET"
