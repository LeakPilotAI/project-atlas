from app.investment.board import build_quality_dips_board


def row(symbol="MSFT", **kw):
    base = {
        "timestamp": "2026-09-10T12:00:00+00:00",
        "symbol": symbol,
        "name": symbol,
        "asset_type": "STOCK",
        "price": 400.0,
        "classification": "ACCUMULATION",
        "opportunity_score": 82,
        "evidence_quality": "HIGH",
        "thesis": "INTACT",
        "components": {"valuation": 70, "fundamentals": 85, "drawdown": 80, "thesis_integrity": 90},
        "drawdown": {"current_drawdown": -0.20},
        "missing_critical": [],
        "explain": {"invalidation": ["guidance break"], "risks": ["macro"]},
    }
    base.update(kw)
    return base


def test_board_is_stock_etf_only_and_accumulate_first():
    rows = [row("MSFT"), row("SPY", asset_type="ETF", opportunity_score=75), row("BTC", asset_type="OTHER")]
    board = build_quality_dips_board(rows)
    assert [r["symbol"] for r in board] == ["MSFT", "SPY"]
    assert all(r["domain"] == "EQUITY_INVESTMENT" for r in board)
    assert all(r["execution"] == "MANUAL_ONLY" for r in board)


def test_latest_research_record_wins_per_symbol():
    old = row("MSFT", timestamp="2026-09-09T12:00:00+00:00", opportunity_score=99)
    new = row("MSFT", timestamp="2026-09-10T12:00:00+00:00", opportunity_score=61, classification="WATCH")
    board = build_quality_dips_board([old, new])
    assert len(board) == 1
    assert board[0]["opportunity_score"] == 61
    assert board[0]["stance"] == "WATCH"


def test_under_pressure_never_gets_actionable_ladder():
    board = build_quality_dips_board([row(thesis="UNDER_PRESSURE")])
    assert board[0]["stance"] == "PREPARE"
    assert board[0]["ladder_eligible"] is False


def test_active_plan_tiers_show_only_when_gate_allows():
    plan = {"symbol": "MSFT", "status": "ACTIVE", "maximum_target_allocation": 1000, "tiers": [{"index": 1, "price": 380, "dollar_amount": 300}]}
    allowed = build_quality_dips_board([row()], [plan])[0]
    blocked = build_quality_dips_board([row(thesis="BROKEN")], [plan])[0]
    assert allowed["tiers"] == plan["tiers"]
    assert blocked["tiers"] == []
