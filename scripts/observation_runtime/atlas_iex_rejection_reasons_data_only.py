"""Nonfinancial, privacy-preserving reason counters for *rejected* IEX quotes.

Opt-in diagnostic adapter around the original fail-closed IEXFeed._quote.
The original installed R24 parser remains the only quote-acceptance authority.
Only symbolic rejection labels and counts survive; prices/timestamps/frames/
credentials are never logged, saved or included in exported diagnostics.
Does not connect, authenticate, publish, fill orders, or grant E1 permissions.
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.investment.alpaca_iex import IEXFeed

REASON_CODES = (
    "SYMBOL_OR_SHAPE",
    "PRICE_TYPE_OR_NONFINITE",
    "ZERO_OR_CROSSED_SIDE",
    "SPREAD_OVER_100_BASIS_POINTS",
    "INVALID_QUOTE_SIZE_SHARES",
    "NON_REGULAR_QUOTE_CONDITION",
    "EXCHANGE_OR_TAPE_ABSENT",
    "INVALID_SOURCE_TIMESTAMP",
    "STALE_OR_FUTURE_QUOTE_TIMESTAMP",
    "TIMESTAMP_REVERSED_OR_CONFLICTED",
    "UNCLASSIFIED_ORIGINAL_REFUSAL",
)
STAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?Z\Z")
ORIGINAL_REFUSALS = (ValueError, KeyError, TypeError, ArithmeticError)


def classify_after_original_rejection(message, *, symbols, clock, max_age, prior):
    """Hypothesis for the original rejection, never an acceptance decision.

    This mirrors the original validation order without retaining any fields.
    The actual original parser rejection always takes precedence; an ambiguous
    mismatch is reported as UNCLASSIFIED rather than invented as accepted.
    """
    try:
        if type(message) is not dict or message.get("S") not in symbols:
            return "SYMBOL_OR_SHAPE"
        for side in ("bp", "ap"):
            value = message[side]
            if type(value) not in (int, Decimal) or not Decimal(value).is_finite():
                return "PRICE_TYPE_OR_NONFINITE"
        bid, ask = Decimal(message["bp"]), Decimal(message["ap"])
        if not 0 < bid <= ask:
            return "ZERO_OR_CROSSED_SIDE"
        if (ask - bid) * 10000 / ask > 100:
            return "SPREAD_OVER_100_BASIS_POINTS"
        if any(type(message[x]) is not int or not 0 < message[x] <= 10**9
               for x in ("bs", "as")):
            return "INVALID_QUOTE_SIZE_SHARES"
        if message.get("c") != ["R"]:
            return "NON_REGULAR_QUOTE_CONDITION"
        if any(type(message.get(x)) is not str or not message[x]
               for x in ("bx", "ax", "z")):
            return "EXCHANGE_OR_TAPE_ABSENT"
        stamp = message["t"]
        if type(stamp) is not str or STAMP.fullmatch(stamp) is None:
            return "INVALID_SOURCE_TIMESTAMP"
        parsed = datetime.fromisoformat(stamp)
        fraction = stamp.split(".", 1)[1][:-1] if "." in stamp else ""
        source_ns = int(parsed.replace(microsecond=0).timestamp()) * 10**9 + int(
            fraction.ljust(9, "0") or "0")
        source_seconds = source_ns / 10**9
        seconds_now = clock()
        if not 0 <= seconds_now - source_seconds <= max_age:
            return "STALE_OR_FUTURE_QUOTE_TIMESTAMP"
        old = prior.get(message["S"])
        if old and (source_ns < old["source_ns"] or
                    (source_ns == old["source_ns"] and
                     (str(bid), str(ask), message["bs"], message["as"]) !=
                     (old["bid"], old["ask"], old["bid_shares"], old["ask_shares"]))):
            return "TIMESTAMP_REVERSED_OR_CONFLICTED"
    except (KeyError, ValueError, TypeError, InvalidOperation, OverflowError, ArithmeticError):
        return "UNCLASSIFIED_ORIGINAL_REFUSAL"
    return "UNCLASSIFIED_ORIGINAL_REFUSAL"


class CountOnlyIEXRejectionDiagnostic(IEXFeed):
    """Original inherited parser is unchanged; instrument only its refusals."""

    def __init__(self, symbols, **kwargs):
        super().__init__(symbols, **kwargs)
        self._reason_counts = {
            symbol: {reason: 0 for reason in REASON_CODES}
            for symbol in self.symbols
        }

    def _quote(self, message):
        try:
            return super()._quote(message)
        except ORIGINAL_REFUSALS:
            symbol = message.get("S") if type(message) is dict else None
            if type(symbol) is str and symbol in self._reason_counts:
                reason = classify_after_original_rejection(
                    message, symbols=self.symbols, clock=self.clock,
                    max_age=self.max_age, prior=self.quotes)
                self._reason_counts[symbol][reason] += 1
            raise  # the installed original parser retains all rejection behavior

    def count_only_snapshot(self):
        """Return counts only, never mutable quote data or inferred permission."""
        with self.lock:
            result = {
                symbol: {reason: self._reason_counts[symbol][reason]
                         for reason in REASON_CODES}
                for symbol in sorted(self._reason_counts)
            }
        return {
            "schema": "ATLAS_IEX_COUNT_ONLY_REJECTION_REASONS_RESEARCH_V1",
            "status": "DIAGNOSTIC_ONLY_NO_ISSUER_OR_FINANCIAL_AUTHORITY",
            "original_iex_quote_parser_unchanged": True,
            "reason_counts": result,
            "raw_frames_retained": False,
            "provider_data_rights_accepted": False,
            "paper_start_authorized": False,
            "live_order_authorized": False,
        }

    def reconcile_rejected_counts(self, per_symbol):
        """Refuse an incomplete/contradictory count report."""
        report = self.count_only_snapshot()
        if (type(per_symbol) is not dict or
                set(per_symbol) != set(report["reason_counts"])):
            raise ValueError("IEX_COUNT_ONLY_PER_SYMBOL_IDENTITY_REFUSED")
        for symbol, row in report["reason_counts"].items():
            item = per_symbol[symbol]
            if (type(item) is not dict or
                    type(item.get("rejected")) is not int or
                    sum(row.values()) != item["rejected"]):
                raise ValueError("IEX_COUNT_ONLY_ORIGINAL_REJECTION_TOTAL_MISMATCH")
        return report
