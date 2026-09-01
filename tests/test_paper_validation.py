"""Phase 6 paper validation — research math only. Gates stay locked."""

from __future__ import annotations

from app.services.funnel_research import EXT_LOCK, RR_LOCK, RSI_LONG_LOCK, RSI_SHORT_LOCK
from app.services.paper_validation import (
    SIDE_MIN_N,
    bootstrap,
    chronological,
    feature_dataset,
    leakage_audit,
    mean_t_ci,
    metrics,
    milestone_status,
    monte_carlo_drawdown,
    r_milestones,
    readiness_report,
    regime_analysis,
    shadow_vs_paper,
    side_analysis,
    uncertainty,
    wilson_ci,
)
from app.services.perp_micro_coach import PerpMicroCoach


def _row(
    r: float,
    *,
    side: str = "LONG",
    regime: str = "TREND_UP",
    mfe: float | None = None,
    mae: float = 0.4,
    i: int = 0,
    features: dict | None = None,
    **extra,
) -> dict:
    mfe = r if mfe is None and r > 0 else (mfe if mfe is not None else 0.2)
    return {
        "trade_id": f"t{i}",
        "event": "close",
        "trade_type": "PAPER",
        "symbol": extra.get("symbol", "BTC"),
        "side": side,
        "regime": regime,
        "net_pnl_r": r,
        "R_multiple": r,
        "mfe_r": mfe,
        "mae_r": mae,
        "duration_sec": 100 + i,
        "holding_time_sec": 100 + i,
        "entry_timestamp": f"2026-08-29T00:{i:02d}:00+00:00",
        "exit_timestamp": f"2026-08-29T01:{i:02d}:00+00:00",
        "signal_timestamp": f"2026-08-29T00:{i:02d}:00+00:00",
        "actual_entry_price": 100.0,
        "actual_exit_price": 100.0 + r,
        "features": features or {"rsi": 25.0, "ext_pct": 1.8, "rr": 1.8},
        "signal_score": 80,
    }


def test_production_gates_still_locked() -> None:
    assert RSI_LONG_LOCK == 28.0
    assert RSI_SHORT_LOCK == 72.0
    assert EXT_LOCK == 1.4
    assert RR_LOCK == 1.8


def test_wilson_ci_and_expectancy() -> None:
    lo, hi = wilson_ci(16, 28)
    assert lo is not None and hi is not None
    assert 0.3 < lo < 0.57 < hi < 0.8
    empty = wilson_ci(0, 0)
    assert empty == (None, None)
    xs = [1.0, 1.0, -1.0, 1.0]
    elo, ehi = mean_t_ci(xs)
    assert elo is not None and ehi is not None
    assert elo < 0.5 < ehi


def test_metrics_profit_factor_and_expectancy() -> None:
    rows = [_row(1.8, i=0), _row(-1.0, i=1), _row(1.8, i=2)]
    m = metrics(rows)
    assert m["n"] == 3
    assert m["wins"] == 2
    assert m["losses"] == 1
    assert m["expectancy"] == round((1.8 - 1.0 + 1.8) / 3, 4)
    assert m["profit_factor"] == round(3.6 / 1.0, 4)
    assert m["payoff_ratio"] == round(1.8 / 1.0, 4)
    assert m["max_drawdown_r"] >= 0


def test_chronological_preserves_time_order() -> None:
    rows = [_row(1.0, i=2), _row(-1.0, i=0), _row(1.0, i=1)]
    ch = chronological(rows, group_size=1)
    labels = [g["label"] for g in ch["sequential_groups"]]
    assert labels[0].startswith("trades 1")
    # first in time is i=0 losing trade
    assert ch["sequential_groups"][0]["winrate"] == 0.0
    assert ch["sequential_groups"][1]["winrate"] == 1.0
    assert ch["time_order"] == "exit_timestamp"


def test_side_analysis_flags_small_sample() -> None:
    rows = [_row(1.0, side="LONG", i=0), _row(-1.0, side="SHORT", i=1)]
    s = side_analysis(rows)
    assert s["LONG"]["n"] == 1
    assert s["SHORT"]["n"] == 1
    assert s["LONG"]["exploratory"] is True
    assert s["SHORT"]["exploratory"] is True
    assert s["structurally_superior"] is None
    assert SIDE_MIN_N == 20


def test_regime_high_vol_always_exploratory() -> None:
    rows = [_row(1.14, regime="HIGH_VOLATILITY", i=i) for i in range(10)]
    rg = regime_analysis(rows)
    hv = rg["HIGH_VOLATILITY"]
    assert hv["n"] == 10
    assert hv["exploratory"] is True
    assert "not actionable" in hv["label"].lower() or "EXPLORATORY" in hv["label"]


def test_shadow_never_combined() -> None:
    paper = [_row(1.0, i=0), _row(1.0, i=1)]
    shadow = [_row(-1.0, i=9), _row(-1.0, i=8), _row(-1.0, i=7)]
    cmp_ = shadow_vs_paper(paper, shadow)
    assert cmp_["combined_forbidden"] is True
    assert cmp_["paper"]["n"] == 2
    assert cmp_["shadow"]["n"] == 3
    assert "average_r" not in cmp_ or "combined" not in cmp_
    assert cmp_["paper"]["expectancy"] > 0
    assert cmp_["shadow"]["expectancy"] < 0


