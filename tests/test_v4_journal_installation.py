from __future__ import annotations

from typing import Any, Dict

import pytest

from app.services import v4_journal_observer as observer


class FakeJournal:
    def __init__(self) -> None:
        self._open: Dict[str, Dict[str, Any]] = {}
        self.open_calls = 0
        self.mark_calls = 0

    async def open_trade(self, **kwargs: Any) -> str:
        self.open_calls += 1
        tid = kwargs.get("trade_id") or f"trade-{self.open_calls}"
        self._open[tid] = {
            "trade_id": tid,
            "trade_type": kwargs.get("trade_type", "PAPER"),
            "symbol": kwargs["symbol"],
            "side": kwargs["side"],
            "actual_entry_price": float(kwargs["entry"]),
            "initial_stop": float(kwargs["stop"]),
            "stop_price": float(kwargs["stop"]),
            "setup_rr": float(kwargs.get("setup_rr", 1.8)),
            "risk_dollars": float(kwargs.get("risk_usd", 1.0)),
        }
        return str(tid)

    def update_excursion(self, trade_id: str, mark: float, *, force: bool = False) -> None:
        self.mark_calls += 1
        if trade_id not in self._open:
            raise KeyError(trade_id)
        self._open[trade_id]["mark"] = float(mark)


@pytest.mark.asyncio
async def test_install_is_idempotent_and_forwards_paper(monkeypatch):
    journal = FakeJournal()
    opens = []
    marks = []
    monkeypatch.setattr(observer, "on_paper_open", lambda **kw: opens.append(kw))
    monkeypatch.setattr(observer, "on_paper_mark", lambda **kw: marks.append(kw))

    assert observer.install_paper_journal_observer(journal) is True
    assert observer.install_paper_journal_observer(journal) is False

    tid = await journal.open_trade(symbol="btc", side="LONG", entry=100.0, stop=99.0, risk_usd=2.0)
    journal.update_excursion(tid, 101.0)

    assert journal.open_calls == 1
    assert journal.mark_calls == 1
    assert opens == [{
        "trade_id": tid,
        "symbol": "btc",
        "side": "LONG",
        "entry": 100.0,
        "stop": 99.0,
        "setup_rr": 1.8,
        "risk_usd": 2.0,
    }]
    assert marks == [{"symbol": "btc", "mark": 101.0}]


@pytest.mark.asyncio
async def test_installed_bridge_ignores_non_paper(monkeypatch):
    journal = FakeJournal()
    opens = []
    marks = []
    monkeypatch.setattr(observer, "on_paper_open", lambda **kw: opens.append(kw))
    monkeypatch.setattr(observer, "on_paper_mark", lambda **kw: marks.append(kw))
    observer.install_paper_journal_observer(journal)

    tid = await journal.open_trade(symbol="ETH", side="SHORT", entry=100.0, stop=101.0, trade_type="TEST")
    journal.update_excursion(tid, 99.0)

    assert opens == []
    assert marks == []
    assert journal.open_calls == 1
    assert journal.mark_calls == 1


@pytest.mark.asyncio
async def test_shadow_failure_never_changes_legacy_result(monkeypatch):
    journal = FakeJournal()

    def boom(**kwargs: Any) -> None:
        raise RuntimeError("shadow unavailable")

    monkeypatch.setattr(observer, "on_paper_open", boom)
    monkeypatch.setattr(observer, "on_paper_mark", boom)
    observer.install_paper_journal_observer(journal)

    tid = await journal.open_trade(symbol="SOL", side="LONG", entry=50.0, stop=49.0)
    journal.update_excursion(tid, 50.5, force=True)

    assert tid in journal._open
    assert journal._open[tid]["mark"] == 50.5
    assert journal.open_calls == 1
    assert journal.mark_calls == 1
