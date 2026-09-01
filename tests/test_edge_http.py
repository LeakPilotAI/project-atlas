"""GET /api/validation/edge handler must return JSON-serializable dict, never raise."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from app.services.edge_diagnostics import edge_report


def _close(tid, **k):
    row = {
        "event": "close",
        "trade_type": "PAPER",
        "trade_id": tid,
        "symbol": k.get("symbol", "AAA"),
        "side": k.get("side", "LONG"),
        "net_pnl_r": k.get("pnl", 1.0),
        "mfe_r": k.get("mfe", 1.2),
        "mae_r": k.get("mae", 0.4),
        "entry_timestamp": k.get("ts", datetime(2026, 8, 1, 14, tzinfo=timezone.utc).isoformat()),
        "exit_timestamp": k.get("ts", datetime(2026, 8, 1, 14, tzinfo=timezone.utc).isoformat()),
        "features": {"rsi": 20, "ext_pct": 1.6, "rr": 1.8, "qscore": 80, "vol": 2e6},
        "regime": "TREND_UP",
    }
    return row


def _write(path, rows):
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            if isinstance(r, str):
                f.write(r + "\n")
            else:
                f.write(json.dumps(r) + "\n")


def _call(tmp_path, monkeypatch, rows):
    p = tmp_path / "paper_journal.jsonl"
    _write(p, rows)
    monkeypatch.setattr("app.services.paper_journal.JOURNAL_PATH", p)
    body = edge_report(journal_path=p, marks={})
    json.dumps(body)
    return body


def test_edge_normal_journal_200(tmp_path, monkeypatch):
    body = _call(tmp_path, monkeypatch, [_close("a"), _close("b", pnl=-1, side="SHORT")])
    assert body["title"] == "ATLAS EDGE DIAGNOSTICS"
    assert body["baseline"]["n"] == 2
    assert body["live_capital_allowed"] is False


def test_edge_empty_journal_200(tmp_path, monkeypatch):
    body = _call(tmp_path, monkeypatch, [])
    assert body["baseline"]["n"] == 0


def test_edge_malformed_legacy_200(tmp_path, monkeypatch):
    rows = [_close("ok"), "{not json", {"event": "close", "trade_type": "PAPER", "trade_id": "legacy"}]
    body = _call(tmp_path, monkeypatch, rows)
    assert body["malformed_count"] >= 1
    assert body["baseline"]["n"] >= 1


def test_edge_open_and_closed_mixed(tmp_path, monkeypatch):
    open_row = {
        "event": "open",
        "trade_type": "PAPER",
        "trade_id": "open1",
        "symbol": "BBB",
        "side": "LONG",
        "actual_entry_price": 10,
        "stop_price": 9,
        "tp1_price": 12,
    }
    body = _call(tmp_path, monkeypatch, [open_row, _close("c1")])
    assert body["baseline"]["n"] == 1
    assert body["journal_counts"]["open"] == 1


def test_edge_missing_optional_fields(tmp_path, monkeypatch):
    row = {"event": "close", "trade_type": "PAPER", "trade_id": "x", "net_pnl_r": 0.5}
    body = _call(tmp_path, monkeypatch, [row])
    assert body["baseline"]["n"] == 1


def test_edge_returns_json_not_500(tmp_path, monkeypatch):
    body = _call(tmp_path, monkeypatch, [_close("z")])
    assert isinstance(body, dict)
    json.dumps(body)
