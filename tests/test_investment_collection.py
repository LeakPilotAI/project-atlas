"""Collection monitor + dataset readiness. Deterministic. No live Yahoo. No trading."""

from __future__ import annotations

import inspect
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from app.investment.engine import format_dashboard
from app.investment.enums import InvestmentAlertState, ThesisState
from app.investment.integrity import audit_observation, pit_audit
from app.investment.monitor import collection_monitor, format_collection_monitor
from app.investment.provider_health import ProviderHealthBook
from app.investment.quality import asset_quality_breakdown, format_quality_breakdown
from app.investment.readiness import (
    READY_MIN_VALID,
    dataset_readiness,
    format_readiness,
)
from app.investment.scan import format_scan_dashboard
from app.investment.scan_models import ScanObservation, ScanReport


def _write(path: Path, rows: list) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def _row(**kw) -> dict:
    as_of = kw.get("as_of", "2026-08-20T16:00:00+00:00")
    known = kw.get(
        "known_at",
        {
            "as_of": as_of,
            "price_effective": as_of,
            "price_retrieved": as_of,
            "fundamentals_retrieved": as_of,
            "valuation_retrieved": as_of,
            "history_cutoff": str(as_of)[:10],
            "look_ahead_cutoff": str(as_of)[:10],
        },
    )
    return {
        "observation_id": kw.get("oid", f"{kw.get('symbol', 'AAA')}-1"),
        "as_of": as_of,
        "symbol": kw.get("symbol", "AAA"),
        "qualified": kw.get("qualified", False),
        "classification": kw.get("cls", "NO_ACTION"),
        "evaluation": kw.get("evaluation", "VALID_NO_ACTION"),
        "look_ahead_protected": kw.get("lap", True),
        "outcomes": kw.get("outcomes", {"price_20d": None, "return_20d": None}),
        "known_at": known,
        "field_quality": kw.get(
            "fq",
            {
                "price": "FRESH",
                "fundamentals.revenue": "FRESH",
                "valuation.pe": "FRESH",
                "history": "FRESH",
            },
        ),
        "research": {
            "evidence_quality": "MEDIUM",
            "input_snapshot": {
                "asset": {
                    "asset_type": kw.get("atype", "STOCK"),
                    "sector": kw.get("sector", "Health Care"),
                }
            },
        },
    }


def _diverse(n_valid=500, days=12, assets=16) -> list:
    rows = []
    sectors = ["Health Care", "Financials", "Energy", "Industrials", "Utilities"]
    types = ["STOCK", "ETF"]
    for i in range(n_valid):
        day = 10 + (i % days)
        rows.append(
            _row(
                oid=f"A{i}",
                symbol=f"S{i % assets:02d}",
                as_of=f"2026-08-{day:02d}T16:00:00+00:00",
                evaluation="VALID" if i % 7 == 0 else "VALID_NO_ACTION",
                cls="WATCH" if i % 7 == 0 else "NO_ACTION",
                qualified=(i % 7 == 0),
                atype=types[i % 2],
                sector=sectors[i % len(sectors)],
            )
        )
    return rows


def test_valid_observation_counting(tmp_path):
    p = _write(
        tmp_path / "o.jsonl",
        [
            _row(symbol="A", evaluation="VALID", cls="WATCH", qualified=True),
            _row(symbol="B", evaluation="VALID_NO_ACTION", cls="NO_ACTION"),
            _row(symbol="C", evaluation="INSUFFICIENT_DATA", cls="NO_ACTION"),
            _row(symbol="D", evaluation="PROVIDER_ERROR", cls="NO_ACTION"),
            _row(symbol="E", evaluation="UNKNOWN", cls="NO_ACTION"),
        ],
    )
    m = collection_monitor(p, provider=ProviderHealthBook())
    assert m["observations"] == 5
    assert m["valid_observations"] == 2
    assert m["valid"] == 1
    assert m["valid_no_action"] == 1
    assert m["insufficient_data"] == 1
    assert m["provider_error"] == 1
    assert m["unknown"] == 1
    assert m["potential_opportunities"] == 1
    assert m["rejected"] == 4


