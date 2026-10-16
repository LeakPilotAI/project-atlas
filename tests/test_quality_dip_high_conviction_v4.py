from app.investment.high_conviction import (
    from_quality_tape,
    from_research_board,
    recovery_runway_pct,
)


def test_recovery_runway_20pct_drawdown_is_25pct():
    assert recovery_runway_pct(-0.20) == 25.0


def test_tape_gate_requires_quality_and_25pct_runway():
    row = {
        "symbol": "MSFT",
        "drawdown": -0.22,
        "thesis": "STRONG",
        "evidence": "HIGH",
    }
    prep = {
        "action": "ACCUMULATE",
        "quality_score": 82,
        "bottom_risk": 25,
        "trap": False,
        "ladder": [{"limit": 400.0}],
    }
    gate = from_quality_tape(row, prep)
    assert gate["high_conviction"] is True
    assert gate["recovery_runway_pct"] > 25
    assert gate["target_hurdle_pct"] == 25.0


def test_tape_gate_rejects_shallow_pullback_even_if_quality_is_high():
    row = {
        "symbol": "MSFT",
        "drawdown": -0.10,
        "thesis": "STRONG",
        "evidence": "HIGH",
    }
    prep = {
        "action": "ACCUMULATE",
        "quality_score": 90,
        "bottom_risk": 10,
        "trap": False,
        "ladder": [],
    }
    gate = from_quality_tape(row, prep)
    assert gate["high_conviction"] is False
    assert any("recovery runway" in x for x in gate["gate_reasons"])


def test_research_board_gate_requires_strong_components_and_stock():
    row = {
        "asset_type": "STOCK",
        "thesis": "STRONG",
        "evidence_quality": "HIGH",
        "opportunity_score": 84,
        "components": {
            "valuation": 82,
            "fundamentals": 88,
            "drawdown": 90,
            "thesis_integrity": 92,
        },
        "drawdown": {"current_drawdown": -0.25},
    }
    gate = from_research_board(row, stance="ACCUMULATE")
    assert gate["high_conviction"] is True
    assert gate["label"] == "A+ QUALITY DIP"


def test_research_board_gate_never_treats_25pct_as_guarantee():
    row = {
        "asset_type": "STOCK",
        "thesis": "STRONG",
        "evidence_quality": "HIGH",
        "opportunity_score": 90,
        "components": {"valuation": 90, "fundamentals": 90},
        "drawdown": {"current_drawdown": -0.25},
    }
    gate = from_research_board(row, stance="ACCUMULATE")
    assert "does not guarantee" in gate["note"]
