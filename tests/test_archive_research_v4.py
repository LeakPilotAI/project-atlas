import asyncio
import json
from pathlib import Path
import re
import subprocess

from fastapi.testclient import TestClient

import app.api.archive as archive_api
from app.main import app


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "backend" / "app" / "static" / "archive_research.html"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _research_row(
    *,
    timestamp: str,
    symbol: str,
    asset_type: str,
    sector: str,
    classification: str,
    score: int | None,
    evidence: str,
    thesis: str,
) -> dict:
    return {
        "scoring_version": "atlas-invest-3.0",
        "timestamp": timestamp,
        "symbol": symbol,
        "asset_type": asset_type,
        "name": f"{symbol} Name",
        "price": 123.45,
        "classification": classification,
        "opportunity_score": score,
        "evidence_quality": evidence,
        "thesis": thesis,
        "components": {
            "valuation": 72,
            "fundamentals": 81,
            "drawdown": 64,
            "balance_sheet": 77,
            "growth": None,
            "cash_flow": 75,
            "thesis_integrity": 82,
            "risk": 68,
            "evidence_quality": 80,
        },
        "drawdown": {
            "current_drawdown": -0.22,
            "drawdown_52w": -0.18,
            "drawdown_percentile": 88,
        },
        "explain": {
            "why_this_asset": [f"{symbol} research asset"],
            "why_interesting": ["valuation component is attractive"],
            "why_now": ["material drawdown from sample high"],
            "supports_thesis": ["cash generation is positive"],
            "weakens_thesis": ["single current-state risk"],
            "missing_data": ["fundamental growth history"],
            "invalidation": ["evidence quality falls to insufficient"],
            "risks": ["market volatility elevated"],
            "data_quality_notes": ["evidence quality tracked"],
        },
        "generational_blockers": ["generational gate not satisfied"],
        "coverage_label": "3y daily coverage",
        "input_snapshot": {
            "asset": {
                "symbol": symbol,
                "name": f"{symbol} Name",
                "asset_type": asset_type,
                "sector": sector,
            }
        },
        "disclaimer": "Opportunity scores are ordinal research rankings, not probabilities.",
    }


def test_research_archive_builds_from_append_only_research_store(tmp_path, monkeypatch):
    path = tmp_path / "opportunities.jsonl"
    _write_jsonl(
        path,
        [
            _research_row(
                timestamp="2026-09-20T12:00:00+00:00",
                symbol="MSFT",
                asset_type="STOCK",
                sector="Technology",
                classification="ACCUMULATION",
                score=78,
                evidence="HIGH",
                thesis="INTACT",
            ),
            _research_row(
                timestamp="2026-10-01T12:00:00+00:00",
                symbol="NVDA",
                asset_type="STOCK",
                sector="Technology",
                classification="WATCH",
                score=61,
                evidence="MEDIUM",
                thesis="STRONG",
            ),
            _research_row(
                timestamp="2026-10-01T13:00:00+00:00",
                symbol="BTC",
                asset_type="OTHER",
                sector="",
                classification="NO_ACTION",
                score=None,
                evidence="LOW",
                thesis="UNKNOWN",
            ),
        ],
    )
    monkeypatch.setattr(archive_api, "OPPORTUNITIES_PATH", path)

    payload = archive_api._build_research_archive(
        date_range="all",
        asset_type="",
        sector="",
        classification="",
        evidence="",
        thesis="",
        scoring_version="",
        search="",
        limit=100,
    )
    summary = payload["summary"]
    assert payload["domain"] == "INVESTMENT_RESEARCH_ARCHIVE"
    assert payload["execution"] == "RESEARCH_ONLY"
    assert payload["live_capital_allowed"] is False
    assert payload["automatic_real_money_execution"] is False
    assert summary["records"] == 3
    assert summary["tracked_symbols"] == 3
    assert summary["classification_count"] == 3
    assert summary["high_evidence_records"] == 1
    assert summary["intact_or_strong_thesis_records"] == 2
    assert summary["research_win_rate"] is None
    assert summary["outcome_linkage_supported"] is False
    assert payload["top_research_scores"][0]["symbol"] == "MSFT"
    assert "Technology" in payload["facets"]["sectors"]
    assert any(row["name"] == "ACCUMULATION" for row in payload["breakdowns"]["classification"])
    assert payload["records"][0]["symbol"] == "BTC"


def test_research_archive_filters_and_detail_use_real_record_fields(tmp_path, monkeypatch):
    path = tmp_path / "opportunities.jsonl"
    msft = _research_row(
        timestamp="2026-10-01T12:00:00+00:00",
        symbol="MSFT",
        asset_type="STOCK",
        sector="Technology",
        classification="ACCUMULATION",
        score=82,
        evidence="HIGH",
        thesis="INTACT",
    )
    nvda = _research_row(
        timestamp="2026-10-01T13:00:00+00:00",
        symbol="NVDA",
        asset_type="STOCK",
        sector="Technology",
        classification="WATCH",
        score=62,
        evidence="MEDIUM",
        thesis="STRONG",
    )
    _write_jsonl(path, [msft, nvda])
    monkeypatch.setattr(archive_api, "OPPORTUNITIES_PATH", path)

    payload = archive_api._build_research_archive(
        date_range="all",
        asset_type="STOCK",
        sector="Technology",
        classification="ACCUMULATION",
        evidence="HIGH",
        thesis="INTACT",
        scoring_version="atlas-invest-3.0",
        search="cash generation",
        limit=100,
    )
    assert payload["summary"]["records"] == 1
    assert payload["records"][0]["symbol"] == "MSFT"

    rid = payload["records"][0]["record_id"]
    detail = asyncio.run(archive_api.research_archive_detail(rid))
    assert detail["record"]["symbol"] == "MSFT"
    assert detail["record"]["opportunity_score"] == 82
    assert detail["record"]["sector"] == "Technology"
    assert detail["execution"] == "RESEARCH_ONLY"
    assert detail["live_capital_allowed"] is False


def test_archive_research_page_contract():
    text = PAGE.read_text(encoding="utf-8")
    for label in (
        "Research Archive",
        "Research Filters",
        "Research Record Preview",
        "Classification Breakdown",
        "Research Activity",
        "Top Research Scores",
        "Research Outcomes",
        "EXECUTED OUTCOME LINKAGE UNAVAILABLE",
    ):
        assert label in text
    assert "/api/archive/research-archive" in text
    assert "scores are ordinal, not probabilities" in text
    assert "Research win rate and executed-idea returns are therefore not shown." in text
    # Guard against copying mock reference telemetry into production while allowing
    # incidental digits in CSS or implementation details.
    assert "412 research" not in text.lower()
    assert ">412<" not in text
    assert "71.4%" not in text
    assert "+21.8%" not in text
    assert "NVDA +208.4%" not in text


def test_archive_research_route_serves_no_cache_html():
    response = TestClient(app).get("/dashboard/archive/research")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "no-store" in response.headers["cache-control"]
    assert "Archive / Research Archive" in response.text


def test_archive_research_inline_javascript_compiles_with_node():
    html = PAGE.read_text(encoding="utf-8")
    scripts = re.findall(r"<script(?:[^>]*)>([\s\S]*?)</script>", html)
    inline = "\n".join(script for script in scripts if script.strip())
    result = subprocess.run(
        ["node", "-e", "new Function(" + repr(inline) + "); console.log('archive-research-js-ok')"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "archive-research-js-ok" in result.stdout
