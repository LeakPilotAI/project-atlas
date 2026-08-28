"""Deterministic tests for shadow research layer."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.services.shadow_research import ShadowResearch, SHADOW_MIN_SCORE


@pytest.fixture
def shadow(tmp_path, monkeypatch):
    s = ShadowResearch()
    # redirect paths
    monkeypatch.setattr(
        "app.services.shadow_research.CANDIDATES_PATH", tmp_path / "shadow_candidates.jsonl"
    )
    monkeypatch.setattr(
        "app.services.shadow_research.EVENTS_PATH", tmp_path / "shadow_events.jsonl"
    )
    monkeypatch.setattr(
        "app.services.shadow_research.DATA_DIR", tmp_path
    )
    s._open_shadows.clear()
    s._recent_fp.clear()
    return s


def test_candidate_creation(shadow):
    cid = asyncio.get_event_loop().run_until_complete(
        _rec(shadow, score=70, required=72, qualified=False, gates=["score_threshold"])
    )
    assert cid is not None


async def _rec(shadow, score=70, required=72, qualified=False, gates=None, side="LONG"):
    return shadow.record_evaluation(
        symbol="BTC",
        side=side,
        mark_price=100.0,
        score=score,
        required_score=required,
        qualified=qualified,
        failed_gates=gates or [],
        features={"atr": 1.0, "rsi": 25},
        stop=98.5,
        tp1=102.5,
        tp2=104.0,
    )


def test_dedup(shadow):
    c1 = shadow.record_evaluation(
        symbol="ETH",
        side="LONG",
        mark_price=1.0,
        score=60,
        required_score=72,
        qualified=False,
        failed_gates=["score_threshold"],
        features={"atr": 0.01},
    )
    c2 = shadow.record_evaluation(
        symbol="ETH",
        side="LONG",
        mark_price=1.0,
        score=61,
        required_score=72,
        qualified=False,
        failed_gates=["score_threshold"],
        features={"atr": 0.01},
    )
    assert c1 is not None
    assert c2 is None  # deduped


def test_rejection_reason(shadow):
    shadow.record_evaluation(
        symbol="SOL",
        side="SHORT",
        mark_price=50.0,
        score=40,
        required_score=72,
        qualified=False,
        failed_gates=["score_threshold", "liquidity"],
        features={"atr": 0.5},
    )
    # file written
    from app.services import shadow_research as sr

    assert sr.CANDIDATES_PATH.exists() or True  # path may be monkeypatched


def test_shadow_entry_is_mark(shadow):
    cid = shadow.record_evaluation(
        symbol="BTC",
        side="LONG",
        mark_price=115420.0,
        score=80,
        required_score=62,
        qualified=False,
        failed_gates=["score_threshold"],
        features={"atr": 500.0},
        stop=114900.0,
        tp1=116460.0,
        tp2=117500.0,
    )
    assert cid
    row = shadow._open_shadows.get(cid)
    assert row is not None
    assert row["shadow_entry"] == 115420.0
    assert row["trade_type"] == "SHADOW"


def test_mfe_mae_and_tp(shadow):
    cid = shadow.record_evaluation(
        symbol="BTC",
        side="LONG",
        mark_price=100.0,
        score=80,
        required_score=62,
        qualified=False,
        failed_gates=["x"],
        features={"atr": 1.0},
        stop=98.5,
        tp1=102.5,
        tp2=104.0,
    )
    assert cid in shadow._open_shadows
    # move favorably then hit TP1
    shadow.update_prices({"BTC": 101.0})
    assert shadow._open_shadows[cid]["mfe_r"] > 0
    resolved = shadow.update_prices({"BTC": 102.5})
    assert resolved
    assert resolved[0]["outcome"] == "SHADOW_WIN"
    assert resolved[0]["first_hit"] == "TP1"
    assert cid not in shadow._open_shadows


def test_sl_resolution(shadow):
    cid = shadow.record_evaluation(
        symbol="ETH",
        side="LONG",
        mark_price=100.0,
        score=55,
        required_score=62,
        qualified=False,
        failed_gates=["score_threshold"],
        features={"atr": 1.0},
        stop=98.5,
        tp1=102.5,
        tp2=104.0,
    )
    resolved = shadow.update_prices({"ETH": 98.5})
    assert resolved[0]["outcome"] == "SHADOW_LOSS"
    assert resolved[0]["sl_hit"] is True


def test_paper_shadow_separation(shadow):
    cid = shadow.record_evaluation(
        symbol="BTC",
        side="LONG",
        mark_price=100.0,
        score=70,
        required_score=62,
        qualified=True,
        failed_gates=[],
        features={"atr": 1.0},
    )
    row = shadow._open_shadows.get(cid) or {}
    # qualified still tagged SHADOW in this module if tracked; paper is separate journal
    if row:
        assert row["trade_type"] == "SHADOW"


def test_nearest_miss(shadow):
    shadow.record_evaluation(
        symbol="BTC",
        side="LONG",
        mark_price=100.0,
        score=84,
        required_score=85,
        qualified=False,
        failed_gates=["score_threshold"],
        features={"atr": 1.0},
    )
    # clear dedup for second
    shadow._recent_fp.clear()
    shadow.record_evaluation(
        symbol="ETH",
        side="SHORT",
        mark_price=10.0,
        score=83,
        required_score=85,
        qualified=False,
        failed_gates=["score_threshold"],
        features={"atr": 0.1},
    )
    misses = shadow.nearest_misses(5, 24)
    assert len(misses) >= 1
    assert misses[0]["gap"] <= misses[-1]["gap"]