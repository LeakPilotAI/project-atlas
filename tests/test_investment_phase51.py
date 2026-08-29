"""Phase 5.1 — collection integrity. Deterministic. No live Yahoo. No trading imports."""

from __future__ import annotations

import asyncio
import inspect
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.investment.completeness import COMPLETENESS_FIELDS, completeness_report
from app.investment.dataset import dataset_stats, format_dataset_report
from app.investment.diagnostics import format_data_health, format_scanner_health
from app.investment.enums import (
    DataQuality,
    EvaluationStatus,
    EvidenceQuality,
    InvestmentAlertState,
    ThesisState,
)
from app.investment.evaluation import classify_evaluation
from app.investment.freshness import restamp
from app.investment.models import MeasuredValue
from app.investment.outcomes import empty_outcomes, persist_outcome
from app.investment.provider_health import ProviderHealthBook
from app.investment.research_models import ComponentScores, ResearchRecord
from app.investment.scan import FetchState, plan_fetches
from app.investment.scan_models import ScanObservation, ScanReport
from app.investment.scan_settings import ScanSettings
from app.investment.snapshot import (
    load_latest_snapshot,
    save_latest_snapshot,
    snapshot_from_parts,
)
from app.investment.universe import UniverseEntry
from app.investment.yfinance_client import wrap_provider_error


def _entry(sym="XYZ"):
    return UniverseEntry(symbol=sym, name="Test", active=True)


def mv(v, q=DataQuality.FRESH, ts=None):
    return MeasuredValue.of(v, source="test", quality=q, timestamp=ts)


def _snap(price=50.0, pq=DataQuality.FRESH, funds=True, failures=None, ts=None):
    e = _entry()
    fund = {}
    if funds:
        fund = {
            "revenue": mv(1e9, pq, ts),
            "earnings": mv(1e8, pq, ts),
            "eps": mv(2.0, pq, ts),
            "free_cash_flow": mv(8e7, pq, ts),
            "operating_cash_flow": mv(1e8, pq, ts),
            "cash": mv(5e8, pq, ts),
            "total_debt": mv(1e8, pq, ts),
            "market_cap": mv(8e9, pq, ts),
        }
    val = {"pe": mv(14, pq, ts), "ps": mv(2, pq, ts), "fcf_yield": mv(0.06, pq, ts)} if funds else {}
    return snapshot_from_parts(
        e,
        price=mv(price, pq, ts),
        fundamentals=fund,
        valuation=val,
        failures=failures or [],
    )


def _rec(**kw):
    return ResearchRecord(
        symbol=kw.get("symbol", "XYZ"),
        classification=kw.get("cls", InvestmentAlertState.NO_ACTION),
        opportunity_score=kw.get("score", 40),
        evidence_quality=kw.get("evidence", EvidenceQuality.MEDIUM),
        thesis=kw.get("thesis", ThesisState.INTACT),
        components=ComponentScores(valuation=40, fundamentals=70),
        missing_critical=kw.get("missing", []),
        generational_blockers=kw.get("blockers", ["valuation missing or not attractive (need ≥ 70)"]),
    )


def test_valid_no_action_is_not_insufficient():
    snap = _snap()
    rec = _rec(cls=InvestmentAlertState.NO_ACTION, evidence=EvidenceQuality.MEDIUM, blockers=["valuation not attractive"])
    st, reason = classify_evaluation(snap, rec)
    assert st is EvaluationStatus.VALID_NO_ACTION
    assert "attractive" in reason.lower() or "valuation" in reason.lower()
    assert st is not EvaluationStatus.INSUFFICIENT_DATA


def test_insufficient_data_distinct():
    snap = _snap(funds=False)
    snap.price = MeasuredValue.unknown("test", "missing")
    rec = _rec(evidence=EvidenceQuality.INSUFFICIENT, missing=["price", "revenue"], score=None)
    rec.opportunity_score = None
    st, reason = classify_evaluation(snap, rec)
    assert st is EvaluationStatus.INSUFFICIENT_DATA
    assert st is not EvaluationStatus.VALID_NO_ACTION


