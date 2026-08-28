"""Outcome collection: MFE/MAE, closes, restart, duplicates, expectancy, drawdown."""

from __future__ import annotations

import asyncio

from app.analytics.regime import RegimeResult, normalize_regime
from app.services.outcome_research import paper_performance
from app.services.paper_journal import PaperJournal
from app.services.shadow_research import ShadowResearch


def test_normalize_regime_buckets() -> None:
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


def test_open_mfe_mae_tp_sl_expire_and_restart(tmp_path, monkeypatch) -> None:
    path = tmp_path / "paper_journal.jsonl"
    monkeypatch.setattr("app.services.paper_journal.JOURNAL_PATH", path)
    monkeypatch.setattr("app.services.paper_journal.CANDIDATE_PATH", tmp_path / "cands.jsonl")

    async def _run() -> None:
        j = PaperJournal()
        tid = await j.open_trade(
            symbol="BTC",
            side="LONG",
            entry=100.0,
            stop=99.0,
            tp1=101.8,
            tp2=103.0,
            features={"regime_normalized": "TREND_DOWN"},
            regime="TREND_DOWN",
        )
        assert j._open[tid]["actual_entry_price"] == 100.0
        assert j._open[tid]["signal_price"] == 100.0
        j.update_excursion(tid, 101.0)  # +1R MFE
        j.update_excursion(tid, 99.4)  # 0.6R MAE
        assert j._open[tid]["mfe_r"] >= 0.99
        assert j._open[tid]["mae_r"] >= 0.59

        j2 = PaperJournal()
        assert tid in j2._open
        assert j2._open[tid]["mfe_r"] >= 0.99
        assert j2._open[tid]["mae_r"] >= 0.59

        closed = await j2.close_trade(tid, exit_price=101.8, result="TP1")
        assert closed["win"] is True
        assert closed["reached_1r"] is True
        assert closed["reached_1_8r"] is True
        assert closed["mfe_r"] >= 1.0
        again = await j2.close_trade(tid, exit_price=90.0, result="STOP")
        assert again.get("result") == "TP1"
        assert again.get("actual_exit_price") == 101.8

        tid_sl = await j.open_trade(
            symbol="ETH",
            side="LONG",
            entry=100.0,
            stop=99.0,
            tp1=101.8,
            tp2=103.0,
        )
        sl = await j.close_trade(tid_sl, exit_price=99.0, result="STOP", pnl_r=-1.0)
        assert sl["win"] is False
        assert sl["R_multiple"] == -1.0

        tid_ex = await j.open_trade(
            symbol="SOL",
            side="SHORT",
            entry=10.0,
            stop=10.2,
            tp1=9.64,
            tp2=9.4,
        )
        ex = await j.close_trade(tid_ex, exit_price=10.05, result="EXPIRE")
        assert ex["exit_reason"] == "EXPIRE"

        dup = await j.open_trade(
            symbol="SOL",
            side="SHORT",
            entry=11.0,
            stop=11.2,
            tp1=10.6,
            tp2=10.4,
        )
        assert dup == tid_ex or dup != tid_ex  # expire closed SOL, new open allowed
        # SOL short was closed, so a new open is a new id
        assert dup != tid_ex

    asyncio.get_event_loop().run_until_complete(_run())


def test_duplicate_open_same_symbol_side(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.paper_journal.JOURNAL_PATH", tmp_path / "j.jsonl")
    monkeypatch.setattr("app.services.paper_journal.CANDIDATE_PATH", tmp_path / "c.jsonl")

    async def _run() -> None:
        j = PaperJournal()
        a = await j.open_trade(symbol="XRP", side="LONG", entry=1.0, stop=0.9, tp1=1.18, tp2=1.3)
        b = await j.open_trade(symbol="XRP", side="LONG", entry=1.05, stop=0.95, tp1=1.23, tp2=1.4)
        assert a == b
        assert j._open[a]["actual_entry_price"] == 1.0

    asyncio.get_event_loop().run_until_complete(_run())


def test_test_trades_excluded_from_performance(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.paper_journal.JOURNAL_PATH", tmp_path / "j.jsonl")
    monkeypatch.setattr("app.services.paper_journal.CANDIDATE_PATH", tmp_path / "c.jsonl")

    async def _run() -> None:
        j = PaperJournal()
        tid = await j.open_trade(
            symbol="ATLAS_TEST",
            side="LONG",
            entry=100.0,
            stop=99.0,
            tp1=101.8,
            tp2=103.0,
            trade_type="TEST",
        )
        await j.close_trade(tid, exit_price=101.8, result="TEST_CLOSE")
        from app.services.outcome_research import load_paper_closes

        rows = load_paper_closes(tmp_path / "j.jsonl")
        assert rows == []
        stats = await j.stats()
        assert stats["closed"] == 0

    asyncio.get_event_loop().run_until_complete(_run())


def test_expectancy_drawdown_side_regime(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.paper_journal.JOURNAL_PATH", tmp_path / "j.jsonl")
    monkeypatch.setattr("app.services.paper_journal.CANDIDATE_PATH", tmp_path / "c.jsonl")

    async def _run() -> None:
        j = PaperJournal()
        t1 = await j.open_trade(
            symbol="BTC",
            side="LONG",
            entry=100.0,
            stop=99.0,
            tp1=101.8,
            tp2=103.0,
            features={"regime_normalized": "TREND_DOWN"},
            regime="TREND_DOWN",
        )
        j.update_excursion(t1, 101.8)
        await j.close_trade(t1, exit_price=101.8, result="TP1")
        t2 = await j.open_trade(
            symbol="ETH",
            side="SHORT",
            entry=10.0,
            stop=10.2,
            tp1=9.64,
            tp2=9.4,
            features={"regime_normalized": "RANGE"},
            regime="RANGE",
        )
        await j.close_trade(t2, exit_price=10.2, result="STOP", pnl_r=-1.0)
        from app.services.outcome_research import load_paper_closes, paper_performance

        rows = load_paper_closes(tmp_path / "j.jsonl")
        perf = paper_performance(rows)
        assert perf["n"] == 2
        assert perf["wins"] == 1
        assert perf["losses"] == 1
        assert perf["winrate"] == 0.5
        assert perf["expectancy"] == perf["avg_r"]
        assert perf["max_drawdown_r"] >= 0
        assert perf["longest_losing_streak"] >= 1
        assert perf["by_side"]["LONG"]["n"] == 1
        assert perf["by_side"]["SHORT"]["n"] == 1
        assert "TREND_DOWN" in perf["by_regime"] or "RANGE" in perf["by_regime"]

    asyncio.get_event_loop().run_until_complete(_run())


def test_shadow_resolution_fields(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.shadow_research.CANDIDATES_PATH", tmp_path / "s.jsonl")
    monkeypatch.setattr("app.services.shadow_research.EVENTS_PATH", tmp_path / "e.jsonl")
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
    assert row["trade_type"] == "SHADOW"
    resolved = s.update_prices({"BTC": 102.5})
    assert resolved[0]["tp_would_have_been_reached"] is True
    assert resolved[0]["time_to_tp_sec"] is not None
    assert resolved[0]["hypothetical_final_r"] > 0
    assert resolved[0]["trade_type"] == "SHADOW"
    stats = s.funnel_stats(24)
    assert stats["resolved"] >= 1
    assert stats["shadow_wins"] >= 1
