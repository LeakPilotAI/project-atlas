"""Selected PUBLIC Hyperliquid HTTP-book evidence during sparse WebSocket updates.

An 8-second WebSocket gap is NOT an 8-second executable quote.  When the
original WebSocket stream is sparse, read the already-gated, independently
parsed REST book from the SAME existing HyperliquidAdapter's cache.  Never
open sockets, issue an account/financial lease, replay fills, or translate
one public book into a continuous feed or a funding settlement oracle.

This is a research/health-monitor port. Admission for a PAPER order still
requires the independent source, fee, instrument, clock and writer verifiers.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.adapters.hyperliquid import HyperliquidAdapter, _paper_execution_observation

SCHEMA = "HL_PUBLIC_HTTP_GAP_HEALTH_V1"
COINS = frozenset({"BTC", "ETH", "SOL"})
MAX_WEBSOCKET_GAP_MS = 8_000
MAX_BOOK_AGE_MS = 5_000
NO_AUTHORITY = {
    "financial_execution_authorized": False,
    "continuous_websocket_source_accepted": False,
    "provider_rights_accepted": False,
    "fee_schedule_accepted": False,
    "funding_settlement_accepted": False,
    "paper_start_authorized": False,
    "live_trading_authorized": False,
}


class PublicBookContinuityRefused(ValueError):
    """The source cannot be used, including for research/health inspection."""


class PublicRestGapMonitor:
    """One already-connected adapter, read-only, no refresh or issued source."""

    def __init__(self, *, adapter):
        if type(adapter) is not HyperliquidAdapter:
            raise PublicBookContinuityRefused("HL_ORIGINAL_PUBLIC_ADAPTER_REQUIRED")
        self._adapter = adapter
        self._last_now = None
        self._last_book = {}

    def inspect(self, *, symbol, last_ws_book_received_ms, now_ms):
        if (type(symbol) is not str or symbol not in COINS
                or type(now_ms) is not int or now_ms <= 0
                or type(last_ws_book_received_ms) is not int
                or not 0 <= last_ws_book_received_ms <= now_ms
                or self._last_now is not None and now_ms < self._last_now):
            raise PublicBookContinuityRefused("HL_PUBLIC_GAP_CLOCK_OR_SYMBOL_REFUSED")
        self._last_now = now_ms
        gap = now_ms - last_ws_book_received_ms
        if gap <= MAX_WEBSOCKET_GAP_MS:
            # Current WS is NOT accepted by this monitor: it has no WS
            # attestor and does not inspect frames or issue tradable quotes.
            return {
                "schema": SCHEMA,
                "symbol": symbol,
                "status": "WS_WITHIN_GAP_WINDOW_NOT_ATTESTED_HERE",
                "ws_gap_ms": gap,
                "http_book_timestamp_ms": None,
                "rest_public_book_for_research": False,
                **NO_AUTHORITY,
            }
        source = self._adapter.paper_source_snapshot()
        if (type(source) is not dict
                or source.get("schema") != "HL_SOURCE_CACHE_V1"
                or type(source.get("revision")) is not int
                or source["revision"] < 1
                or source.get("connected") is not True
                or type(source.get("facts")) is not dict
                or type(source["facts"].get("books")) is not dict):
            raise PublicBookContinuityRefused("HL_HTTP_GAP_SOURCE_CACHE_UNAVAILABLE")
        row = source["facts"]["books"].get(symbol)
        if type(row) is not dict or set(row) != {"parsed", "metadata", "book"}:
            raise PublicBookContinuityRefused("HL_HTTP_GAP_REAL_ADAPTER_PARSED_BOOK_REQUIRED")
        data = row["parsed"]
        if (type(data) is not dict
                or data.get("schema") != "ATLAS_HYPERLIQUID_PUBLIC_BOOK_V1"
                or data.get("provider") != "https://api.hyperliquid.xyz/info"
                or data.get("symbol") != symbol
                or data.get("timestamp_basis") != "PROVIDER_BOOK_MS"
                or data.get("market_book_validated") is not True
                or data.get("financial_execution_authorized") is not False
                or data.get("startup_authorized") is not False
                or data.get("fee_schedule") is not None
                or data.get("funding_settlement") is not None
                or data.get("historical_settlement_oracle") is not None):
            raise PublicBookContinuityRefused("HL_HTTP_GAP_UNAUTHENTICATED_PUBLIC_BOOK")
        start, observed, stamp = (
            data.get("request_started_ms"), data.get("observed_at_ms"),
            data.get("book_timestamp_ms"),
        )
        if (any(type(x) is not int for x in (start, observed, stamp))
                or not 0 < start <= observed <= now_ms
                or not 0 < stamp <= observed
                or not 0 <= now_ms - stamp <= MAX_BOOK_AGE_MS
                or not 0 <= observed - start <= 10_000
                or type(row["book"]) is not dict
                or row["book"].get("coin") != symbol
                or row["book"].get("time") != stamp):
            raise PublicBookContinuityRefused("HL_HTTP_GAP_REAL_PROVIDER_TIMESTAMP_STALE")
        try:
            bid, ask, bid_sz, ask_sz = (Decimal(data[k]) for k in (
                "bid", "ask", "bid_size", "ask_size"))
        except (InvalidOperation, TypeError, KeyError, ValueError) as exc:
            raise PublicBookContinuityRefused("HL_HTTP_GAP_FINITE_PRICE_SIZE_REQUIRED") from exc
        if (not all(x.is_finite() and x > 0 for x in (bid, ask, bid_sz, ask_sz))
                or bid >= ask):
            raise PublicBookContinuityRefused("HL_HTTP_GAP_CROSSED_OR_INVALID_BOOK")
        # Reconstruct the exact ORIGINAL adapter-accepted book from raw
        # provider payloads, not a caller-adjusted parsed-cache dictionary.
        # Even though this monitor grants NO financial authority, a changed
        # cache should not be described as an actual original REST cut.
        try:
            parsed_again = _paper_execution_observation(
                symbol, row["metadata"], row["book"], start, observed)
        except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
            raise PublicBookContinuityRefused(
                "HL_HTTP_GAP_ORIGINAL_PROVIDER_PARSE_REFUSED") from exc
        if parsed_again != data:
            raise PublicBookContinuityRefused(
                "HL_HTTP_GAP_ORIGINAL_PROVIDER_FACTS_MISMATCH")
        prior = self._last_book.get(symbol)
        if prior is not None and (stamp <= prior[0] or source["revision"] <= prior[1]):
            raise PublicBookContinuityRefused("HL_HTTP_GAP_REPLAY_OR_OLD_CACHE")
        # Two cache reads detect a source replacement during verification.
        if self._adapter.paper_source_snapshot() != source:
            raise PublicBookContinuityRefused("HL_HTTP_GAP_SOURCE_CHANGED_DURING_READ")
        self._last_book[symbol] = (stamp, source["revision"])
        return {
            "schema": SCHEMA,
            "symbol": symbol,
            "status": "FRESH_HTTP_BOOK_FOR_RESEARCH_ONLY_WS_GAP_UNRESOLVED",
            "ws_gap_ms": gap,
            "http_book_timestamp_ms": stamp,
            "http_book_age_ms": now_ms - stamp,
            "rest_public_book_for_research": True,
            **NO_AUTHORITY,
        }
