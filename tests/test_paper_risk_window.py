import json
from datetime import datetime, timezone

from app.services.paper_risk import check_paper_risk
from app.services.paper_risk_window import utc_day_risk_snapshot


def _write(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_daily_risk_window_does_not_carry_prior_day_losses(tmp_path):
    path = tmp_path / "paper.jsonl"
    _write(
        path,
        [
            {
                "event": "close",
                "trade_type": "PAPER",
                "exit_timestamp": "2026-09-29T23:59:00+00:00",
                "net_pnl_r": -10.0,
                "result": "LOSS",
            },
            {
                "event": "close",
                "trade_type": "PAPER",
                "exit_timestamp": "2026-09-30T00:01:00+00:00",
                "net_pnl_r": -1.0,
                "result": "LOSS",
            },
        ],
    )
    snap = utc_day_risk_snapshot(
        path,
        now=datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc),
    )
    assert snap["net_r"] == -1.0
    assert snap["closed"] == 1
    assert snap["window"] == "UTC_DAY"
    decision = check_paper_risk(
        open_positions=[],
        requested_risk_usd=1.0,
        session_net_r=snap["net_r"],
    )
    assert decision["allowed"] is True


def test_daily_risk_window_still_enforces_three_r_loss_stop(tmp_path):
    path = tmp_path / "paper.jsonl"
    _write(
        path,
        [
            {
                "event": "close",
                "trade_type": "PAPER",
                "exit_timestamp": "2026-09-30T01:00:00+00:00",
                "net_pnl_r": -1.25,
                "result": "LOSS",
            },
            {
                "event": "close",
                "trade_type": "PAPER",
                "exit_timestamp": "2026-09-30T02:00:00+00:00",
                "net_pnl_r": -1.75,
                "result": "LOSS",
            },
        ],
    )
    snap = utc_day_risk_snapshot(
        path,
        now=datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc),
    )
    assert snap["net_r"] == -3.0
    decision = check_paper_risk(
        open_positions=[],
        requested_risk_usd=1.0,
        session_net_r=snap["net_r"],
    )
    assert decision["allowed"] is False
    assert "paper session loss stop reached" in decision["blockers"]


def test_daily_risk_window_excludes_non_performance_rows(tmp_path):
    path = tmp_path / "paper.jsonl"
    rows = [
        {"event": "close", "trade_type": "TEST", "exit_timestamp": "2026-09-30T01:00:00Z", "net_pnl_r": -9},
        {"event": "close", "trade_type": "PAPER", "exit_timestamp": "2026-09-30T02:00:00Z", "net_pnl_r": -9, "result": "INTERRUPTED"},
        {"event": "close", "trade_type": "PAPER", "exit_timestamp": "2026-09-30T03:00:00Z", "net_pnl_r": -9, "result": "SESSION_ROLL", "session_roll": True},
        {"event": "close", "trade_type": "PAPER", "exit_timestamp": "2026-09-30T04:00:00Z", "net_pnl_r": 0.5, "result": "WIN"},
    ]
    _write(path, rows)
    snap = utc_day_risk_snapshot(path, now=datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc))
    assert snap["closed"] == 1
    assert snap["net_r"] == 0.5
