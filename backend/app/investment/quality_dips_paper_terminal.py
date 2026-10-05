"""Prospective terminal closure for QUALITY_DIPS_PAPER_V1.

Only a current V3 terminal condition plus a fresh/live timestamped quote may
close an open PAPER lot. This is append-only PAPER accounting, never brokerage.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from app.investment.quality_dips_paper import close_lot, open_lots, read_events
from app.investment.quality_dips_paper_exit_policy import evaluate_exit

CLOSABLE_QUOTE_QUALITIES = frozenset({"LIVE", "FRESH"})


def close_terminal_quality_dips_paper(
    board: Iterable[Dict[str, Any]],
    quotes: Dict[str, Dict[str, Any]],
    *,
    events: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Close terminal PAPER lots exactly once at a fresh observed quote."""
    rows = list(events) if events is not None else read_events()
    opened = open_lots(rows)
    by_symbol: Dict[str, Dict[str, Any]] = {}
    for row in board:
        symbol = str(row.get("symbol") or "").upper().strip()
        v3 = dict((row.get("quality_dips_v2") or {}).get("quality_dips_v3") or {})
        if symbol and v3:
            by_symbol[symbol] = {
                "classification": v3.get("patient_state"),
                "prediction": v3,
            }

    closed = []
    skipped = []
    for lot in opened:
        symbol = str(lot.get("symbol") or "").upper().strip()
        terminal = evaluate_exit(by_symbol.get(symbol) or {})
        if not terminal.get("terminal"):
            continue
        quote = dict(quotes.get(symbol) or {})
        quality = str(quote.get("quality") or "").upper().strip()
        price = quote.get("price")
        observed_at = quote.get("effective_timestamp")
        if quality not in CLOSABLE_QUOTE_QUALITIES or price is None or not observed_at:
            skipped.append({
                "lot_id": lot.get("lot_id"),
                "symbol": symbol,
                "terminal_reason": terminal.get("terminal_reason"),
                "reason": "NO_FRESH_EXECUTABLE_MARK",
            })
            continue
        closed.append(
            close_lot(
                str(lot["lot_id"]),
                exit_price=price,
                reason=str(terminal["terminal_reason"]),
                closed_at=str(observed_at),
            )
        )
    return {
        "terminal_candidates": len(closed) + len(skipped),
        "closed_lots": len(closed),
        "skipped_lots": len(skipped),
        "closes": closed,
        "skips": skipped,
        "execution": "PAPER_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
