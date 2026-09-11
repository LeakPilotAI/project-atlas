from app.services.command_center_summary import build_command_center_summary


def _investment(symbol="MSFT", stance="ACCUMULATE"):
    cls = "ACCUMULATION" if stance == "ACCUMULATE" else "WATCH"
    return {
        "timestamp": "2026-09-10T12:00:00+00:00",
        "symbol": symbol,
        "asset_type": "STOCK",
        "classification": cls,
        "opportunity_score": 82,
        "evidence_quality": "HIGH",
        "thesis": "INTACT",
        "components": {"valuation": 80, "fundamentals": 85, "drawdown": 75, "thesis_integrity": 90},
        "drawdown": {"current_drawdown": -0.2},
    }


def test_summary_keeps_perp_and_investment_domains_separate():
    perp = {
        "running": True,
        "market_count": 200,
        "setups": [{"symbol": "BTC", "side": "LONG", "tier": "PRIME", "state": "PREPARE", "score": 88}],
        "plans": [{"symbol": "BTC", "status": "ENTERED"}],
        "alert_candidates": [],
    }
    out = build_command_center_summary(perp, [_investment("MSFT")])
    assert out["domain"] == "ORCHESTRATION"
    assert out["execution"] == "NO_ORDER_ACTIONS"
    assert out["perps"]["domain"] == "HYPERLIQUID_PERPS"
    assert out["investments"]["domain"] == "EQUITY_INVESTMENT"
    assert out["perps"]["top_setup"]["symbol"] == "BTC"
    assert out["investments"]["top_opportunity"]["symbol"] == "MSFT"
    assert "capital" not in out["perps"]
    assert "market_count" not in out["investments"]


def test_summary_guardrails_explicitly_forbid_cross_domain_merging():
    out = build_command_center_summary({}, [])
    assert out["guardrails"] == {
        "shared_symbols": False,
        "shared_capital_assumptions": False,
        "shared_performance": False,
        "shared_action_logic": False,
    }


def test_investment_summary_never_contains_perp_setup_fields():
    out = build_command_center_summary({"setups": []}, [_investment()])
    inv = out["investments"]
    assert "side" not in inv
    assert "leverage" not in inv
    assert "setup_count" not in inv
    assert inv["top_opportunity"]["stance"] == "ACCUMULATE"


def test_perp_summary_surfaces_auto_paper_journal_counts_without_live_unlock():
    perp = {
        "running": True,
        "market_count": 234,
        "setups": [],
        "plans": [],
        "auto_paper": {
            "open_count": 3,
            "opened_total": 17,
            "closed_total": 14,
            "included_in_paper_journal": True,
            "counts_for_live": False,
        },
    }
    out = build_command_center_summary(perp, [])
    p = out["perps"]
    assert p["auto_paper_open_count"] == 3
    assert p["auto_paper_opened_total"] == 17
    assert p["auto_paper_closed_total"] == 14
    assert p["auto_paper_included_in_journal"] is True
    assert out["execution"] == "NO_ORDER_ACTIONS"
