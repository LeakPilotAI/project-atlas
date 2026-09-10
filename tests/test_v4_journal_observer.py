from __future__ import annotations

import app.services.v4_journal_observer as observer


def test_open_observer_forwards_exact_trade(monkeypatch):
    seen = {}

    def fake(**kwargs):
        seen.update(kwargs)
        return True

    monkeypatch.setattr(observer, "mirror_open_from_legacy", fake)
    observer.on_paper_open(
        trade_id="t1",
        symbol="btc",
        side="LONG",
        entry=100.0,
        stop=98.0,
        setup_rr=1.8,
        risk_usd=2.0,
    )
    assert seen == {
        "trade_id": "t1",
        "symbol": "btc",
        "side": "LONG",
        "price": 100.0,
        "stop": 98.0,
        "setup_rr": 1.8,
        "risk_usd": 2.0,
    }


def test_mark_observer_uppercases_symbol(monkeypatch):
    seen = {}

    def fake(price_map):
        seen.update(price_map)
        return 1

    monkeypatch.setattr(observer, "mirror_marks_from_legacy", fake)
    observer.on_paper_mark(symbol="eth", mark=2500.5)
    assert seen == {"ETH": 2500.5}


def test_open_observer_contains_shadow_failure(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("shadow down")

    monkeypatch.setattr(observer, "mirror_open_from_legacy", boom)
    observer.on_paper_open(
        trade_id="t1",
        symbol="BTC",
        side="LONG",
        entry=100.0,
        stop=98.0,
        setup_rr=1.8,
        risk_usd=1.0,
    )


def test_mark_observer_contains_shadow_failure(monkeypatch):
    def boom(price_map):
        raise RuntimeError("shadow down")

    monkeypatch.setattr(observer, "mirror_marks_from_legacy", boom)
    observer.on_paper_mark(symbol="BTC", mark=101.0)
