"""Deterministic tests for funnel research layer. Production gates stay locked."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.analytics.regime import RegimeResult, normalize_regime
from app.services.funnel_research import (
    EXT_LOCK,
    RR_LOCK,
    RSI_LONG_LOCK,
    RSI_SHORT_LOCK,
    FunnelResearch,
    _percentile,
    _stats,
)
from app.services.paper_pipeline import PaperPipeline
from app.services.perp_micro_coach import _atr_proxy, _rsi, _sma
from app.services.shadow_research import ShadowResearch


def test_locked_thresholds_unchanged() -> None:
    assert RSI_LONG_LOCK == 28.0
    assert RSI_SHORT_LOCK == 72.0
    assert EXT_LOCK == 1.4
    assert RR_LOCK == 1.8


def test_percentile_and_stats() -> None:
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert _percentile(xs, 0) == 1.0
    assert _percentile(xs, 100) == 5.0
    assert _percentile(xs, 50) == 3.0
    st = _stats(xs)
    assert st["n"] == 5
    assert st["min"] == 1.0
    assert st["max"] == 5.0
    assert st["mean"] == 3.0
    empty = _stats([])
    assert empty["n"] == 0
    assert empty["p95"] is None


def test_normalize_regime() -> None:
    assert normalize_regime("trend_up") == "TREND_UP"
    assert normalize_regime("trend_down") == "TREND_DOWN"
    assert normalize_regime("range") == "RANGE"
    assert normalize_regime("expansion") == "HIGH_VOLATILITY"
    assert normalize_regime(None) == "UNKNOWN"
    r = RegimeResult(
        name="range",
        strength=10,
        vol_state="low",
        efficiency=0.1,
        slope_fast=0.0,
        slope_slow=0.0,
    )
    assert normalize_regime(r) == "LOW_VOLATILITY"
    r2 = RegimeResult(
        name="trend_up",
        strength=50,
        vol_state="high",
        efficiency=0.5,
        slope_fast=1.0,
        slope_slow=1.0,
    )
    assert normalize_regime(r2) == "HIGH_VOLATILITY"


def test_independent_gates_vs_sequential(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.funnel_research.RESEARCH_PATH", tmp_path / "funnel_research.jsonl")
    monkeypatch.setattr("app.services.funnel_research.DATA_DIR", tmp_path)
    fr = FunnelResearch()
    fr._rows.clear()

    # Sequential would die at extension (0.5% < 1.4) but RSI is independently oversold.
    fr.observe(
        symbol="AAA",
        price=100.0,
        ext_pct=0.5,
        rsi=22.0,
        quality_score=40.0,
        quality_min=62.0,
        rr=1.8,
        atr=1.0,
        regime="TREND_DOWN",
        side_hyp="LONG",
        sequential_stage="extension",
    )
    # Sequential would die at RSI (ext passes, RSI 50).
    fr.observe(
        symbol="BBB",
        price=100.0,
        ext_pct=2.0,
        rsi=50.0,
        quality_score=30.0,
        quality_min=62.0,
        rr=1.8,
        atr=1.0,
        regime="RANGE",
        side_hyp="LONG",
        sequential_stage="rsi",
    )
    g = fr.independent_gates()
    assert g["n"] == 2
    assert g["extension_ge_1_4"]["count"] == 1  # only BBB
    assert g["rsi_long_le_28"]["count"] == 1  # only AAA
    assert g["rr_ge_1_8"]["count"] == 2
    # Same counts can still be different markets: sequential never sees AAA's RSI.


def test_funnel_counters_and_bottleneck(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.paper_pipeline.FUNNEL_PATH", tmp_path / "funnel.jsonl")
    monkeypatch.setattr("app.services.paper_pipeline.DATA_DIR", tmp_path)
    p = PaperPipeline()
    p._window.clear()
    p._cycle.clear()
    p._session.clear()
    p.inc("tickers_received", 232)
    p.inc("liquid_set", 77)
    p.inc("evaluated", 77)
    p.inc("candle_success", 77)
    p.inc("extension_evaluated", 77)
    p.inc("rsi_evaluated", 77)
    h = p.last_24h()
    assert h["evaluated"] == 77
    assert h["extension_passed"] == 0
    assert h["bottleneck"] == "extension"
    assert "pct" in h
    text = p.funnel_24h_text()
    assert "%" in text


def test_sensitivity_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.funnel_research.RESEARCH_PATH", tmp_path / "funnel_research.jsonl")
    monkeypatch.setattr("app.services.funnel_research.DATA_DIR", tmp_path)
    fr = FunnelResearch()
    fr._rows.clear()
    for ext in (0.4, 0.8, 1.1, 1.4, 2.1):
        fr.observe(
            symbol="X",
            price=10.0,
            ext_pct=ext,
            rsi=40.0,
            quality_score=10.0,
            quality_min=62.0,
            rr=1.8,
            atr=0.1,
        )
    sens = fr.sensitivity()
    assert sens["n"] == 5
    assert sens["extension"]["0.5"]["count"] == 4
    assert sens["extension"]["1.4"]["count"] == 2
    assert sens["locked_production"]["extension"] == 1.4
    assert sens["locked_production"]["rsi_long"] == 28.0


def test_distributions(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.funnel_research.RESEARCH_PATH", tmp_path / "funnel_research.jsonl")
    monkeypatch.setattr("app.services.funnel_research.DATA_DIR", tmp_path)
    fr = FunnelResearch()
    fr._rows.clear()
    for i, rsi in enumerate((10.0, 25.0, 50.0, 75.0, 90.0)):
        fr.observe(
            symbol=f"S{i}",
            price=1.0,
            ext_pct=float(i),
            rsi=rsi,
            quality_score=float(i * 10),
            quality_min=62.0,
            rr=1.8,
            atr=0.01,
        )
    d = fr.distributions()
    assert d["rsi"]["n"] == 5
    assert d["rsi"]["min"] == 10.0
    assert d["rsi"]["max"] == 90.0
    assert d["rsi"]["p5"] is not None
    assert d["extension"]["p95"] is not None
    assert d["quality"]["p95"] is not None
    assert d["rr"]["median"] == 1.8


def test_persistence_and_restart(tmp_path, monkeypatch) -> None:
    path = tmp_path / "funnel_research.jsonl"
    monkeypatch.setattr("app.services.funnel_research.RESEARCH_PATH", path)
    monkeypatch.setattr("app.services.funnel_research.DATA_DIR", tmp_path)
    a = FunnelResearch()
    a._rows.clear()
    a.observe(
        symbol="BTC",
        price=100.0,
        ext_pct=2.0,
        rsi=20.0,
        quality_score=70.0,
        quality_min=62.0,
        rr=1.8,
        atr=1.0,
        regime="TREND_DOWN",
    )
    assert path.exists()
    b = FunnelResearch()
    assert len(b._window_rows()) >= 1
    assert b.independent_gates()["n"] >= 1
    assert b.independent_gates()["rsi_long_le_28"]["count"] >= 1


def test_bottleneck_extension_text(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.funnel_research.RESEARCH_PATH", tmp_path / "fr.jsonl")
    monkeypatch.setattr("app.services.funnel_research.DATA_DIR", tmp_path)
    monkeypatch.setattr("app.services.paper_pipeline.FUNNEL_PATH", tmp_path / "funnel.jsonl")
    monkeypatch.setattr("app.services.paper_pipeline.DATA_DIR", tmp_path)
    from app.services import paper_pipeline as pp_mod

    p = PaperPipeline()
    p._window.clear()
    p._cycle.clear()
    p.inc("evaluated", 77)
    p.inc("candle_success", 77)
    p.inc("extension_passed", 0)
    monkeypatch.setattr(pp_mod, "paper_pipeline", p)
    fr = FunnelResearch()
    fr._rows.clear()
    why = fr.why_no_paper_trades()
    assert why["bottleneck"] == "EXTENSION"
    assert "1.4" in why["reason"]
    diag = fr.diagnostics_text()
    assert "WHY ARE THERE NO PAPER TRADES" in diag
    assert "EXTENSION" in diag


def test_bottleneck_quality(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.paper_pipeline.FUNNEL_PATH", tmp_path / "funnel.jsonl")
    monkeypatch.setattr("app.services.paper_pipeline.DATA_DIR", tmp_path)
    monkeypatch.setattr("app.services.funnel_research.RESEARCH_PATH", tmp_path / "fr.jsonl")
    from app.services import paper_pipeline as pp_mod

    p = PaperPipeline()
    p._window.clear()
    p._cycle.clear()
    p.inc("evaluated", 12)
    p.inc("candle_success", 12)
    p.inc("extension_pass", 12)
    p.inc("rsi_extreme", 12)
    p.inc("quality_pass", 0)
    monkeypatch.setattr(pp_mod, "paper_pipeline", p)
    fr = FunnelResearch()
    why = fr.why_no_paper_trades()
    assert why["bottleneck"] == "QUALITY"


def test_bottleneck_paper_execution(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.paper_pipeline.FUNNEL_PATH", tmp_path / "funnel.jsonl")
    monkeypatch.setattr("app.services.paper_pipeline.DATA_DIR", tmp_path)
    monkeypatch.setattr("app.services.funnel_research.RESEARCH_PATH", tmp_path / "fr.jsonl")
    from app.services import paper_pipeline as pp_mod

    p = PaperPipeline()
    p._window.clear()
    p._cycle.clear()
    p.inc("evaluated", 8)
    p.inc("candle_success", 8)
    p.inc("extension_pass", 8)
    p.inc("rsi_extreme", 8)
    p.inc("quality_pass", 8)
    p.inc("rr_pass", 8)
    p.inc("qualified", 8)
    p.inc("paper_open_attempted", 8)
    p.inc("paper_open_succeeded", 0)
    monkeypatch.setattr(pp_mod, "paper_pipeline", p)
    fr = FunnelResearch()
    why = fr.why_no_paper_trades()
    assert why["bottleneck"] == "PAPER_EXECUTION"


def test_rsi_extension_quality_rr_helpers() -> None:
    closes = [100.0] * 20
    px = 100.0
    for _ in range(28):
        px *= 0.992
        closes.append(px)
    rsi = _rsi(closes, 14)
    sma = _sma(closes, 20)
    assert rsi is not None and sma is not None
    ext = abs(closes[-1] - sma) / sma * 100.0
    assert rsi <= 28.0
    assert ext >= 1.4
    atr = _atr_proxy(closes, 14)
    risk = 1.5 * atr
    rr = (1.8 * risk) / risk
    assert rr >= 1.8 - 1e-12


def test_shadow_time_to_tp(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.shadow_research.CANDIDATES_PATH", tmp_path / "shadow_candidates.jsonl")
    monkeypatch.setattr("app.services.shadow_research.EVENTS_PATH", tmp_path / "shadow_events.jsonl")
    monkeypatch.setattr("app.services.shadow_research.DATA_DIR", tmp_path)
    s = ShadowResearch()
    s._open_shadows.clear()
    s._recent_fp.clear()
    cid = s.record_evaluation(
        symbol="BTC",
        side="LONG",
        mark_price=100.0,
        score=80,
        required_score=62,
        qualified=False,
        failed_gates=["score_threshold"],
        features={"atr": 1.0, "rsi": 22, "ext_pct": 2.0},
        stop=98.5,
        tp1=102.5,
        tp2=104.0,
        rejection_stage="quality",
        regime_normalized="TREND_DOWN",
    )
    assert cid
    row = s._open_shadows[cid]
    assert row["regime_normalized"] == "TREND_DOWN"
    assert row["rejection_stage"] == "quality"
    resolved = s.update_prices({"BTC": 102.5})
    assert resolved[0]["tp_would_have_been_reached"] is True
    assert resolved[0]["time_to_tp_sec"] is not None
    assert resolved[0]["hypothetical_final_r"] > 0
    assert resolved[0]["trade_type"] == "SHADOW"


def test_paper_shadow_not_mixed(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.shadow_research.CANDIDATES_PATH", tmp_path / "s.jsonl")
    monkeypatch.setattr("app.services.shadow_research.EVENTS_PATH", tmp_path / "e.jsonl")
    monkeypatch.setattr("app.services.shadow_research.DATA_DIR", tmp_path)
    s = ShadowResearch()
    s._open_shadows.clear()
    s._recent_fp.clear()
    cid = s.record_evaluation(
        symbol="ETH",
        side="LONG",
        mark_price=10.0,
        score=70,
        required_score=62,
        qualified=True,
        failed_gates=[],
        features={"atr": 0.1},
    )
    row = s._open_shadows.get(cid) or {}
    assert row.get("trade_type") == "SHADOW"
    stats = s.funnel_stats(24)
    assert "shadow_wins" in stats
    assert "pipeline_24h" in stats


def test_research_summary_contains_required_blocks(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.funnel_research.RESEARCH_PATH", tmp_path / "fr.jsonl")
    monkeypatch.setattr("app.services.funnel_research.DATA_DIR", tmp_path)
    monkeypatch.setattr("app.services.paper_pipeline.FUNNEL_PATH", tmp_path / "funnel.jsonl")
    monkeypatch.setattr("app.services.paper_pipeline.DATA_DIR", tmp_path)
    fr = FunnelResearch()
    fr._rows.clear()
    fr.observe(
        symbol="SOL",
        price=20.0,
        ext_pct=0.2,
        rsi=45.0,
        quality_score=10.0,
        quality_min=62.0,
        rr=1.8,
        atr=0.2,
    )
    text = fr.research_summary_text()
    assert "ATLAS RESEARCH" in text
    assert "24H FUNNEL" in text
    assert "BOTTLENECK" in text
    assert "FEATURE DISTRIBUTIONS" in text
    assert "SHADOW PERFORMANCE" in text
    assert "INDEPENDENT GATES" in text
