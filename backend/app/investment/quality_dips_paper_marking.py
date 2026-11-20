"""Fresh-quote PAPER marking for open Quality Dips V3 lots.

Marks are observational only. They never create or close positions and reject
non-fresh/reference-only prices so Atlas cannot manufacture performance.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.investment.quality_dip_quotes import QualityDipQuoteService, quality_dip_quote_service
from app.investment.quality_dips_paper import mark_lot, open_lots, read_events

MARKABLE_QUALITIES = frozenset({"LIVE", "FRESH"})


async def mark_open_quality_dips_paper(
    *,
    quote_service: Optional[QualityDipQuoteService] = None,
) -> Dict[str, Any]:
    service = quote_service or quality_dip_quote_service
    opened = open_lots(read_events())
    symbols = sorted({str(row.get("symbol") or "").upper() for row in opened if row.get("symbol")})
    if not symbols:
        return {"requested_symbols": 0, "marked_lots": 0, "skipped_lots": 0, "marks": []}
    quotes = await service.get_many(symbols)
    marks = []
    skipped = 0
    for lot in opened:
        quote = quotes.get(str(lot.get("symbol") or "").upper()) or {}
        quality = str(quote.get("quality") or "").upper()
        price = quote.get("price")
        ts = quote.get("effective_timestamp")
        if quality not in MARKABLE_QUALITIES or price is None or not ts:
            skipped += 1
            continue
        marks.append(mark_lot(lot["lot_id"], market_price=price, observed_at=str(ts)))
    return {
        "requested_symbols": len(symbols),
        "marked_lots": len(marks),
        "skipped_lots": skipped,
        "marks": marks,
        "execution": "PAPER_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
