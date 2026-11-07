import asyncio
import json
from pathlib import Path
import re
import subprocess

from fastapi.testclient import TestClient

import app.api.archive as archive_api
from app.main import app


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "backend" / "app" / "static" / "archive_paper_trades.html"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_paper_archive_builds_truthful_stats_and_excludes_nonperformance_rows(tmp_path, monkeypatch):
    journal = tmp_path / "paper_journal.jsonl"
    rows = [
        {
            "event": "open", "trade_id": "a", "trade_type": "PAPER", "symbol": "BTC",
            "side": "LONG", "strategy": "momentum", "entry_timestamp": "2026-09-01T10:00:00+00:00",
            "actual_entry_price": 100.0, "stop_price": 95.0, "tp1_price": 110.0,
        },
        {
            "event": "close", "trade_id": "a", "trade_type": "PAPER", "symbol": "BTC",
            "side": "LONG", "strategy": "momentum", "entry_timestamp": "2026-09-01T10:00:00+00:00",
            "exit_timestamp": "2026-09-01T11:00:00+00:00", "actual_entry_price": 100.0,
            "actual_exit_price": 105.0, "net_pnl_r": 1.0, "result": "TP", "notes": "winner",
        },
        {
            "event": "close", "trade_id": "b", "trade_type": "PAPER", "symbol": "ETH",
            "side": "SHORT", "strategy": "reversal", "entry_timestamp": "2026-09-02T10:00:00+00:00",
            "exit_timestamp": "2026-09-02T11:00:00+00:00", "actual_entry_price": 200.0,
            "actual_exit_price": 204.0, "net_pnl_r": -0.5, "result": "SL", "notes": "loser",
        },
        {
            "event": "close", "trade_id": "c", "trade_type": "PAPER", "symbol": "SOL",
            "side": "LONG", "strategy": "range", "entry_timestamp": "2026-09-03T10:00:00+00:00",
            "exit_timestamp": "2026-09-03T11:00:00+00:00", "actual_entry_price": 150.0,
            "actual_exit_price": 150.0, "net_pnl_r": 0.0, "result": "BE", "scratch": True,
        },
        {
            "event": "close", "trade_id": "rolled", "trade_type": "PAPER", "symbol": "BTC",
            "exit_timestamp": "2026-09-04T11:00:00+00:00", "net_pnl_r": 0.0,
            "result": "SESSION_ROLL", "session_roll": True,
        },
        {
            "event": "close", "trade_id": "interrupted", "trade_type": "PAPER", "symbol": "BTC",
            "exit_timestamp": "2026-09-05T11:00:00+00:00", "net_pnl_r": 0.0,
            "result": "INTERRUPTED",
        },
        {
            "event": "close", "trade_id": "test", "trade_type": "TEST", "symbol": "BTC",
            "exit_timestamp": "2026-09-06T11:00:00+00:00", "net_pnl_r": 99.0,
            "result": "TP",
        },
    ]
    _write_jsonl(journal, rows)
    monkeypatch.setattr(archive_api, "JOURNAL_PATH", journal)

    payload = archive_api._build_paper_trades_archive(
        date_range="all", symbol="", setup="", limit=100
    )
    summary = payload["summary"]
    assert payload["execution"] == "PAPER_ONLY"
    assert payload["live_capital_allowed"] is False
    assert payload["automatic_real_money_execution"] is False
    assert summary["total"] == 3
    assert summary["wins"] == 1
    assert summary["losses"] == 1
    assert summary["scratches"] == 1
    assert summary["sum_r"] == 0.5
    assert summary["avg_r"] == round(0.5 / 3, 4)
    assert summary["best_trade"]["trade_id"] == "a"
    assert summary["worst_trade"]["trade_id"] == "b"
    assert {row["trade_id"] for row in payload["trades"]} == {"a", "b", "c"}
    assert summary["max_drawdown_r"] <= 0
    assert any(row["direction"] == "LONG" for row in summary["by_direction"])
    assert any(row["setup"] == "MOMENTUM" for row in summary["by_setup"])


def test_paper_trade_detail_returns_only_persisted_journal_path(tmp_path, monkeypatch):
    journal = tmp_path / "paper_journal.jsonl"
    _write_jsonl(
        journal,
        [
            {
                "event": "open", "trade_id": "abc", "trade_type": "PAPER", "symbol": "BTC",
                "side": "LONG", "strategy": "momentum", "entry_timestamp": "2026-10-01T10:00:00+00:00",
                "actual_entry_price": 100.0, "stop_price": 95.0, "tp1_price": 110.0,
            },
            {
                "event": "mark", "trade_id": "abc", "trade_type": "PAPER",
                "timestamp": "2026-10-01T10:05:00+00:00", "mark": 102.0, "mfe_r": 0.4, "mae_r": 0.0,
            },
            {
                "event": "close", "trade_id": "abc", "trade_type": "PAPER", "symbol": "BTC",
                "side": "LONG", "strategy": "momentum", "entry_timestamp": "2026-10-01T10:00:00+00:00",
                "exit_timestamp": "2026-10-01T10:10:00+00:00", "actual_entry_price": 100.0,
                "actual_exit_price": 105.0, "net_pnl_r": 1.0, "result": "TP",
            },
        ],
    )
    monkeypatch.setattr(archive_api, "JOURNAL_PATH", journal)
    payload = asyncio.run(archive_api.paper_trade_detail("abc"))
    assert payload["trade"]["trade_id"] == "abc"
    assert payload["trade"]["status"] == "WIN"
    assert [row["event"] for row in payload["marks"]] == ["OPEN", "MARK", "CLOSE"]
    assert [row["price"] for row in payload["marks"]] == [100.0, 102.0, 105.0]
    assert payload["execution"] == "PAPER_ONLY"
    assert payload["live_capital_allowed"] is False


def test_archive_paper_trades_page_contract():
    text = PAGE.read_text(encoding="utf-8")
    for label in (
        "Paper Trades History",
        "Paper Performance",
        "Setup Breakdown",
        "Direction",
        "Trade Details",
        "Paper Statistics",
        "Cumulative R",
        "Drawdown",
    ):
        assert label in text
    assert "/api/archive/paper-trades" in text
    assert "TEST / SESSION_ROLL / INTERRUPTED excluded" in text
    assert "PAPER ONLY · no live capital" in text
    assert "hasNum" in text
    assert "v!==null&&v!==undefined&&v!==''" in text
    assert "173 trades" not in text.lower()
    assert ">173<" not in text
    assert "+28.37R" not in text
    assert "64.2%" not in text
    assert "+4.32R" not in text
    assert "-2.10R" not in text


def test_archive_paper_trades_route_serves_no_cache_html():
    response = TestClient(app).get("/dashboard/archive/paper-trades")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "no-store" in response.headers["cache-control"]
    assert "Archive / Paper Trades" in response.text


def test_archive_paper_trades_inline_javascript_compiles_with_node():
    html = PAGE.read_text(encoding="utf-8")
    scripts = re.findall(r"<script(?:[^>]*)>([\s\S]*?)</script>", html)
    inline = "\n".join(script for script in scripts if script.strip())
    result = subprocess.run(
        ["node", "-e", "new Function(" + repr(inline) + "); console.log('archive-paper-js-ok')"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "archive-paper-js-ok" in result.stdout