def test_negative_rejected_observations_are_kept(tmp_path):
    p = _write(
        tmp_path / "o.jsonl",
        [
            _row(symbol="Q", cls="DEEP_VALUE", evaluation="VALID", qualified=True),
            _row(symbol="R", cls="NO_ACTION", evaluation="VALID_NO_ACTION", qualified=False),
        ],
    )
    m = collection_monitor(p, provider=ProviderHealthBook())
    assert m["potential_opportunities"] == 1
    assert m["rejected"] == 1
    text = format_collection_monitor(m)
    assert "Rejected / no-action: 1" in text
    assert "win rate" not in text.lower()
    assert "alpha" not in text.lower() or "not" in text.lower()


def test_sector_and_asset_diversity(tmp_path):
    p = _write(
        tmp_path / "o.jsonl",
        [
            _row(symbol="A", atype="STOCK", sector="Health Care"),
            _row(symbol="B", atype="ETF", sector="Broad Market", oid="B-1"),
            _row(symbol="C", atype="STOCK", sector="Energy", oid="C-1"),
        ],
    )
    m = collection_monitor(p, provider=ProviderHealthBook())
    assert m["by_asset_type"]["STOCK"] == 2
    assert m["by_asset_type"]["ETF"] == 1
    assert "Health Care" in m["by_sector"]
    assert "Energy" in m["by_sector"]
    assert m["unique_assets"] == 3


def test_provider_reliability_calculations():
    book = ProviderHealthBook()
    book.record("OK", success=True)
    book.record("OK", success=True)
    book.record("OK", success=True)
    book.record("HTTP_401", success=False)
    book.record("RATE_LIMIT", success=False)
    d = book.as_dict()
    assert d["requests"] == 5
    assert d["successes"] == 3
    assert abs(d["success_rate"] - 0.6) < 1e-9
    assert abs(d["failure_rate"] - 0.4) < 1e-9
    assert d["http_401"] == 1
    assert d["http_429"] == 1


def test_missing_stale_conflicting_fields(tmp_path):
    p = _write(
        tmp_path / "o.jsonl",
        [
            _row(
                symbol="MSX",
                fq={"price": "FRESH", "fundamentals.revenue": "MISSING", "valuation.pe": "STALE", "history": "CONFLICTING"},
            ),
            _row(
                symbol="ETY",
                oid="ETY-1",
                fq={"price": "MISSING", "history": "UNKNOWN"},
            ),
        ],
    )
    q = asset_quality_breakdown(p)
    by = {a["symbol"]: a["groups"] for a in q["assets"]}
    assert by["MSX"]["price"] == "FRESH"
    assert by["MSX"]["fundamentals"] == "MISSING"
    assert by["MSX"]["valuation"] == "STALE"
    assert by["MSX"]["history"] == "CONFLICTING"
    assert by["MSX"]["news"] == "MISSING"
    assert by["MSX"]["macro"] == "MISSING"
    assert by["ETY"]["price"] == "MISSING"
    text = format_quality_breakdown(q)
    assert "MSX" in text
    assert "Price: FRESH" in text
    assert "Fundamentals: MISSING" in text


def test_point_in_time_validation_clean(tmp_path):
    p = _write(tmp_path / "o.jsonl", [_row()])
    a = pit_audit(p)
    assert a["observations"] == 1
    assert a["ok"] == 1
    assert a["lookahead_violations"] == 0
    assert a["clean"] is True


def test_lookahead_detection(tmp_path):
    bad = _row(
        as_of="2026-08-10T16:00:00+00:00",
        known_at={
            "as_of": "2026-08-10T16:00:00+00:00",
            "price_effective": "2026-08-20T16:00:00+00:00",
            "history_cutoff": "2026-08-20",
        },
    )
    leaked = _row(
        oid="LEAK-1",
        symbol="BBB",
        outcomes={"price_20d": 112.0, "return_20d": 0.12},
    )
    p = _write(tmp_path / "o.jsonl", [bad, leaked])
    a = pit_audit(p)
    assert a["lookahead_violations"] >= 1
    assert a["flagged"] >= 2
    assert a["clean"] is False
    flags = audit_observation(bad)["flags"]
    assert any("look-ahead" in f for f in flags)
    flags2 = audit_observation(leaked)["flags"]
    assert any("outcome fields" in f for f in flags2)


