"""GET /api/validation/edge must return JSON HTTP 200 — never a 500.

These tests call the real FastAPI route (TestClient), not just edge_report().
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.validation import router


def _close(tid, **k):
    ts = k.get("ts", datetime(2026, 8, 1, 14, tzinfo=timezone.utc).isoformat())
    return {
        "event": "close",
        "trade_type": "PAPER",
        "trade_id": tid,
        "symbol": k.get("symbol", "AAA"),
        "side": k.get("side", "LONG"),
        "net_pnl_r": k.get("pnl", 1.0),
        "mfe_r": k.get("mfe", 1.2),
        "mae_r": k.get("mae", 0.4),
        "entry_timestamp": ts,
        "exit_timestamp": ts,
        "features": {"rsi": 20, "ext_pct": 1.6, "rr": 1.8, "qscore": 80, "vol": 2e6},
        "regime": "TREND_UP",
    }


def _write(path, rows):
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            if isinstance(r, str):
                f.write(r + "\n")
            else:
                f.write(json.dumps(r) + "\n")


def _app_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _get_edge(tmp_path, monkeypatch, rows):
    p = tmp_path / "paper_journal.jsonl"
    _write(p, rows)
    shadow = tmp_path / "shadow.jsonl"
    shadow.write_text("", encoding="utf-8")
    monkeypatch.setattr("app.services.paper_journal.JOURNAL_PATH", p)
    monkeypatch.setattr("app.services.shadow_research.CANDIDATES_PATH", shadow)
    client = _app_client()
    resp = client.get("/api/validation/edge")
    assert resp.status_code == 200, resp.text[:800]
    assert "application/json" in resp.headers.get("content-type", "")
    body = resp.json()
    json.dumps(body, allow_nan=False)
    return resp, body


def test_edge_http_normal_journal_200(tmp_path, monkeypatch):
    resp, body = _get_edge(tmp_path, monkeypatch, [_close("a"), _close("b", pnl=-1, side="SHORT")])
    assert resp.status_code == 200
    assert body["title"] == "ATLAS EDGE DIAGNOSTICS"
    assert body["baseline"]["n"] == 2
    assert body["live_capital_allowed"] is False


def test_edge_http_empty_journal_200(tmp_path, monkeypatch):
    resp, body = _get_edge(tmp_path, monkeypatch, [])
    assert resp.status_code == 200
    assert body["baseline"]["n"] == 0
    assert body["ok"] is True


def test_edge_http_malformed_legacy_200(tmp_path, monkeypatch):
    rows = [_close("ok"), "{not json", {"event": "close", "trade_type": "PAPER", "trade_id": "legacy"}]
    resp, body = _get_edge(tmp_path, monkeypatch, rows)
    assert resp.status_code == 200
    assert body["malformed_count"] >= 1
    assert body["baseline"]["n"] >= 1


def test_edge_http_open_trade_not_counted(tmp_path, monkeypatch):
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
    resp, body = _get_edge(tmp_path, monkeypatch, [open_row])
    assert resp.status_code == 200
    assert body["baseline"]["n"] == 0
    assert body["journal_counts"]["open"] == 1


def test_edge_http_closed_trade(tmp_path, monkeypatch):
    resp, body = _get_edge(tmp_path, monkeypatch, [_close("c1")])
    assert resp.status_code == 200
    assert body["baseline"]["n"] == 1


def test_edge_http_mixed_open_closed(tmp_path, monkeypatch):
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
    resp, body = _get_edge(tmp_path, monkeypatch, [open_row, _close("c1")])
    assert resp.status_code == 200
    assert body["baseline"]["n"] == 1
    assert body["journal_counts"]["open"] == 1


def test_edge_http_missing_optional_fields(tmp_path, monkeypatch):
    row = {"event": "close", "trade_type": "PAPER", "trade_id": "x", "net_pnl_r": 0.5}
    resp, body = _get_edge(tmp_path, monkeypatch, [row])
    assert resp.status_code == 200
    assert body["baseline"]["n"] == 1


def test_edge_http_returns_json_not_500(tmp_path, monkeypatch):
    resp, body = _get_edge(tmp_path, monkeypatch, [_close("z")])
    assert resp.status_code == 200
    assert isinstance(body, dict)
    json.dumps(body, allow_nan=False)


def test_edge_http_nan_inf_not_500(tmp_path, monkeypatch):
    rows = [
        _close("ok"),
        {"event": "close", "trade_type": "PAPER", "trade_id": "nan1", "net_pnl_r": float("nan")},
        {"event": "close", "trade_type": "PAPER", "trade_id": "inf1", "net_pnl_r": float("inf")},
    ]
    resp, body = _get_edge(tmp_path, monkeypatch, rows)
    assert resp.status_code == 200
    assert body["malformed_count"] >= 2
    assert body["baseline"]["n"] == 1


def test_edge_http_report_raise_still_200_json(tmp_path, monkeypatch):
    p = tmp_path / "paper_journal.jsonl"
    p.write_text("", encoding="utf-8")
    monkeypatch.setattr("app.services.paper_journal.JOURNAL_PATH", p)

    def boom(*_a, **_k):
        raise RuntimeError("trade only shorts — simulated")

    monkeypatch.setattr("app.services.edge_diagnostics.edge_report", boom)
    client = _app_client()
    resp = client.get("/api/validation/edge")
    assert resp.status_code == 200, resp.text[:800]
    body = resp.json()
    assert body["ok"] is False
    assert body["live_capital_allowed"] is False
    json.dumps(body, allow_nan=False)


def test_edge_http_193_paper_trades_200(tmp_path, monkeypatch):
    rows = []
    t0 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    for i in range(193):
        side = "LONG" if i < 115 else "SHORT"
        wr = 0.43 if side == "LONG" else 0.54
        win = (i % 100) < int(wr * 100)
        pnl = 1.8 if win else -1.0
        ts = (t0 + timedelta(hours=i)).isoformat()
        rows.append(
            _close(
                f"t{i}",
                side=side,
                pnl=pnl,
                symbol=["BTC", "ETH", "SOL", "HYPE", "AAVE"][i % 5],
                ts=ts,
            )
        )
    resp, body = _get_edge(tmp_path, monkeypatch, rows)
    assert resp.status_code == 200
    assert body["baseline"]["n"] == 193
    assert body["live_capital_allowed"] is False
    assert body["control_gates"]["rsi_long"] == 28.0
    assert body["control_gates"]["unchanged"] is True
    assert "narrative" in body
