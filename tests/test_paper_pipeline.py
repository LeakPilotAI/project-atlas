"""Prove paper journal + qualification math + TEST isolation. No live network required."""

from __future__ import annotations

import asyncio
from typing import List

from app.services.paper_journal import PaperJournal
from app.services.paper_pipeline import PaperPipeline
from app.services.perp_micro_coach import PerpMicroCoach, _atr_proxy, _rsi, _sma


def _oversold_closes(n: int = 48) -> List[float]:
    """Deterministic dump that satisfies current RSI<=28 and extension>=1.4%."""
    closes = [100.0] * 20
    px = 100.0
    for i in range(n - 20):
        px *= 0.992
        closes.append(px)
    return closes


def test_rsi_and_extension_fixture_meets_current_thresholds() -> None:
    closes = _oversold_closes()
    price = closes[-1]
    rsi = _rsi(closes, 14)
    sma20 = _sma(closes, 20)
    assert rsi is not None and sma20 is not None
    ext = abs(price - sma20) / sma20 * 100.0
    assert rsi <= 28.0
    assert ext >= 1.4


def test_quality_accepts_major_oversold_dump() -> None:
    closes = _oversold_closes()
    price = closes[-1]
    rsi = _rsi(closes, 14)
    sma20 = _sma(closes, 20)
    assert rsi is not None and sma20 is not None
    ext = abs(price - sma20) / sma20 * 100.0
    coach = PerpMicroCoach()
    coach._vol_map["BTC"] = 8_000_000
    coach._oi_map["BTC"] = 8_000_000
    ok, score, reason = coach._setup_quality(
        "BTC", "LONG", price, closes, rsi, sma20, ext
    )
    assert ok is True
    assert score >= 62.0
    assert "RSI" in reason or "ext" in reason.lower()


def test_rr_geometry_meets_min() -> None:
    closes = _oversold_closes()
    price = closes[-1]
    atr = _atr_proxy(closes, 14)
    stop = price - 1.5 * atr
    risk = abs(price - stop)
    tp1 = price + 1.8 * risk
    rr = abs(tp1 - price) / risk
    assert rr >= 1.8 - 1e-12


def test_paper_journal_test_type_does_not_count(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.paper_journal.JOURNAL_PATH", tmp_path / "paper_journal.jsonl")
    monkeypatch.setattr("app.services.paper_journal.CANDIDATE_PATH", tmp_path / "paper_candidates.jsonl")

    async def _run() -> None:
        j = PaperJournal()
        before = await j.stats()
        tid = await j.open_trade(
            symbol="ATLAS_TEST",
            side="LONG",
            entry=100.0,
            stop=99.0,
            tp1=101.8,
            tp2=103.0,
            counts_for_live=False,
            trade_type="TEST",
            source="diagnostics",
        )
        j.update_excursion(tid, 100.5)
        j.update_excursion(tid, 99.6)
        closed = await j.close_trade(tid, exit_price=101.8, result="TEST_CLOSE")
        after = await j.stats()
        assert tid
        assert closed.get("mfe_r", 0) > 0
        assert closed.get("mae_r", 0) > 0
        assert closed.get("trade_type") == "TEST"
        assert after.get("closed") == before.get("closed")

    asyncio.run(_run())


def test_pipeline_counters_increment() -> None:
    p = PaperPipeline()
    p.reset_cycle()
    p.inc("evaluated")
    p.inc_reject("RSI_NOT_EXTREME")
    p.inc("qualified")
    snap = p.snapshot_cycle()
    assert snap["evaluated"] == 1
    assert snap["qualified"] == 1
    why = p.why_no_trade()
    assert "headline" in why


def test_last_24h_funnel_and_bottleneck(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.paper_pipeline.FUNNEL_PATH", tmp_path / "funnel.jsonl")
    monkeypatch.setattr("app.services.paper_pipeline.DATA_DIR", tmp_path)
    p = PaperPipeline()
    p._window.clear()
    p._cycle.clear()
    p._session.clear()
    p._latest_universe = {"markets": 0, "liquid": 0}

    p.inc("tickers_received", 232)
    p.inc("liquid_set", 78)
    p.inc("evaluated", 78)
    h = p.last_24h()
    assert h["markets"] == 232
    assert h["liquid"] == 78
    assert h["evaluated"] == 78
    assert h["extension_passed"] == 0
    assert h["bottleneck"] == "extension"
    assert "Extension" in p.bottleneck_text(h)

    p.inc("extension_pass", 35)
    h = p.last_24h()
    assert h["bottleneck"] == "rsi"
    assert "RSI" in p.bottleneck_text(h)

    p.inc("rsi_extreme", 20)
    h = p.last_24h()
    assert h["bottleneck"] == "quality"

    p.inc("quality_pass", 8)
    h = p.last_24h()
    assert h["bottleneck"] == "rr"

    p.inc("rr_pass", 6)
    p.inc("qualified", 6)
    p.inc("paper_open_succeeded", 6)
    h = p.last_24h()
    assert h["bottleneck"] == "producing"
    assert h["paper_trades"] == 6
    text = p.funnel_24h_text()
    assert "LAST 24 HOURS" in text
    assert "Markets:" in text
    assert "Liquid:" in text
    assert "Evaluated:" in text
    assert "Extension passed:" in text
    assert "RSI passed:" in text
    assert "Quality passed:" in text
    assert "R:R passed:" in text
    assert "Qualified:" in text
    assert "Paper trades:" in text
    assert "Shadow candidates:" in text
    assert "Bottleneck:" in text


def test_24h_window_does_not_sum_universe(tmp_path, monkeypatch) -> None:
    """Markets/liquid are snapshots, not 24h sums of every cycle."""
    monkeypatch.setattr("app.services.paper_pipeline.FUNNEL_PATH", tmp_path / "funnel.jsonl")
    monkeypatch.setattr("app.services.paper_pipeline.DATA_DIR", tmp_path)
    p = PaperPipeline()
    p._window.clear()
    p._cycle.clear()
    p._latest_universe = {"markets": 0, "liquid": 0}
    p.inc("tickers_received", 232)
    p.inc("liquid_set", 78)
    p.inc("evaluated", 10)
    p.reset_cycle()
    p.inc("tickers_received", 232)
    p.inc("liquid_set", 80)
    p.inc("evaluated", 12)
    h = p.last_24h()
    assert h["markets"] == 232
    assert h["liquid"] == 80
    assert h["evaluated"] == 22
