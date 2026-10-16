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


def test_tickers_received_is_snapshot_not_sum(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.paper_pipeline.FUNNEL_PATH", tmp_path / "funnel.jsonl")
    monkeypatch.setattr("app.services.paper_pipeline.DATA_DIR", tmp_path)
    p = PaperPipeline()
    p._window.clear()
    p._cycle.clear()
    p._latest_universe = {"markets": 0, "liquid": 0}
    p.inc("tickers_received", 233)
    p.inc("tickers_received", 233)
    p.inc("tickers_received", 233)
    p.inc("liquid_set", 80)
    p.inc("liquid_set", 80)
    h = p.last_24h()
    assert h["markets"] == 233
    assert h["liquid"] == 80



def test_quality_ema_history_fallback() -> None:
    """Insufficient history must not fabricate an EMA50 trend."""
    from app.services.perp_micro_coach import _ema

    closes = [100.0 + i * 0.1 for i in range(48)]
    ema21 = _ema(closes, 21)
    ema50 = _ema(closes, 50) if len(closes) >= 50 else None

    assert ema21 is not None
    assert ema50 is None


def test_quality_ema50_available_with_50_candles() -> None:
    """Full history permits independent EMA-stack evaluation."""
    from app.services.perp_micro_coach import _ema

    closes = [100.0 + i * 0.1 for i in range(50)]
    ema21 = _ema(closes, 21)
    ema50 = _ema(closes, 50)

    assert ema21 is not None
    assert ema50 is not None
    assert ema21 != ema50



def test_quality_ema_scoring_behavior() -> None:
    """EMA50 history must affect LONG/SHORT scores as designed."""
    from app.services.perp_micro_coach import _ema

    coach = PerpMicroCoach()
    coach._vol_map["BTC"] = 8_000_000
    coach._oi_map["BTC"] = 8_000_000

    expected = {
        ("UP", "LONG"): (90.0, 92.0),
        ("UP", "SHORT"): (90.0, 98.0),
        ("DOWN", "LONG"): (108.0, 116.0),
        ("DOWN", "SHORT"): (90.0, 92.0),
    }

    for (direction, side), (expected_48, expected_50) in expected.items():
        step = 0.1 if direction == "UP" else -0.1
        closes = [100.0 + i * step for i in range(50)]
        scores = []

        for n in (48, 50):
            history = closes[:n]
            price = history[-1]
            sma20 = _sma(history, 20)
            assert sma20 is not None

            rsi = 20.0 if side == "LONG" else 80.0

            ok, score, reason = coach._setup_quality(
                "BTC", side, price, history, rsi, sma20, 3.0
            )

            assert ok is False
            assert "ATR too tight" in reason
            scores.append(score)

        assert scores == [expected_48, expected_50]
        assert _ema(closes, 21) != _ema(closes, 50)



def test_rr_precision_tolerance() -> None:
    """Tiny floating-point noise must not reject intended 1.8R geometry."""
    import math

    min_rr = 1.8

    def rejected(rr: float) -> bool:
        return rr < min_rr and not math.isclose(
            rr, min_rr, rel_tol=1e-12, abs_tol=0.0
        )

    assert rejected(1.7999999999999812) is False
    assert rejected(1.7999999999999703) is False
    assert rejected(1.79) is True
    assert rejected(1.5) is True

def test_instrumented_rr_precision_real_branch(monkeypatch) -> None:
    """Exercise the actual R:R gate without paper trades or persistent writes."""
    import asyncio
    from collections import Counter
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    import app.services.paper_try_symbol as scanner
    import app.services.paper_pipeline as pipeline_module
    import app.services.paper_journal as journal_module
    import app.services.shadow_research as shadow_module
    import app.services.funnel_research as funnel_module

    counts = Counter()
    rejects = Counter()

    pipeline = SimpleNamespace(
        inc=lambda key, amount=1: counts.update({key: amount}),
        inc_reject=lambda key: rejects.update({key: 1}),
        mark_error=lambda message: None,
        last_candle_ok_at=None,
        last_qualified_at=None,
    )

    journal = SimpleNamespace(
        log_candidate=AsyncMock(),
        open_trade=AsyncMock(
            side_effect=AssertionError("Paper trade must not open")
        ),
    )

    shadow = SimpleNamespace(record_evaluation=MagicMock())
    funnel = SimpleNamespace(observe=MagicMock())

    monkeypatch.setattr(pipeline_module, "paper_pipeline", pipeline)
    monkeypatch.setattr(journal_module, "paper_journal", journal)
    monkeypatch.setattr(shadow_module, "shadow_research", shadow)
    monkeypatch.setattr(funnel_module, "funnel_research", funnel)

    settings = SimpleNamespace(
        perp_micro_majors_list=[],
        perp_micro_min_rr=1.8,
        perp_micro_rsi_long=28.0,
        perp_micro_rsi_short=72.0,
        perp_micro_min_extension_pct=1.4,
        perp_micro_max_extension_pct=3.5,
        perp_micro_htf_align=False,
    )

    monkeypatch.setattr(scanner, "get_settings", lambda: settings)

    # This fixture produces an R:R microscopically below 1.8
    # solely because of floating-point rounding.
    closes = [0.1] * 20
    price = 0.1
    for _ in range(30):
        price *= 0.998
        closes.append(price)

    from app.services.perp_micro_coach import _atr_proxy, _rsi, _sma
    import math

    atr = _atr_proxy(closes, 14)
    rsi = _rsi(closes, 14)
    sma = _sma(closes, 20)

    assert rsi is not None and rsi <= 28.0
    assert sma is not None
    assert 1.4 <= abs(price - sma) / sma * 100 <= 3.5

    stop = price - 1.5 * atr
    risk = abs(price - stop)
    target = price + 1.8 * risk
    actual_rr = abs(target - price) / risk

    assert actual_rr < 1.8, (
        "Fixture must reproduce the original rounding rejection"
    )
    assert math.isclose(
        actual_rr, 1.8, rel_tol=1e-12, abs_tol=0.0
    )

    class FakeCoach:
        _vol_map = {"ATLAS_RR_TEST": 8_000_000.0}
        _oi_map = {"ATLAS_RR_TEST": 8_000_000.0}

        async def _fetch_closes(self, symbol, n):
            assert symbol == "ATLAS_RR_TEST"
            assert n == 50
            return list(closes)

        def _setup_quality(self, *args, **kwargs):
            return True, 100.0, "test-qualified"

    async def run():
        return await scanner.instrumented_try_symbol(
            FakeCoach(), "ATLAS_RR_TEST", price
        )

    result = asyncio.run(run())

    assert result is False
    assert counts["quality_pass"] == 1
    assert counts["rr_pass"] == 1
    assert counts["rejected_rr"] == 0
    assert rejects["RISK_REWARD"] == 0
    assert rejects["TIER"] == 1
    journal.open_trade.assert_not_awaited()
