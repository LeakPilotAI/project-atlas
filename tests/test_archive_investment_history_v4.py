import asyncio
import json
from pathlib import Path
import re
import subprocess

from fastapi.testclient import TestClient

from app.investment.bars import OhlcvBar
from app.investment.paper_book import PaperBook
from app.main import app
import app.api.archive as archive_api


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "backend" / "app" / "static" / "archive.html"


def test_archive_investment_history_builds_from_real_paper_book_and_ledger(tmp_path, monkeypatch):
    state = tmp_path / "paper_account.json"
    ledger = tmp_path / "paper_investment_ledger.jsonl"
    plans = tmp_path / "daily_manual_research_plans.jsonl"

    book = PaperBook(cash=10000.0, state_path=state, ledger_path=ledger)
    fill = book.research_buy("MSFT", 300.0, 1200.0, reason="test accumulation")
    assert fill is not None
    book.mark({"MSFT": 330.0})

    plans.write_text(
        json.dumps(
            {
                "timestamp": "2026-10-01T12:00:00+00:00",
                "status": "MANUAL_RESEARCH_ONLY",
                "planning_model_version": "manual-daily-research-v1",
                "current_research_allocation": 500.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(archive_api, "PAPER_STATE_PATH", state)
    monkeypatch.setattr(archive_api, "LEDGER_PATH", ledger)
    monkeypatch.setattr(archive_api, "PLAN_PATH", plans)

    payload = archive_api._build_investment_history(100)
    assert payload["domain"] == "INVESTMENT_ARCHIVE"
    assert payload["execution"] == "PAPER_RESEARCH_ONLY"
    assert payload["live_capital_allowed"] is False
    assert payload["automatic_real_money_execution"] is False
    assert payload["summary"]["open_positions"] == 1
    assert payload["summary"]["paper_fills"] == 1
    assert payload["summary"]["realized_performance_supported"] is False
    assert payload["summary"]["win_rate"] is None
    assert payload["positions"][0]["symbol"] == "MSFT"
    assert payload["positions"][0]["unrealized_pnl"] > 0
    assert payload["events"][0]["status"] == "PAPER_FILLED"
    assert payload["events"][0]["exit_price"] is None
    assert payload["events"][0]["realized_pnl"] is None
    assert payload["daily_plan_history"][0]["status"] == "MANUAL_RESEARCH_ONLY"
    assert payload["capabilities"]["closed_long_horizon_investment_exits"] is False
    assert payload["capabilities"]["broker_history"] is False


def test_archive_investment_history_bars_are_read_only_real_history(monkeypatch):
    bars = [
        OhlcvBar("2026-09-29", open=100, high=103, low=99, close=102, volume=1000),
        OhlcvBar("2026-09-30", open=102, high=105, low=101, close=104, volume=1100),
    ]
    monkeypatch.setattr(archive_api, "load_bars", lambda symbol: bars)

    payload = asyncio.run(archive_api.investment_history_bars("msft", limit=20))
    assert payload["symbol"] == "MSFT"
    assert payload["execution"] == "READ_ONLY"
    assert payload["live_capital_allowed"] is False
    assert [row["close"] for row in payload["bars"]] == [102, 104]


def test_archive_investment_history_page_contract():
    text = PAGE.read_text(encoding="utf-8")
    for label in (
        "Investment History",
        "Open Investment Book",
        "Daily Research Plans",
        "Position Details",
        "REALIZED INVESTMENT PERFORMANCE NOT YET SUPPORTED",
        "no closed investment exits recorded",
    ):
        assert label in text
    assert "/api/archive/investment-history?limit=400" in text
    assert "/api/archive/investment-history/" in text
    assert "PAPER research only" in text
    assert "no live brokerage execution" in text
    # Honest disclosure may mention unsupported realized metrics by name.
    # Guard against rendering fake realized-performance metric cards/values instead.
    assert '<div class="label">Win Rate</div>' not in text
    assert "68.1%" not in text
    assert "BEST POSITION" not in text


def test_archive_workspace_route_serves_no_cache_html():
    response = TestClient(app).get("/dashboard/archive")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "no-store" in response.headers["cache-control"]
    assert "Archive / Investment History" in response.text


def test_archive_inline_javascript_compiles_with_node():
    html = PAGE.read_text(encoding="utf-8")
    scripts = re.findall(r"<script(?:[^>]*)>([\s\S]*?)</script>", html)
    inline = "\n".join(script for script in scripts if script.strip())
    result = subprocess.run(
        ["node", "-e", "new Function(" + repr(inline) + "); console.log('archive-js-ok')"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "archive-js-ok" in result.stdout
