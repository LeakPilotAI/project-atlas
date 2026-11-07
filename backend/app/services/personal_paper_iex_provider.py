"""Read-only authenticated existing IEX feed adapter for personal PAPER diagnostics.

No socket startup, credential loading, broker client or simulated fill.
"""
from __future__ import annotations

from app.investment.alpaca_iex import IEXFeed


class PersonalPaperIEXProvider:
    def __init__(self, feed: IEXFeed):
        if type(feed) is not IEXFeed:
            raise ValueError("EXISTING_ALPACA_IEX_FEED_REQUIRED")
        self._feed = feed

    def read_iex_quote(self, symbol: str) -> dict:
        with self._feed.lock:
            view = self._feed.snapshot()
            if (view.get("schema") != "ATLAS_ALPACA_IEX_VIEW_V1"
                    or view.get("feed_id") != "ALPACA_IEX_V1"
                    or view.get("scope") != "SINGLE_EXCHANGE_NOT_NBBO"
                    or view.get("size_units") != "ROUND_LOTS"
                    or view.get("authenticated") is not True
                    or view.get("subscribed") is not True
                    or view.get("connection") != "CONNECTED"
                    or view.get("error") is not None):
                raise ValueError("AUTHENTICATED_IEX_FEED_UNAVAILABLE")
            if symbol not in self._feed.symbols:
                raise ValueError("IEX_SYMBOL_NOT_SUBSCRIBED")
            rows = [row for row in view["quotes"] if row.get("symbol") == symbol]
            if len(rows) != 1 or rows[0].get("state") != "FRESH":
                raise ValueError("IEX_QUOTE_NOT_FRESH")
            row = rows[0]
            if (row.get("generation") != self._feed.generation
                    or row.get("timestamp") is None):
                raise ValueError("IEX_QUOTE_GENERATION_INVALID")
        return {"symbol": symbol, "state": row["state"],
                "bid": row["bid"], "ask": row["ask"],
                "bid_lots": row["bid_lots"], "ask_lots": row["ask_lots"],
                "timestamp": row["timestamp"],
                "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP",
                "source": "ALPACA_IEX_PROVIDER_QUOTE"}
