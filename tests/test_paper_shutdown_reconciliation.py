import asyncio
import json

from app.services import paper_journal as journal_mod


def _configure(tmp_path, monkeypatch):
    path = tmp_path / "paper.jsonl"
    monkeypatch.setattr(journal_mod, "JOURNAL_PATH", path)
    j = journal_mod.PaperJournal()
    return j, path


def test_shutdown_interrupt_preserves_history_but_removes_open(tmp_path, monkeypatch):
    j, path = _configure(tmp_path, monkeypatch)
    tid = asyncio.run(j.open_trade(symbol="BTC", side="LONG", entry=100, stop=99, tp1=102, tp2=103))
    assert len(j.list_open()) == 1
    interrupted = j.interrupt_open_for_shutdown()
    assert interrupted == [tid]
    assert j.list_open() == []
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    close = [x for x in rows if x.get("event") == "close"][-1]
    assert close["result"] == "INTERRUPTED"
    assert close["counts_for_live"] is False
    assert close["net_pnl_r"] == 0.0


def test_interrupted_trade_does_not_pollute_performance(tmp_path, monkeypatch):
    j, _ = _configure(tmp_path, monkeypatch)
    asyncio.run(j.open_trade(symbol="ETH", side="SHORT", entry=100, stop=101, tp1=98, tp2=97))
    j.interrupt_open_for_shutdown()
    stats = asyncio.run(j.stats())
    assert stats["closed"] == 0
    assert stats["sum_r"] == 0.0


def test_restart_does_not_recover_interrupted_trade(tmp_path, monkeypatch):
    j, _ = _configure(tmp_path, monkeypatch)
    asyncio.run(j.open_trade(symbol="SOL", side="LONG", entry=100, stop=99, tp1=102, tp2=103))
    j.interrupt_open_for_shutdown()
    restarted = journal_mod.PaperJournal()
    assert restarted.list_open() == []
