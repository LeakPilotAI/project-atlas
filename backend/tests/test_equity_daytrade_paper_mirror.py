from types import SimpleNamespace

import pytest

from app.services.equity_daytrade_paper_mirror import (
    EquityDayTradePaperMirror,
    SOURCE,
)
from app.services.paper_journal import paper_journal


def _plan(*, price=100.0, action="PREPARE", phase="OPEN"):
    return SimpleNamespace(
        symbol="TEST",
        action=action,
        phase=phase,
        confidence=70.0,
        price=price,
        l1=99.0,
        l2=98.0,
        stop=97.0,
        tp1=102.6,
        tp2=105.0,
    )


@pytest.mark.asyncio
async def test_new_manual_limit_arms_but_does_not_fill_same_scan(tmp_path, monkeypatch):
    mirror = EquityDayTradePaperMirror(pending_path=tmp_path / "pending.jsonl")
    monkeypatch.setattr(paper_journal, "list_open", lambda: [])

    async def should_not_open(**kwargs):
        raise AssertionError("newly displayed limit must require later price evidence")

    monkeypatch.setattr(paper_journal, "open_trade", should_not_open)
    result = await mirror.sync([_plan(price=98.5)], phase="OPEN", day="2026-09-28")

    assert result["armed"] == 1
    assert result["filled"] == 0
    assert result["pending"] == 1
    assert mirror.status()["live_capital_allowed"] is False
    assert mirror.status()["automatic_real_money_execution"] is False


@pytest.mark.asyncio
async def test_later_touch_opens_isolated_paper_trade(tmp_path, monkeypatch):
    mirror = EquityDayTradePaperMirror(pending_path=tmp_path / "pending.jsonl")
    open_rows = []

    monkeypatch.setattr(paper_journal, "list_open", lambda: list(open_rows))

    async def fake_open_trade(**kwargs):
        row = {
            "trade_id": "paper-1",
            "trade_type": "PAPER",
            "symbol": kwargs["symbol"],
            "side": kwargs["side"],
            "source": kwargs["source"],
            "features": kwargs["features"],
        }
        open_rows.append(row)
        return "paper-1"

    monkeypatch.setattr(paper_journal, "open_trade", fake_open_trade)
    monkeypatch.setattr(paper_journal, "update_excursion", lambda *args, **kwargs: None)

    first = await mirror.sync([_plan(price=100.0)], phase="OPEN", day="2026-09-28")
    second = await mirror.sync([_plan(price=98.9, action="TRIGGER")], phase="OPEN", day="2026-09-28")

    assert first["armed"] == 1
    assert second["filled"] == 1
    assert second["pending"] == 0
    assert open_rows[0]["source"] == SOURCE
    assert open_rows[0]["features"]["paper_order_id"] == "2026-09-28|TEST|L1"


@pytest.mark.asyncio
async def test_midday_cancels_unfilled_manual_limits(tmp_path, monkeypatch):
    mirror = EquityDayTradePaperMirror(pending_path=tmp_path / "pending.jsonl")
    monkeypatch.setattr(paper_journal, "list_open", lambda: [])

    first = await mirror.sync([_plan()], phase="OPEN", day="2026-09-28")
    second = await mirror.sync([_plan(action="SKIP", phase="MIDDAY")], phase="MIDDAY", day="2026-09-28")

    assert first["pending"] == 1
    assert second["cancelled"] == 1
    assert second["pending"] == 0