def test_readiness_not_ready_when_empty(tmp_path):
    p = _write(tmp_path / "o.jsonl", [])
    # empty file → no rows
    (tmp_path / "o.jsonl").write_text("", encoding="utf-8")
    r = dataset_readiness(tmp_path / "o.jsonl", provider=ProviderHealthBook())
    assert r["status"] == "NOT READY"
    text = format_readiness(r)
    assert "DATASET STATUS: NOT READY" in text
    assert "profitable" not in text.lower() or "does not mean" in text.lower()


def test_readiness_collecting_then_ready(tmp_path):
    small = [_row(symbol="A", evaluation="VALID", cls="WATCH", qualified=True)]
    p = _write(tmp_path / "s.jsonl", small)
    r = dataset_readiness(p, provider=ProviderHealthBook())
    assert r["status"] == "COLLECTING"
    assert r["checks"]["valid_observations"]["ok"] is False

    book = ProviderHealthBook()
    for _ in range(10):
        book.record("OK", success=True)
    ready_rows = _diverse()
    p2 = _write(tmp_path / "r.jsonl", ready_rows)
    r2 = dataset_readiness(p2, provider=book)
    assert r2["status"] == "READY FOR RESEARCH"
    assert r2["monitor"]["valid_observations"] >= READY_MIN_VALID
    assert "does not mean the strategy is profitable" in r2["disclaimer"].lower()


def test_readiness_lookahead_blocks_ready(tmp_path):
    book = ProviderHealthBook()
    for _ in range(10):
        book.record("OK", success=True)
    rows = _diverse()
    rows[0]["known_at"]["history_cutoff"] = "2099-01-01"
    p = _write(tmp_path / "x.jsonl", rows)
    r = dataset_readiness(p, provider=book)
    assert r["status"] == "NOT READY"
    assert r["checks"]["look_ahead"]["ok"] is False


def test_provider_failures_in_monitor(tmp_path):
    p = _write(
        tmp_path / "o.jsonl",
        [
            _row(evaluation="RATE_LIMITED", cls="NO_ACTION"),
            _row(symbol="B", oid="B1", evaluation="PROVIDER_ERROR", cls="NO_ACTION"),
            _row(symbol="C", oid="C1", evaluation="STALE_DATA", cls="WATCH", qualified=True),
        ],
    )
    m = collection_monitor(p, provider=ProviderHealthBook())
    assert m["rate_limited"] == 1
    assert m["provider_error"] == 1
    assert m["stale_data"] == 1


def test_dashboard_separates_data_quality_from_performance():
    from app.investment.drawdown import DrawdownReport
    from app.investment.enums import EvidenceQuality
    from app.investment.research_models import ComponentScores, ResearchRecord

    rec = ResearchRecord(
        symbol="XYZ",
        classification=InvestmentAlertState.WATCH,
        opportunity_score=45,
        evidence_quality=EvidenceQuality.MEDIUM,
        thesis=ThesisState.INTACT,
        components=ComponentScores(risk=50),
        drawdown=DrawdownReport(current_drawdown=-0.1),
    )
    text = format_dashboard([rec], [], None, session="MARKET_CLOSED")
    assert "DATA QUALITY" in text
    assert "INVESTMENT OPPORTUNITY" in text
    assert "PERFORMANCE" in text
    assert "No win rate" in text
    assert "No alpha" in text
    report = ScanReport(scan_id="s", universe=1, evaluated=1, observations=[], evaluation_counts={"VALID": 0})
    scan_text = format_scan_dashboard(report)
    assert "DATA QUALITY" in scan_text
    assert "PERFORMANCE" in scan_text
    assert "win rate" in scan_text.lower()


def test_collection_isolation():
    import app.investment.integrity as i
    import app.investment.monitor as m
    import app.investment.quality as q
    import app.investment.readiness as r

    for mod in (i, m, q, r):
        src = Path(inspect.getfile(mod)).read_text(encoding="utf-8")
        assert "from app.services" not in src
        assert "from app.adapters" not in src
        assert "perp_micro" not in src
        assert not re.search(r"\bRSI\b", src)
        assert "sklearn" not in src
