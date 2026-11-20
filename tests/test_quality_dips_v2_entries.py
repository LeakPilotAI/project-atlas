from copy import deepcopy

import pytest

from app.investment.quality_dips_v2_entries import (
    LEVEL_HURDLES,
    build_entry_ladder,
    freeze_entry_snapshot,
)


def test_requires_complete_valuation_window():
    out = build_entry_ladder(
        symbol="MSFT",
        normalization_value={"conservative": 500.0},
        valuation_window_complete=False,
        current_price=350.0,
    )
    assert out["ready"] is False
    assert out["levels"] == []
    assert out["execution"] == "MANUAL_ONLY"
    assert out["live_capital_allowed"] is False
    assert out["automatic_real_money_execution"] is False


def test_builds_four_patient_levels_from_conservative_value():
    out = build_entry_ladder(
        symbol="MSFT",
        normalization_value={"conservative": 500.0, "base": 550.0, "optimistic": 650.0},
        valuation_window_complete=True,
        current_price=360.0,
    )
    assert out["ready"] is True
    assert [row["level"] for row in out["levels"]] == ["L1", "L2", "L3", "L4"]
    assert [row["required_upside_pct"] for row in out["levels"]] == [29.0, 35.0, 40.0, 50.0]
    assert out["levels"][0]["limit_price"] == pytest.approx(387.6, abs=0.01)
    assert out["levels"][1]["limit_price"] == pytest.approx(370.37, abs=0.01)
    assert out["levels"][2]["limit_price"] == pytest.approx(357.14, abs=0.01)
    assert out["levels"][3]["limit_price"] == pytest.approx(333.33, abs=0.01)


def test_deeper_levels_are_lower_prices():
    out = build_entry_ladder(
        symbol="AAPL",
        normalization_value={"conservative": 300.0},
        valuation_window_complete=True,
    )
    prices = [row["limit_price"] for row in out["levels"]]
    assert prices == sorted(prices, reverse=True)


def test_reached_flags_use_current_price_without_placing_orders():
    out = build_entry_ladder(
        symbol="NVDA",
        normalization_value={"conservative": 150.0},
        valuation_window_complete=True,
        current_price=105.0,
    )
    reached = {row["level"]: row["reached"] for row in out["levels"]}
    assert reached["L1"] is True
    assert reached["L2"] is True
    assert reached["L3"] is True
    assert reached["L4"] is False
    assert out["execution"] == "MANUAL_ONLY"


def test_freeze_entry_snapshot_preserves_point_in_time_evidence():
    evidence = {
        "patient_state": "DEEP_VALUE",
        "trend": {"long_term": "UP", "short_term": "DOWN"},
        "normalization_value": {"conservative": 500.0},
    }
    original = deepcopy(evidence)
    snap = freeze_entry_snapshot(
        symbol="MSFT",
        level="L3",
        entry_price=350.0,
        evidence=evidence,
        recorded_at="2026-09-17T12:00:00+00:00",
    )
    evidence["trend"]["long_term"] = "DOWN"
    assert snap["evidence_snapshot"] == original
    assert snap["level"] == "L3"
    assert snap["required_upside_pct_at_level"] == LEVEL_HURDLES["L3"]
    assert snap["execution"] == "MANUAL_ONLY"
    assert snap["automatic_real_money_execution"] is False


def test_snapshot_rejects_invalid_level():
    with pytest.raises(ValueError):
        freeze_entry_snapshot(symbol="MSFT", level="L5", entry_price=100.0, evidence={})


def test_snapshot_rejects_nonpositive_price():
    with pytest.raises(ValueError):
        freeze_entry_snapshot(symbol="MSFT", level="L1", entry_price=0.0, evidence={})
