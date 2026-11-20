from datetime import datetime, timedelta, timezone

from app.services.paper_adaptive_exit import (
    ADAPTIVE_EXIT_POLICY_VERSION,
    evaluate_adaptive_exit,
    policy_metadata,
)


def trade(*, side="LONG", mark=100.0, mfe_r=0.0, minutes=5, adaptive=True):
    now = datetime.now(timezone.utc)
    if side == "LONG":
        stop, tp1, tp2 = 95.0, 105.0, 110.0
    else:
        stop, tp1, tp2 = 105.0, 95.0, 90.0
    return {
        "trade_id": "t1",
        "trade_type": "PAPER",
        "side": side,
        "actual_entry_price": 100.0,
        "risk_price": 5.0,
        "stop_price": stop,
        "working_stop": stop,
        "tp1_price": tp1,
        "tp2_price": tp2,
        "working_target": tp1,
        "mark": mark,
        "mfe_r": mfe_r,
        "mae_r": 0.2,
        "fees_bps": 2.0,
        "slippage_bps": 2.0,
        "entry_timestamp": (now - timedelta(minutes=minutes)).isoformat(),
        "features": {
            "adaptive_exit_policy_version": ADAPTIVE_EXIT_POLICY_VERSION,
        } if adaptive else {},
    }


def strong_setup(side="LONG"):
    direction = 1 if side == "LONG" else -1
    return {
        "symbol": "BTC",
        "side": side,
        "score": 82.0,
        "discovery_stale": False,
        "momentum_pct": 0.35 * direction,
        "trend_pct": 0.55 * direction,
        "volatility_pct": 0.60,
        "volume_24h": 250_000_000.0,
        "open_interest": 90_000_000.0,
    }


def test_static_existing_trade_is_not_retroactively_changed():
    t = trade(mark=102.0, mfe_r=0.8, adaptive=False)
    out = evaluate_adaptive_exit(t, strong_setup())
    assert out["eligible"] is False
    assert out["working_stop"] == 95.0
    assert out["working_target"] == 105.0


def test_materially_green_long_arms_cost_covering_profit_protection():
    t = trade(mark=102.5, mfe_r=0.60)
    out = evaluate_adaptive_exit(t, {"discovery_stale": True})
    assert out["eligible"] is True
    assert out["stage"] in {"PROTECT", "FADE_PROTECT"}
    assert out["working_stop"] > 100.0
    assert out["working_target"] == 105.0
    assert out["guaranteed_no_loss"] is False


def test_strong_fresh_structure_can_extend_target_to_tp2():
    t = trade(mark=102.5, mfe_r=0.60)
    out = evaluate_adaptive_exit(t, strong_setup("LONG"))
    assert out["eligible"] is True
    assert out["strong_follow_through"] is True
    assert out["working_target"] == 110.0
    assert out["working_stop"] > 100.0


def test_fading_evidence_tightens_stop_after_large_mfe():
    t = trade(mark=103.0, mfe_r=1.60)
    fading = strong_setup("LONG")
    fading["momentum_pct"] = -0.20
    fading["trend_pct"] = -0.30
    out = evaluate_adaptive_exit(t, fading)
    assert out["stage"] == "FADE_PROTECT"
    assert out["lock_r"] >= 1.25
    assert out["working_stop"] >= 106.25
    assert out["working_target"] == 105.0


def test_short_trade_uses_inverse_protective_geometry():
    t = trade(side="SHORT", mark=96.0, mfe_r=1.20)
    out = evaluate_adaptive_exit(t, strong_setup("SHORT"))
    assert out["eligible"] is True
    assert out["working_stop"] < 100.0
    assert out["working_target"] == 90.0


def test_time_evidence_can_protect_smaller_green_excursion_after_30m():
    t = trade(mark=101.0, mfe_r=0.30, minutes=31)
    out = evaluate_adaptive_exit(t, {"discovery_stale": True})
    assert out["eligible"] is True
    assert out["stage"] == "TIME_PROTECT"
    assert out["working_stop"] > 100.0


def test_policy_metadata_is_explicitly_paper_only_and_not_a_guarantee():
    meta = policy_metadata()
    assert meta["mode"] == "PAPER_ONLY"
    assert meta["evidence_interval"] == "5m"
    assert meta["automatic_real_money_execution"] is False
    assert meta["live_capital_allowed"] is False
    assert meta["guaranteed_no_loss"] is False