def test_provider_error_and_rate_limit_distinct():
    snap = _snap(funds=False)
    snap.price = MeasuredValue.unknown("yfinance", "401")
    rec = _rec(evidence=EvidenceQuality.INSUFFICIENT, score=None)
    rec.opportunity_score = None
    st, _ = classify_evaluation(snap, rec, failures=[{"code": "HTTP_401", "message": "unauthorized"}])
    assert st is EvaluationStatus.PROVIDER_ERROR
    st2, _ = classify_evaluation(snap, rec, failures=[{"code": "RATE_LIMIT", "message": "429"}])
    assert st2 is EvaluationStatus.RATE_LIMITED
    assert st2 is not st


def test_stale_data_not_marked_fresh():
    old = datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc)
    snap = _snap(pq=DataQuality.FRESH, ts=old)
    now = datetime(2026, 8, 28, 15, 0, tzinfo=timezone.utc)
    snap.price = restamp(snap.price, kind="price", now=now)
    assert snap.price.quality is DataQuality.STALE
    rec = _rec(evidence=EvidenceQuality.MEDIUM)
    st, reason = classify_evaluation(snap, rec)
    assert st is EvaluationStatus.STALE_DATA
    assert "STALE" in reason


def test_conflicting_data_status():
    snap = _snap()
    snap.price.quality = DataQuality.CONFLICTING
    rec = _rec()
    st, _ = classify_evaluation(snap, rec)
    assert st is EvaluationStatus.CONFLICTING_DATA


def test_completeness_is_diagnostic_not_confidence():
    snap = _snap()
    rep = completeness_report(snap, evidence=EvidenceQuality.MEDIUM)
    assert rep["required"] == 12
    assert len(COMPLETENESS_FIELDS) == 12
    assert rep["present"] >= 9
    assert "not investment confidence" in rep["note"].lower()
    empty = completeness_report(_snap(funds=False), evidence=EvidenceQuality.INSUFFICIENT)
    # price only
    assert empty["present"] <= 2
    assert empty["label"].endswith("/ 12")


def test_provider_health_counters(tmp_path):
    book = ProviderHealthBook(path=tmp_path / "h.json", log_path=tmp_path / "h.jsonl", persist=True)
    book.record("OK", success=True)
    book.record("OK", success=True)
    book.record("HTTP_401", success=False, message="crumb")
    book.record("RATE_LIMIT", success=False)
    book.record("TIMEOUT", success=False)
    book.record("EMPTY", success=False)
    d = book.as_dict()
    assert d["requests"] == 6
    assert d["successes"] == 2
    assert d["http_401"] == 1
    assert d["http_429"] == 1
    assert d["timeouts"] == 1
    assert d["empty"] == 1
    assert d["status"] in {"DEGRADED", "DOWN", "OK"}
    loaded = ProviderHealthBook.load(tmp_path / "h.json")
    assert loaded.http_401 == 1


def test_wrap_401_is_structured():
    err = wrap_provider_error(RuntimeError("HTTP Error 401: Unauthorized Invalid Crumb"), "SPY")
    assert err.failure.code == "HTTP_401"
    assert err.failure.retryable is False


