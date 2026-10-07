from app.services.oos_cost_validation import (
    build_oos_cost_report,
    chronological_holdout,
    cost_stress,
    rolling_expectancy,
    side_and_regime_splits,
)


def _rows(n=100, value=0.2):
    rows = []
    for i in range(n):
        rows.append({
            "exit_timestamp": f"2026-01-{(i % 28) + 1:02d}T00:{i % 60:02d}:00+00:00",
            "net_pnl_r": value if i % 2 == 0 else value / 2,
            "side": "LONG" if i % 2 == 0 else "SHORT",
            "regime": "TREND" if i % 3 else "RANGE",
        })
    return rows


def test_chronological_holdout_is_read_only_and_reports_split():
    rows = _rows(100)
    before = [dict(r) for r in rows]
    report = chronological_holdout(rows)
    assert report["train"]["n"] == 70
    assert report["holdout"]["n"] == 30
    assert rows == before


def test_cost_stress_reduces_expectancy_monotonically():
    report = cost_stress(_rows(60, 0.3), scenarios_r=(0.0, 0.05, 0.10))
    exps = [row["expectancy_r"] for row in report["scenarios"]]
    assert exps[0] > exps[1] > exps[2]


def test_rolling_expectancy_flags_positive_to_negative_transition():
    rows = _rows(30, 0.4) + [
        {"exit_timestamp": f"2026-02-{(i % 28) + 1:02d}T01:{i % 60:02d}:00+00:00", "net_pnl_r": -0.5, "side": "LONG", "regime": "TREND"}
        for i in range(30)
    ]
    report = rolling_expectancy(rows, window=30, step=30)
    assert report["edge_decay_flag"] is True
    assert report["recent_expectancy_r"] < 0


def test_side_and_regime_splits_remain_separate():
    report = side_and_regime_splits(_rows(40))
    assert set(report["side"]) >= {"LONG", "SHORT"}
    assert report["side"]["LONG"]["n"] == 20
    assert report["side"]["SHORT"]["n"] == 20
    assert sum(v["n"] for v in report["regime"].values()) == 40


def test_full_report_never_unlocks_or_retunes():
    report = build_oos_cost_report(_rows(100))
    assert report["domain"] == "HYPERLIQUID_PERPS"
    assert report["strategy_frozen"] is True
    assert report["live_capital_allowed"] is False
    assert "holdout" in report
    assert "rolling" in report
    assert "splits" in report
    assert "cost_stress" in report
