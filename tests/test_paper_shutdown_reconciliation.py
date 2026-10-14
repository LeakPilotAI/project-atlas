import asyncio
import json
from pathlib import Path

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


def test_shutdown_persists_final_mark_and_interrupts_once(tmp_path, monkeypatch):
    j, path = _configure(tmp_path, monkeypatch)
    tid = asyncio.run(j.open_trade(symbol="BTC", side="LONG", entry=100, stop=99, tp1=102, tp2=103))
    j.update_excursion(tid, 101.25, force=True)

    assert j.persist_open_marks() == 1
    assert j.interrupt_open_for_shutdown() == [tid]
    assert j.interrupt_open_for_shutdown() == []

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    marks = [row for row in rows if row.get("event") == "mark" and row.get("trade_id") == tid]
    closes = [row for row in rows if row.get("event") == "close" and row.get("trade_id") == tid]
    assert marks[-1]["mark"] == 101.25
    assert marks[-1]["unrealized_r"] == 1.25
    assert len(closes) == 1
    assert closes[0]["result"] == "INTERRUPTED"
    assert closes[0]["actual_exit_price"] == 101.25
    assert closes[0]["counts_for_live"] is False

    restarted = journal_mod.PaperJournal()
    assert restarted.list_open() == []
    recovered_rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len([row for row in recovered_rows if row.get("event") == "close" and row.get("trade_id") == tid]) == 1


def test_lifespan_stops_services_before_paper_interruption():
    source = (Path(__file__).resolve().parents[1] / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    cancel_boot = source.index("boot_task.cancel()")
    stop_services = source.index("for name, stopper in [")
    await_stopper = source.index("await stopper()", stop_services)
    paper_guard = source.index("if shutdown_services_stopped:", await_stopper)
    pending_reconciliation = source.index("cancel_all_pending(reason=\"ATLAS_SHUTDOWN\")", paper_guard)
    persist_marks = source.index("paper_journal.persist_open_marks()", pending_reconciliation)
    interrupt = source.index("paper_journal.interrupt_open_for_shutdown()", persist_marks)

    assert cancel_boot < stop_services < await_stopper < paper_guard
    assert paper_guard < pending_reconciliation < persist_marks < interrupt
    assert "open journal rows were retained for operator recovery" in source