def test_rejection_stage_keys_exist() -> None:
    from app.services.paper_validation import rejection_analysis

    out = rejection_analysis()
    assert isinstance(out, dict)


def test_bootstrap_seeded_and_not_a_forecast() -> None:
    rs = [1.0, -1.0, 1.8, -1.0, 0.5] * 4
    a = bootstrap(rs, n_iter=200, seed=6)
    b = bootstrap(rs, n_iter=200, seed=6)
    assert a == b
    assert "forecast" not in a["label"].lower() or "not a forecast" in a["label"].lower()
    assert a["winrate"]["p5"] <= a["winrate"]["p95"]
    assert a["expectancy"]["p5"] <= a["expectancy"]["p95"]


def test_monte_carlo_drawdown_seeded() -> None:
    rs = [1.0, -1.0, 1.8, -1.0] * 5
    a = monte_carlo_drawdown(rs, n_iter=200, seed=6)
    b = monte_carlo_drawdown(rs, n_iter=200, seed=6)
    assert a == b
    assert a["drawdown_r"]["p50"] <= a["drawdown_r"]["p95"]
    assert a["losing_streak"]["p50"] <= a["losing_streak"]["p95"]
    assert "not a guaranteed" in a["label"].lower()


def test_leakage_detection_and_clean_rows() -> None:
    clean = [_row(1.0, i=1)]
    dirty = _row(
        1.0,
        i=2,
        features={"rsi": 20, "net_pnl_r": 1.8, "future_rsi": 80},
    )
    dirty["exit_timestamp"] = "2026-08-28T00:00:00+00:00"
    dirty["entry_timestamp"] = "2026-08-29T00:00:00+00:00"
    audit = leakage_audit(clean + [dirty])
    assert audit["contaminated"] >= 1
    assert audit["pass"] is False
    assert leakage_audit(clean)["pass"] is True


def test_feature_dataset_point_in_time_fields() -> None:
    rows = [_row(1.8, i=3, features={"rsi": 24.0, "ext_pct": 2.1, "rr": 1.8, "vol": 1e6})]
    ds = feature_dataset(rows)
    assert ds[0]["RSI"] == 24.0
    assert ds[0]["extension"] == 2.1
    assert ds[0]["R"] == 1.8
    assert "future_price" not in ds[0]


def test_milestone_28_is_insufficient() -> None:
    ms = milestone_status(28)
    assert ms["current_label"] == "INSUFFICIENT SAMPLE"
    assert ms["next"] == 30
    assert ms["unlocks_live"] is False
    rows = [_row(1.0 if i % 2 == 0 else -1.0, i=i) for i in range(28)]
    rd = readiness_report(rows, [])
    assert rd["live_capital_allowed"] is False
    assert "INSUFFICIENT EVIDENCE" in rd["conclusion"]
    assert rd["statistical_confidence"] == "LOW"
    assert rd["sample_size"] == "LOW"


def test_uncertainty_flags_n_under_30() -> None:
    rows = [_row(1.0, i=i) for i in range(10)]
    u = uncertainty(rows)
    assert u["sample_too_small"] is True
    assert u["winrate_ci95"][0] is not None


def test_r_milestones_from_mfe() -> None:
    rows = [_row(1.8, i=0, mfe=1.8)]
    ms = r_milestones(rows)
    assert ms["reached_1_8r"]["count"] == 1
    assert ms["reached_0_5r"]["count"] == 1


def test_coach_thresholds_untouched() -> None:
    from app.core.config import get_settings

    s = get_settings()
    assert s.perp_micro_rsi_long == 28.0
    assert s.perp_micro_rsi_short == 72.0
    assert s.perp_micro_min_extension_pct == 1.4
    assert s.perp_micro_min_rr == 1.8
    assert hasattr(PerpMicroCoach, "_rehydrate_open")


def test_exit_research_and_buckets_are_exploratory() -> None:
    from app.services.paper_validation import exit_research, feature_buckets, hour_dow_analysis

    rows = [
        {
            "net_pnl_r": 1.0,
            "mfe_r": 2.0,
            "mae_r": 0.4,
            "duration_sec": 100,
            "entry_timestamp": "2026-08-31T14:00:00+00:00",
            "features": {"rsi": 18, "ext_pct": 1.6, "rr": 1.8, "qscore": 80, "vol": 2_000_000},
            "side": "SHORT",
        },
        {
            "net_pnl_r": -1.0,
            "mfe_r": 0.2,
            "mae_r": 1.0,
            "duration_sec": 80,
            "entry_timestamp": "2026-09-01T15:00:00+00:00",
            "features": {"rsi": 75, "ext_pct": 2.5, "rr": 1.9, "qscore": 60, "vol": 100_000},
            "side": "LONG",
        },
    ]
    er = exit_research(rows)
    assert er["do_not_change_gates"] is True
    assert er["avg_mfe_winners"] == 2.0
    assert er["mean_mfe_captured"] is not None
    fb = feature_buckets(rows)
    assert fb["gates_locked"] is True
    hd = hour_dow_analysis(rows)
    assert "hour" in hd and "day_of_week" in hd
