import asyncio
import json
from pathlib import Path
import re
import subprocess

from fastapi.testclient import TestClient

import app.api.archive as archive_api
from app.main import app


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "backend" / "app" / "static" / "archive_export.html"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_archive_export_summary_and_preview_use_real_sources(tmp_path, monkeypatch):
    paper = tmp_path / "paper.jsonl"
    invest = tmp_path / "invest.jsonl"
    research = tmp_path / "research.jsonl"
    snaps = tmp_path / "snapshots.jsonl"
    plans = tmp_path / "plans.jsonl"
    universe = tmp_path / "universe.json"

    _write_jsonl(
        paper,
        [
            {"timestamp": "2026-09-01T12:00:00+00:00", "event": "open", "symbol": "BTC"},
            {"timestamp": "2026-10-01T12:00:00+00:00", "event": "close", "symbol": "BTC"},
        ],
    )
    _write_jsonl(invest, [{"at": "2026-10-01T10:00:00+00:00", "kind": "research_buy", "symbol": "MSFT"}])
    _write_jsonl(research, [{"timestamp": "2026-10-01T09:00:00+00:00", "symbol": "NVDA", "stance": "WATCH"}])
    _write_jsonl(snaps, [{"retrieved_at": "2026-10-01T08:00:00+00:00", "asset": {"symbol": "AAPL"}}])
    _write_jsonl(plans, [{"timestamp": "2026-10-01T07:00:00+00:00", "status": "MANUAL_RESEARCH_ONLY"}])
    universe.write_text(json.dumps({"symbols": {"MSFT": {"name": "Microsoft"}}}), encoding="utf-8")

    monkeypatch.setattr(archive_api, "JOURNAL_PATH", paper)
    monkeypatch.setattr(archive_api, "LEDGER_PATH", invest)
    monkeypatch.setattr(archive_api, "OPPORTUNITIES_PATH", research)
    monkeypatch.setattr(archive_api, "SNAPSHOTS_PATH", snaps)
    monkeypatch.setattr(archive_api, "PLAN_PATH", plans)
    monkeypatch.setattr(archive_api, "UNIVERSE_PATH", universe)

    summary = archive_api._export_summary()
    assert summary["domain"] == "ARCHIVE_EXPORT"
    assert summary["mode"] == "READ_ONLY_DOWNLOAD"
    assert summary["totals"]["available_sources"] == 6
    assert summary["totals"]["rows"] == 7
    assert summary["capabilities"]["csv"] is True
    assert summary["capabilities"]["jsonl"] is True
    assert summary["capabilities"]["persistent_export_history"] is False
    assert summary["capabilities"]["scheduled_exports"] is False

    preview = asyncio.run(
        archive_api.export_preview(dataset="paper_trades", date_range="all", limit=10)
    )
    assert preview["label"] == "Paper Trades"
    assert preview["row_count"] == 2
    assert preview["rows"][0]["event"] == "close"


def test_archive_export_download_is_read_only_csv(tmp_path, monkeypatch):
    paper = tmp_path / "paper.jsonl"
    _write_jsonl(
        paper,
        [{"timestamp": "2026-10-01T12:00:00+00:00", "event": "close", "symbol": "BTC", "R_multiple": 1.25}],
    )
    monkeypatch.setattr(archive_api, "JOURNAL_PATH", paper)

    response = asyncio.run(
        archive_api.export_download(dataset="paper_trades", format="csv", date_range="all")
    )
    body = response.body.decode("utf-8-sig")
    assert response.status_code == 200
    assert "text/csv" in response.media_type
    assert "attachment;" in response.headers["content-disposition"]
    assert "symbol" in body
    assert "BTC" in body
    assert paper.exists()
    assert paper.read_text(encoding="utf-8").count("\n") == 1


def test_archive_export_page_contract():
    text = PAGE.read_text(encoding="utf-8")
    for label in (
        "Export Options",
        "Export Preview",
        "Archive Source Inventory",
        "Export History",
        "Quick Exports",
        "SCHEDULED EXPORTS NOT ENABLED",
    ):
        assert label in text
    assert "/api/archive/export/summary" in text
    assert "/api/archive/export/preview" in text
    assert "/api/archive/export/download" in text
    assert "CSV Spreadsheet" in text
    assert "JSON Lines" in text
    assert "this browser session only" in text
    assert "Atlas does not persist export-generation history" in text
    assert "No background export jobs" in text
    # Guard against copying mock reference telemetry into production without
    # rejecting incidental CSS/color literals that may contain the same digits.
    assert "86 Exports" not in text
    assert "86 exports" not in text
    assert ">86<" not in text
    assert "482 MB" not in text


def test_archive_export_route_serves_no_cache_html():
    response = TestClient(app).get("/dashboard/archive/export")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "no-store" in response.headers["cache-control"]
    assert "Archive / Export" in response.text


def test_archive_export_inline_javascript_compiles_with_node():
    html = PAGE.read_text(encoding="utf-8")
    scripts = re.findall(r"<script(?:[^>]*)>([\s\S]*?)</script>", html)
    inline = "\n".join(script for script in scripts if script.strip())
    result = subprocess.run(
        ["node", "-e", "new Function(" + repr(inline) + "); console.log('archive-export-js-ok')"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "archive-export-js-ok" in result.stdout
