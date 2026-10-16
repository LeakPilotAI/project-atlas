import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.challenger_prospective import classify_open, prospective_report


def _row(event, tid, ts, *, regime="TREND_UP", ext=3.2, q=90, pnl=1.0):
    row = {"event": event, "trade_id": tid, "trade_type": "PAPER", "symbol": "X", "side": "LONG", "entry_timestamp": ts.isoformat(), "signal_timestamp": ts.isoformat(), "regime": regime, "regime_normalized": regime, "signal_score": q, "features": {"ext_pct": ext, "qscore": q, "rsi": 20, "rr": 1.8}}
    if event == "close":
        row.update({"exit_timestamp": (ts + timedelta(minutes=5)).isoformat(), "net_pnl_r": pnl, "R_multiple": pnl, "mfe_r": max(pnl, 0), "mae_r": 0.4})
    return row


def _write(path: Path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_membership_uses_open_snapshot_only():
    t = datetime(2026, 9, 15, tzinfo=timezone.utc)
    row = _row("open", "a", t, regime="TREND_UP", ext=3.5, q=91)
    assert classify_open(row) == ["trend_regime", "extension_3pct", "quality_85", "trend_extension_quality"]


def test_pre_cutoff_history_cannot_masquerade_as_prospective(tmp_path):
    cutoff = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)
    old = cutoff - timedelta(hours=1); new = cutoff + timedelta(minutes=1)
    journal = tmp_path / "journal.jsonl"; marker = tmp_path / "marker.json"; members = tmp_path / "members.jsonl"
    marker.write_text(json.dumps({"cohort": "v6_forward_only", "version": "v6", "started_at": cutoff.isoformat(), "forward_only": True}), encoding="utf-8")
    _write(journal, [_row("open", "old", old), _row("close", "old", old, pnl=5), _row("open", "new", new), _row("close", "new", new, pnl=1)])
    r = prospective_report(journal_path=journal, marker_path=marker, membership_path=members, now=cutoff + timedelta(hours=2))
    assert r["membership_count"] == 1
    assert r["closed_count"] == 1
    assert r["baseline"]["total_r"] == 1.0
    assert r["retrospective_rows_count_as_prospective"] is False


def test_membership_survives_restart_and_does_not_duplicate(tmp_path):
    cutoff = datetime(2026, 9, 15, 12, tzinfo=timezone.utc); ts = cutoff + timedelta(minutes=1)
    journal = tmp_path / "journal.jsonl"; marker = tmp_path / "marker.json"; members = tmp_path / "members.jsonl"
    marker.write_text(json.dumps({"cohort": "v6_forward_only", "version": "v6", "started_at": cutoff.isoformat(), "forward_only": True}), encoding="utf-8")
    _write(journal, [_row("open", "x", ts)])
    first = prospective_report(journal_path=journal, marker_path=marker, membership_path=members, now=ts)
    second = prospective_report(journal_path=journal, marker_path=marker, membership_path=members, now=ts + timedelta(minutes=1))
    assert first["added_this_sync"] == 1
    assert second["added_this_sync"] == 0
    assert second["membership_count"] == 1
    assert len([x for x in members.read_text(encoding="utf-8").splitlines() if x.strip()]) == 1


def test_close_features_cannot_reclassify_membership(tmp_path):
    cutoff = datetime(2026, 9, 15, 12, tzinfo=timezone.utc); ts = cutoff + timedelta(minutes=1)
    journal = tmp_path / "journal.jsonl"; marker = tmp_path / "marker.json"; members = tmp_path / "members.jsonl"
    marker.write_text(json.dumps({"cohort": "v6_forward_only", "version": "v6", "started_at": cutoff.isoformat(), "forward_only": True}), encoding="utf-8")
    open_row = _row("open", "x", ts, regime="RANGE", ext=1.5, q=70)
    close_row = _row("close", "x", ts, regime="TREND_UP", ext=9.0, q=99, pnl=2)
    _write(journal, [open_row, close_row])
    r = prospective_report(journal_path=journal, marker_path=marker, membership_path=members, now=ts + timedelta(hours=1))
    assert r["membership_count"] == 1
    assert all(v["opened"] == 0 for v in r["challengers"].values())
    assert r["production_strategy_modified"] is False
    assert r["live_capital_allowed"] is False
