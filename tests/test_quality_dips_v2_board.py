from __future__ import annotations

from datetime import datetime, timezone

from app.investment.quality_dips_v2_board import attach_v2_board, build_v2_projection


def _row() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "symbol": "TEST",
        "timestamp": now,
        "price": 90.0,
        "research_price": 90.0,
        "classification": "ACCUMULATION",
        "opportunity_score": 88,
        "evidence_quality": "HIGH",
        "thesis": "INTACT",
        "components": {"quality": 92, "fundamentals": 90, "valuation": 91},
        "drawdown": {"percentile": 96},
        "trend": {
            "short_term": "DOWN",
            "intermediate_term": "MIXED",
            "long_term": "UP",
            "momentum": "WEAK",
            "relative_strength": "MIXED",
            "as_of": now,
            "source": "TEST",
        },
        "valuation_sources": [
            {"value": 130, "provenance": "DCF", "as_of": now},
            {"value": 140, "provenance": "HISTORICAL_MULTIPLE", "as_of": now},
            {"value": 150, "provenance": "OWNER_EARNINGS", "as_of": now},
        ],
    }


def test_v2_projection_exposes_patient_fields_without_live_execution():
    out = build_v2_projection(_row())
    assert out["symbol"] == "TEST"
    assert out["patient_state"] in {"ACCUMULATION", "DEEP_VALUE", "GENERATIONAL", "WATCH"}
    assert out["normalization_value"]["conservative"] == 130.0
    assert out["entry_ladder"]["ready"] is True
    assert [x["level"] for x in out["entry_ladder"]["levels"]] == ["L1", "L2", "L3", "L4"]
    assert out["execution"] == "MANUAL_ONLY"
    assert out["live_capital_allowed"] is False
    assert out["automatic_real_money_execution"] is False


def test_attach_v2_board_preserves_legacy_fields():
    legacy = [{"symbol": "TEST", "stance": "ACCUMULATE", "opportunity_score": 88}]
    out = attach_v2_board(legacy, [_row()])
    assert out[0]["stance"] == "ACCUMULATE"
    assert out[0]["opportunity_score"] == 88
    assert out[0]["quality_dips_v2"]["symbol"] == "TEST"


def test_attach_v2_board_fails_closed_when_source_missing():
    out = attach_v2_board([{"symbol": "MISS", "stance": "WATCH"}], [])
    v2 = out[0]["quality_dips_v2"]
    assert v2["patient_state"] == "WATCH"
    assert v2["evidence_gate"]["status"] == "BLOCKED"
    assert v2["live_capital_allowed"] is False


def test_projection_surfaces_trend_for_future_active_position_display():
    out = build_v2_projection(_row())
    assert out["trend"]["short_term"] == "DOWN"
    assert out["trend"]["long_term"] == "UP"
    assert out["policy"]["price_alone_breaks_thesis"] is False


def test_projection_attaches_v3_without_mutating_v2_contract():
    out = build_v2_projection(_row())
    v3 = out["quality_dips_v3"]
    assert v3["cycle"] == "QUALITY_DIPS_V3_MARGIN_OF_SAFETY"
    assert v3["fair_value_anchor"] == 140.0
    assert [x["limit_price"] for x in v3["entry_ladder"]["levels"]] == [119.0, 112.0, 105.0, 98.0]
    assert out["policy"]["minimum_upside_hurdle_pct"] == 29.0
    assert out["entry_ladder"]["levels"][0]["required_upside_pct"] == 29.0
    assert v3["execution"] == "MANUAL_ONLY"
