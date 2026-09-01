"""Phase 8 edge diagnostics — research only, no gate changes."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.edge_diagnostics import (
    FORBIDDEN,
    direction_deep,
    edge_report,
    edge_text,
    enrich_exits,
    exit_diagnosis,
    gate_interactions,
    holdout_split,
    loss_clusters,
    session_bucket,
    drawdown_path,
)
from app.services.funnel_research import EXT_LOCK, RR_LOCK, RSI_LONG_LOCK, RSI_SHORT_LOCK
from app.services.paper_validation import leakage_audit, r_series


def _t(i: int) -> str:
    return (datetime(2026, 8, 1, tzinfo=timezone.utc) + timedelta(hours=i)).isoformat()


def _trade(
    i: int,
    *,
    side="LONG",
    pnl=1.0,
    mfe=1.5,
    mae=0.4,
    regime="TREND_UP",
    symbol="AAA",
    rsi=20.0,
    ext=1.6,
    rr=1.8,
    q=80,
    vol=2_000_000,
    hour=14,
    result="TP1",
) -> dict:
    ts = datetime(2026, 8, 1, hour % 24, tzinfo=timezone.utc) + timedelta(days=i)
    return {
        "event": "close",
        "trade_type": "PAPER",
        "trade_id": f"t{i}",
        "symbol": symbol,
        "side": side,
        "net_pnl_r": pnl,
        "R_multiple": pnl,
        "mfe_r": mfe,
        "mae_r": mae,
        "entry_timestamp": ts.isoformat(),
        "exit_timestamp": (ts + timedelta(minutes=20)).isoformat(),
        "signal_timestamp": ts.isoformat(),
        "duration_sec": 1200,
        "regime": regime,
        "regime_normalized": regime,
        "exit_reason": result,
        "actual_entry_price": 100.0,
        "stop_price": 99.0,
        "tp1_price": 101.8,
        "features": {"rsi": rsi, "ext_pct": ext, "rr": rr, "qscore": q, "vol": vol},
    }


def test_gates_untouched() -> None:
    assert RSI_LONG_LOCK == 28.0
    assert RSI_SHORT_LOCK == 72.0
    assert EXT_LOCK == 1.4
    assert RR_LOCK == 1.8


def test_mfe_capture_and_giveback() -> None:
    rows = [
        _trade(0, pnl=0.8, mfe=2.0),  # gave back
        _trade(1, pnl=-1.0, mfe=0.7, side="SHORT"),  # loser had MFE
        _trade(2, pnl=1.8, mfe=1.8),
    ]
    en = enrich_exits(rows)
    assert en[0]["_capture"] == 0.4
    assert en[0]["_gave_back"] is True
    assert en[1]["_loser_had_mfe"] is True
    d = exit_diagnosis(en)
    assert d["do_not_change_exits"] is True
    assert d["milestones"]["reached_1_5r"]["count"] == 2
    assert d["milestones"]["reached_3_0r"]["count"] == 0
    assert "leave exits unchanged" in d["note"].lower() or "exploratory" in d["note"].lower()


def test_mae_and_missing_time_to_mfe() -> None:
    rows = [_trade(0, mae=1.2, mfe=0.5, pnl=-1.0)]
    d = exit_diagnosis(enrich_exits(rows, marks={}))
    assert d["avg_mae"] == 1.2
    assert d["median_time_to_mfe_sec"] is None
    assert "UNKNOWN" in d["time_to_extreme_note"]


def test_time_to_mfe_from_marks() -> None:
    t0 = datetime(2026, 8, 1, 14, tzinfo=timezone.utc)
    rows = [_trade(0, pnl=1.0, mfe=1.5)]
    rows[0]["entry_timestamp"] = t0.isoformat()
    rows[0]["trade_id"] = "x1"
    marks = {
        "x1": [
            {"event": "mark", "trade_id": "x1", "mfe_r": 0.4, "mae_r": 0.1, "timestamp": (t0 + timedelta(seconds=10)).isoformat()},
            {"event": "mark", "trade_id": "x1", "mfe_r": 1.5, "mae_r": 0.2, "timestamp": (t0 + timedelta(seconds=40)).isoformat()},
        ]
    }
    en = enrich_exits(rows, marks)
    assert en[0]["_time_to_mfe"] == 40.0


def test_direction_buckets_exploratory() -> None:
    rows = [_trade(i, side="LONG", pnl=-1.0 if i < 8 else 1.0) for i in range(12)]
    rows += [_trade(20 + i, side="SHORT", pnl=1.0 if i < 10 else -1.0) for i in range(12)]
    d = direction_deep(rows)
    assert d["structurally_superior"] is None
    assert d["recommendation"].startswith("none")
    assert "exploratory" in d["statistical"].lower() or "insufficient" in d["statistical"].lower()
    assert "LONG" in d and "SHORT" in d


def test_regime_and_time_thin_label() -> None:
    rows = [_trade(i, regime="RANGE", pnl=-0.5, hour=3) for i in range(5)]
    rows += [_trade(10 + i, regime="HIGH_VOLATILITY", pnl=1.0, hour=15) for i in range(20)]
    from app.services.paper_validation import regime_analysis

    rg = regime_analysis(rows)
    assert rg["RANGE"]["exploratory"] is True
    sess = session_bucket(rows)
    asia = sess["session"].get("ASIA") or {}
    if asia:
        assert asia["exploratory"] is True or asia["n"] < 15


def test_gate_interactions_do_not_optimize() -> None:
    rows = [_trade(i, rsi=18, ext=2.2, q=90, pnl=0.5) for i in range(16)]
    g = gate_interactions(rows)
    assert g["do_not_optimize"] is True
    assert g["gates_locked"]["rsi_long"] == 28.0
    assert "drop a locked gate" in g["note"].lower() or "do not search" in g["note"].lower()


def test_loss_clusters() -> None:
    rows = [_trade(i, symbol="ZZZ", pnl=-1.0, regime="RANGE") for i in range(10)]
    rows += [_trade(20 + i, symbol="QQQ", pnl=1.0, regime="HIGH_VOLATILITY") for i in range(10)]
    c = loss_clusters(rows)
    assert "ZZZ" in c["by_symbol"]
    assert c["by_symbol"]["ZZZ"]["total_r"] < 0


def test_drawdown_streak() -> None:
    rows = [_trade(i, pnl=-1.0) for i in range(8)] + [_trade(10, pnl=2.0)]
    d = drawdown_path(rows)
    assert d["longest_losing_streak"] == 8
    assert d["max_drawdown_r"] >= 8.0
    assert d["causation"] is False


def test_chronological_holdout_not_shuffled() -> None:
    rows = [_trade(i, pnl=1.0 if i % 2 == 0 else -0.5) for i in range(50)]
    h = holdout_split(rows)
    assert h["available"] is True
    assert h["shuffled"] is False
    assert h["research"]["n"] + h["holdout"]["n"] == 50
    assert str(h["research"]["first_ts"]) <= str(h["holdout"]["first_ts"])
    tiny = holdout_split(rows[:10])
    assert tiny["available"] is False


def test_no_future_leakage() -> None:
    rows = [_trade(0), _trade(1, pnl=-1)]
    leak = leakage_audit(rows)
    assert leak["pass"] is True
    bad = dict(rows[0])
    bad["features"] = {"future_close": 1}
    leak2 = leakage_audit([bad])
    assert leak2["pass"] is False


def test_paper_shadow_separation() -> None:
    paper = [_trade(i, pnl=1.0) for i in range(12)]
    shadow = [_trade(100 + i, pnl=-1.0, symbol="SH") for i in range(12)]
    for s in shadow:
        s["trade_type"] = "SHADOW"
    r = edge_report(paper=paper, shadow=shadow, marks={})
    assert r["combined_forbidden"] is True
    assert r["paper_vs_shadow"]["combined_forbidden"] is True
    assert r["paper_vs_shadow"]["paper"]["n"] == 12
    assert r["paper_vs_shadow"]["shadow"]["n"] == 12
    assert r["paper_vs_shadow"]["paper"]["expectancy"] != r["paper_vs_shadow"]["shadow"]["expectancy"]


def test_edge_report_forbids_live_claims() -> None:
    rows = [_trade(i, side="SHORT" if i % 2 else "LONG", pnl=0.3 if i % 3 else -1.0) for i in range(45)]
    r = edge_report(paper=rows, shadow=[], marks={})
    blob = str(r).lower()
    for phrase in FORBIDDEN:
        assert phrase not in blob
    assert r["live_capital_allowed"] is False
    assert r["control_gates"]["unchanged"] is True
    text = edge_text()
    assert "unlock live" not in text.lower()
    assert "trade only shorts" not in text.lower()


def test_no_trading_files_imported() -> None:
    import inspect
    from app.services import edge_diagnostics as m

    src = Path(inspect.getfile(m)).read_text(encoding="utf-8")
    assert "perp_micro_coach" not in src
    assert "perp_micro_rsi" not in src
