import asyncio
import json

from app.services import paper_journal as journal_mod


def _journal(tmp_path, monkeypatch):
    path = tmp_path / "paper.jsonl"
    monkeypatch.setattr(journal_mod, "JOURNAL_PATH", path)
    return journal_mod.PaperJournal(), path


def test_close_trade_is_idempotent(tmp_path, monkeypatch):
    j, path = _journal(tmp_path, monkeypatch)
    tid = asyncio.run(j.open_trade(symbol="BTC", side="LONG", entry=100, stop=99, tp1=102, tp2=103))
    first = asyncio.run(j.close_trade(tid, exit_price=102, result="WIN"))
    second = asyncio.run(j.close_trade(tid, exit_price=105, result="WIN"))
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    closes = [x for x in rows if x.get("event") == "close" and x.get("trade_id") == tid]
    assert len(closes) == 1
    assert first == second
    assert j.trade_terminal(tid) is True