def test_cache_reuse_and_stale_refresh(tmp_path):
    st = FetchState(path=tmp_path / "f.json")
    cfg = ScanSettings(price_refresh_seconds=900, fundamental_refresh_seconds=86400, valuation_refresh_seconds=86400, history_refresh_seconds=86400)
    now = datetime(2026, 8, 24, 15, 0, tzinfo=timezone.utc)  # Monday 11 ET
    # no prior → must fetch
    p0 = plan_fetches("SPY", session="MARKET_OPEN", settings=cfg, state=st, now=now, has_prior=False, has_history=False)
    assert p0.price is True
    st.touch("SPY", price=now, fundamentals=now, valuation=now, history=now)
    p1 = plan_fetches("SPY", session="MARKET_OPEN", settings=cfg, state=st, now=now + timedelta(minutes=1), has_prior=True, has_history=True)
    assert p1.price is False
    assert p1.fundamentals is False
    # stale cache → refresh
    p2 = plan_fetches(
        "SPY",
        session="MARKET_OPEN",
        settings=cfg,
        state=st,
        now=now + timedelta(hours=2),
        has_prior=True,
        has_history=True,
    )
    assert p2.price is True


def test_latest_snapshot_roundtrip(tmp_path):
    snap = _snap(price=42.5)
    save_latest_snapshot(snap, root=tmp_path)
    loaded = load_latest_snapshot("XYZ", root=tmp_path)
    assert loaded is not None
    assert loaded.asset.symbol == "XYZ"
    assert loaded.price.value == 42.5
    assert loaded.price.quality is DataQuality.FRESH


def test_point_in_time_fields_on_observation():
    as_of = datetime(2026, 8, 28, 16, 0, tzinfo=timezone.utc)
    rec = _rec()
    obs = ScanObservation(
        scan_id="s",
        as_of=as_of,
        symbol="XYZ",
        classification="NO_ACTION",
        evaluation=EvaluationStatus.VALID_NO_ACTION.value,
        evaluation_reason="valuation not attractive",
        completeness={"present": 9, "required": 12, "label": "9 / 12"},
        known_at={
            "as_of": as_of.isoformat(),
            "price_effective": as_of.isoformat(),
            "price_retrieved": as_of.isoformat(),
            "fundamentals_retrieved": as_of.isoformat(),
            "valuation_retrieved": as_of.isoformat(),
            "history_cutoff": "2026-08-27",
            "look_ahead_cutoff": "2026-08-28",
        },
        research=rec,
        outcomes=empty_outcomes(),
    )
    d = obs.as_dict()
    assert d["evaluation"] == "VALID_NO_ACTION"
    assert d["known_at"]["history_cutoff"] == "2026-08-27"
    assert d["known_at"]["as_of"]
    assert d["outcomes"]["price_20d"] is None
    assert d["look_ahead_protected"] is True


def test_outcome_enrichment_does_not_rewrite_observation(tmp_path):
    obs_path = tmp_path / "obs.jsonl"
    row = {
        "observation_id": "XYZ-T",
        "as_of": "2026-08-01T16:00:00+00:00",
        "symbol": "XYZ",
        "classification": "DEEP_VALUE",
        "opportunity_score": 88,
        "price": 100,
        "outcomes": empty_outcomes(),
        "look_ahead_protected": True,
    }
    obs_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    persist_outcome(
        observation_id="XYZ-T",
        symbol="XYZ",
        as_of=datetime(2026, 8, 1, 16, tzinfo=timezone.utc),
        outcomes={"price_20d": 112.0, "return_20d": 0.12, **{k: None for k in empty_outcomes() if k not in ("price_20d", "return_20d")}},
        path=tmp_path / "out.jsonl",
        now=datetime(2026, 8, 28, tzinfo=timezone.utc),
    )
    original = json.loads(obs_path.read_text().splitlines()[0])
    assert original["price"] == 100
    assert original["opportunity_score"] == 88
    assert original["outcomes"]["price_20d"] is None
    later = json.loads((tmp_path / "out.jsonl").read_text().splitlines()[0])
    assert later["price_20d"] == 112.0
    assert later["observation_id"] == "XYZ-T"


