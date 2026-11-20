import asyncio

import app.investment.quality_dips_paper_marking as marking
import app.investment.quality_dips_paper as paper


class Quotes:
    def __init__(self, rows):
        self.rows = rows
    async def get_many(self, symbols):
        return self.rows


def _lot(symbol="MSFT"):
    return {"event": "open_lot", "lot_id": "lot-1", "symbol": symbol}


def test_fresh_quote_marks_open_paper_lot(monkeypatch):
    monkeypatch.setattr(marking, "read_events", lambda: [_lot()])
    monkeypatch.setattr(marking, "open_lots", lambda rows: rows)
    captured = []
    monkeypatch.setattr(marking, "mark_lot", lambda lot_id, **kw: captured.append((lot_id, kw)) or {"lot_id": lot_id})
    svc = Quotes({"MSFT": {"quality": "LIVE", "price": 525.0, "effective_timestamp": "2026-10-05T15:00:00+00:00"}})
    result = asyncio.run(marking.mark_open_quality_dips_paper(quote_service=svc))
    assert result["marked_lots"] == 1
    assert result["skipped_lots"] == 0
    assert captured[0][1]["market_price"] == 525.0
    assert result["live_capital_allowed"] is False


def test_reference_quote_cannot_mark_performance(monkeypatch):
    monkeypatch.setattr(marking, "read_events", lambda: [_lot()])
    monkeypatch.setattr(marking, "open_lots", lambda rows: rows)
    monkeypatch.setattr(marking, "mark_lot", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not mark")))
    svc = Quotes({"MSFT": {"quality": "REFERENCE", "price": 525.0, "effective_timestamp": "2026-10-04T15:00:00+00:00"}})
    result = asyncio.run(marking.mark_open_quality_dips_paper(quote_service=svc))
    assert result["marked_lots"] == 0
    assert result["skipped_lots"] == 1


def test_missing_timestamp_cannot_mark(monkeypatch):
    monkeypatch.setattr(marking, "read_events", lambda: [_lot()])
    monkeypatch.setattr(marking, "open_lots", lambda rows: rows)
    monkeypatch.setattr(marking, "mark_lot", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not mark")))
    svc = Quotes({"MSFT": {"quality": "FRESH", "price": 525.0, "effective_timestamp": None}})
    result = asyncio.run(marking.mark_open_quality_dips_paper(quote_service=svc))
    assert result["marked_lots"] == 0
