import asyncio
import json
from pathlib import Path
import re
import subprocess

from fastapi.testclient import TestClient

import app.api.archive as archive_api
from app.main import app


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "backend" / "app" / "static" / "archive_snapshots.html"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _measured(value, *, source="yahoo", quality="FRESH", available=True):
    return {
        "value": value,
        "source": source,
        "quality": quality,
        "availability": available,
        "timestamp": "2026-10-01T12:00:00+00:00",
        "effective_timestamp": "2026-10-01T12:00:00+00:00",
        "retrieved_at": "2026-10-01T12:05:00+00:00",
        "notes": "",
    }


def _snapshot(
    *,
    retrieved_at: str,
    symbol: str,
    asset_type: str,
    sector: str,
    price: float,
    quality: str = "FRESH",
    failures: list | None = None,
):
    return {
        "asset": {
            "symbol": symbol,
            "name": f"{symbol} Name",
            "asset_type": asset_type,
            "sector": sector,
            "industry": "Software" if sector == "Technology" else "",
            "exchange": "NASDAQ",
            "currency": "USD",
            "active": True,
        },
        "retrieved_at": retrieved_at,
        "price": _measured(price, quality=quality),
        "market_cap": _measured(100_000_000_000),
        "latest_bar": {
            "date": "2026-10-01",
            "open": price - 1,
            "high": price + 2,
            "low": price - 2,
            "close": price,
            "volume": 1_000_000,
            "source": "yahoo",
        },
        "fundamentals": {
            "revenue": _measured(80_000_000_000),
            "earnings": _measured(15_000_000_000),
            "free_cash_flow": _measured(12_000_000_000),
        },
        "valuation": {
            "pe": _measured(22.5),
            "fcf_yield": _measured(0.04),
        },
        "failures": failures or [],
        "history_rows_stored": 500,
    }


def test_snapshot_archive_builds_from_structured_snapshot_store(tmp_path, monkeypatch):
    path = tmp_path / "snapshots.jsonl"
    _write_jsonl(
        path,
        [
            _snapshot(
                retrieved_at="2026-09-30T12:00:00+00:00",
                symbol="MSFT",
                asset_type="STOCK",
                sector="Technology",
                price=410.0,
            ),
            _snapshot(
                retrieved_at="2026-10-01T12:00:00+00:00",
                symbol="MSFT",
                asset_type="STOCK",
                sector="Technology",
                price=415.0,
            ),
            _snapshot(
                retrieved_at="2026-10-01T13:00:00+00:00",
                symbol="SPY",
                asset_type="ETF",
                sector="",
                price=620.0,
                quality="STALE",
                failures=[{"provider": "yahoo", "reason": "quote stale"}],
            ),
        ],
    )
    monkeypatch.setattr(archive_api, "SNAPSHOTS_PATH", path)

    payload = archive_api._build_snapshot_archive(
        date_range="all",
        asset_type="",
        symbol="",
        sector="",
        quality="",
        source="",
        search="",
        limit=100,
    )
    summary = payload["summary"]
    assert payload["domain"] == "INVESTMENT_SNAPSHOT_ARCHIVE"
    assert payload["execution"] == "READ_ONLY"
    assert payload["live_capital_allowed"] is False
    assert payload["automatic_real_money_execution"] is False
    assert summary["snapshots"] == 3
    assert summary["tracked_symbols"] == 2
    assert summary["asset_type_count"] == 2
    assert summary["fresh_price_records"] == 2
    assert summary["records_with_failures"] == 1
    assert len(payload["price_history"]["MSFT"]) == 2
    assert payload["breakdowns"]["top_assets"][0] == {"symbol": "MSFT", "count": 2}
    assert payload["records"][0]["symbol"] == "SPY"
    assert payload["records"][0]["price_quality"] == "STALE"


def test_snapshot_archive_filters_and_detail_use_real_snapshot_fields(tmp_path, monkeypatch):
    path = tmp_path / "snapshots.jsonl"
    msft = _snapshot(
        retrieved_at="2026-10-01T12:00:00+00:00",
        symbol="MSFT",
        asset_type="STOCK",
        sector="Technology",
        price=415.0,
    )
    spy = _snapshot(
        retrieved_at="2026-10-01T13:00:00+00:00",
        symbol="SPY",
        asset_type="ETF",
        sector="",
        price=620.0,
        quality="STALE",
    )
    _write_jsonl(path, [msft, spy])
    monkeypatch.setattr(archive_api, "SNAPSHOTS_PATH", path)

    payload = archive_api._build_snapshot_archive(
        date_range="all",
        asset_type="STOCK",
        symbol="MSFT",
        sector="Technology",
        quality="FRESH",
        source="yahoo",
        search="MSFT",
        limit=100,
    )
    assert payload["summary"]["snapshots"] == 1
    row = payload["records"][0]
    assert row["symbol"] == "MSFT"
    assert row["price"] == 415.0
    assert row["usable_fundamental_fields"] == 3
    assert row["usable_valuation_fields"] == 2
    assert row["history_rows_stored"] == 500

    detail = asyncio.run(archive_api.snapshot_archive_detail(row["record_id"]))
    assert detail["record"]["symbol"] == "MSFT"
    assert detail["record"]["latest_bar"]["close"] == 415.0
    assert detail["execution"] == "READ_ONLY"
    assert detail["live_capital_allowed"] is False


def test_archive_snapshots_page_contract():
    text = PAGE.read_text(encoding="utf-8")
    for label in (
        "Snapshot Gallery",
        "Snapshot Filters",
        "Snapshot Preview",
        "Asset Type Distribution",
        "Snapshot Activity",
        "Top Assets In Snapshots",
        "Recent Snapshots",
        "structured InvestmentSnapshot",
    ):
        assert label in text
    assert "/api/archive/snapshots" in text
    assert "no screenshot/image attachment archive" in text
    assert "user-created chart screenshots" in text
    assert "Chart Snapshots" not in text
    assert "Watchlist Snaps" not in text
    assert "NVDA - Daily Setup" not in text
    assert "50.0%" not in text


def test_archive_snapshots_route_serves_no_cache_html():
    response = TestClient(app).get("/dashboard/archive/snapshots")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "no-store" in response.headers["cache-control"]
    assert "Archive / Snapshots" in response.text


def test_archive_snapshots_inline_javascript_compiles_with_node():
    html = PAGE.read_text(encoding="utf-8")
    scripts = re.findall(r"<script(?:[^>]*)>([\s\S]*?)</script>", html)
    inline = "\n".join(script for script in scripts if script.strip())
    result = subprocess.run(
        ["node", "-e", "new Function(" + repr(inline) + "); console.log('archive-snapshots-js-ok')"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "archive-snapshots-js-ok" in result.stdout