def test_dataset_statistics_and_classification_counts(tmp_path):
    p = tmp_path / "obs.jsonl"
    rows = []
    for i, (sym, cls, ev) in enumerate(
        [
            ("AAA", "WATCH", "VALID"),
            ("BBB", "NO_ACTION", "VALID_NO_ACTION"),
            ("CCC", "NO_ACTION", "INSUFFICIENT_DATA"),
            ("AAA", "DEEP_VALUE", "VALID"),
            ("DDD", "NO_ACTION", "PROVIDER_ERROR"),
        ]
    ):
        rows.append(
            {
                "observation_id": f"{sym}-{i}",
                "as_of": f"2026-08-2{i+1}T16:00:00+00:00",
                "symbol": sym,
                "classification": cls,
                "evaluation": ev,
                "research": {
                    "evidence_quality": "MEDIUM",
                    "input_snapshot": {"asset": {"sector": "Health Care" if i % 2 else "Financials"}},
                },
            }
        )
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    stats = dataset_stats(observations_path=p, outcomes_path=tmp_path / "none.jsonl")
    assert stats["observations"] == 5
    assert stats["unique_assets"] == 4
    assert stats["valid_evaluations"] == 3  # VALID + VALID_NO_ACTION
    assert stats["insufficient_data"] == 1
    assert stats["provider_error"] == 1
    assert stats["classifications"]["WATCH"] == 1
    assert stats["classifications"]["DEEP_VALUE"] == 1
    assert stats["generational_count"] == 0
    assert "GENERATIONAL = 0" in stats["warning"]
    text = format_dataset_report(stats)
    assert "ATLAS INVESTMENT DATASET" in text
    assert "Not performance" in text
    assert "Do not claim the strategy works" in text
    assert "By sector" in text


def test_rejection_persistence_keeps_blockers():
    rec = _rec(cls=InvestmentAlertState.NO_ACTION, blockers=["valuation not attractive", "drawdown too small"])
    obs = ScanObservation(
        symbol="MSFT".replace("MSFT", "ZZZ"),
        classification="NO_ACTION",
        evaluation=EvaluationStatus.VALID_NO_ACTION.value,
        evaluation_reason="valuation not attractive",
        blocking_reason="valuation not attractive",
        blocking_factors=list(rec.generational_blockers),
        research=rec,
    )
    d = obs.as_dict()
    assert d["evaluation"] == "VALID_NO_ACTION"
    assert d["blocking_factors"]
    assert d["classification"] == "NO_ACTION"


def test_data_health_and_scanner_health_text():
    rec = _rec()
    obs = ScanObservation(
        symbol="XYZ",
        classification="NO_ACTION",
        evaluation=EvaluationStatus.INSUFFICIENT_DATA.value,
        evaluation_reason="fundamental provider unavailable",
        field_quality={"price": "MISSING"},
        research=rec,
        completeness={"label": "4 / 12", "present": 4, "required": 12},
    )
    report = ScanReport(
        scan_id="s",
        universe=10,
        evaluated=1,
        failed=0,
        alerts_emitted=0,
        observations=[obs],
        counts={"NO_ACTION": 1},
    )
    text = format_data_health(report)
    assert "INVESTMENT DATA HEALTH" in text
    assert "INSUFFICIENT_DATA" in text
    assert "VALID_NO_ACTION" in text
    health = format_scanner_health(running=True, last={"universe": 10, "price_coverage": 94.0, "fund_coverage": 61.0, "val_coverage": 58.0})
    assert "ATLAS INVESTMENT HEALTH" in health
    assert "RUNNING" in health
    assert "No real orders: YES" in health
    assert "Trading engine: ISOLATED" in health
    assert "/paper" not in health


def test_phase51_isolation():
    import app.investment.diagnostics as d
    import app.investment.evaluation as e
    import app.investment.dataset as ds

    for mod in (d, e, ds):
        src = Path(inspect.getfile(mod)).read_text(encoding="utf-8")
        assert "perp_micro" not in src
        assert "paper_journal" not in src
        assert not re.search(r"\bRSI\b", src)
        assert "from app.services" not in src
        assert "from app.adapters" not in src
