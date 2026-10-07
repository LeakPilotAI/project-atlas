from app.services.challenger_lab import PRODUCTION_GATES, challenger_report


def _trade(i, *, regime="TREND_UP", ext=3.2, q=90, pnl=1.0):
    return {
        "event": "close",
        "trade_type": "PAPER",
        "trade_id": f"v6-{i}",
        "symbol": "TEST",
        "side": "LONG",
        "net_pnl_r": pnl,
        "R_multiple": pnl,
        "mfe_r": max(0.0, pnl),
        "mae_r": 0.5,
        "regime": regime,
        "regime_normalized": regime,
        "entry_timestamp": f"2026-09-{1 + (i % 20):02d}T12:00:00+00:00",
        "exit_timestamp": f"2026-09-{1 + (i % 20):02d}T12:05:00+00:00",
        "features": {"rsi": 20, "ext_pct": ext, "rr": 1.8, "qscore": q},
    }


def test_challenger_lab_never_modifies_production_or_live_state():
    rows = [_trade(i) for i in range(50)]
    r = challenger_report(paper=rows)
    assert r["mode"] == "RESEARCH_ONLY"
    assert r["production_strategy_modified"] is False
    assert r["live_capital_allowed"] is False
    assert r["automatic_real_money_execution"] is False
    assert r["production_gates"]["unchanged"] is True
    assert PRODUCTION_GATES == {"rsi_long": 28.0, "rsi_short": 72.0, "extension_pct": 1.4, "min_rr": 1.8}
    assert r["promotion_policy"]["automatic_promotion"] is False


def test_predeclared_challenger_slices_are_separate():
    rows = []
    for i in range(20):
        rows.append(_trade(i, regime="TREND_UP", ext=3.5, q=90, pnl=1.0))
    for i in range(20, 40):
        rows.append(_trade(i, regime="RANGE", ext=1.6, q=75, pnl=-1.0))
    r = challenger_report(paper=rows)
    assert r["paper_n"] == 40
    assert r["challengers"]["trend_regime"]["metrics"]["n"] == 20
    assert r["challengers"]["extension_3pct"]["metrics"]["n"] == 20
    assert r["challengers"]["quality_85"]["metrics"]["n"] == 20
    assert r["challengers"]["trend_extension_quality"]["metrics"]["n"] == 20
    assert r["challengers"]["trend_regime"]["metrics"]["prospective_validated"] is False


def test_exit_challenger_requires_path_aware_replay():
    r = challenger_report(paper=[_trade(i) for i in range(5)])
    assert r["exit_challenger"]["status"] == "DIAGNOSTIC_ONLY"
    assert "point-in-time" in r["exit_challenger"]["next"]
    assert r["shadow_discovery"]["combined_with_paper"] is False
