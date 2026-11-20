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
        # Historical source ACK evidence only; never restore native
        # connection/authentication after original disconnect.
        self._observed_authenticated = False
        self._observed_subscribed = False

    def receive(self, raw):
        """Remember only native ACK milestones, never source frames/headers.

        The original receive() is the only data/entitlement state machine.
        Its disconnect clears current auth/subscription booleans, so a final
        refusal must not reconstruct those milestones from provider guesses.
        """
        try:
            return super().receive(raw)
        finally:
            with self.lock:
                if self.authenticated:
                    self._observed_authenticated = True
                if self.subscribed:
                    self._observed_subscribed = True

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

# This allowlist contains only original local data-only transport state labels.
# Never export original provider exception strings, headers or raw frames.
SAFE_NATIVE_FEED_ERROR_CODES = frozenset({
    "IEX_AUTH_FAILED",
    "IEX_NOT_AUTHENTICATED",
    "IEX_AUTH_TIMEOUT",
    "IEX_SYMBOL_LIMIT",
    "IEX_CONNECTION_LIMIT",
    "IEX_ENTITLEMENT_FAILED",
    "IEX_SLOW_CLIENT",
    "IEX_SERVER_ERROR",
    "IEX_PROTOCOL_REFUSED",
    "IEX_SUBSCRIPTION_MISMATCH",
    "IEX_MALFORMED_MESSAGE",
    "IEX_TRANSPORT_UNAVAILABLE",
    "IEX_READONLY_CONSUMER_REFUSED",
    "IEX_BOUNDED_PROBE_COMPLETE",
    "IEX_DISCONNECTED",
    "IEX_RECONNECTING",
})


def refusal_safe_snapshot(feed):
    """Sanitize an original R24 probe that has ended, even on REFUSED.

    A missing feed is UNKNOWN, not an invented zero quote count. This is
    diagnostic accounting only and NEVER reclassifies a refused session.
    """
    if feed is None:
        return {
            "feed_instantiated": False,
            "original_auth_ack_observed": None,
            "original_subscription_ack_observed": None,
            "last_native_error_code": "NOT_OBSERVED",
            "per_symbol_quote_diagnostics": None,
            "per_symbol_rejection_reason_counts": None,
            "observations_conclusive": False,
        }
    if type(feed) is not CountOnlyIEXRejectionDiagnostic:
        raise TypeError("IEX_REFUSAL_SAFE_ORIGINAL_FEED_CLASS_REQUIRED")
    if feed.run_lock.locked():
        raise ValueError("IEX_REFUSAL_SAFE_FEED_STILL_RUNNING")
    with feed.lock:
        per_symbol = {}
        reasons = {}
        for symbol in sorted(feed.symbols):
            received = feed.quote_messages_seen[symbol]
            accepted = feed.quote_messages_accepted[symbol]
            rejected = feed.quote_messages_rejected[symbol]
            reason_row = dict(feed._reason_counts[symbol])
            if (any(type(x) is not int or x < 0 or x > 10**7
                    for x in (received, accepted, rejected, *reason_row.values()))
                    or received != accepted + rejected
                    or sum(reason_row.values()) != rejected
                    or set(reason_row) != set(REASON_CODES)):
                raise ValueError("IEX_REFUSAL_SAFE_NATIVE_COUNTS_MISMATCH")
            per_symbol[symbol] = {
                "received": received,
                "accepted": accepted,
                "rejected": rejected,
            }
            reasons[symbol] = reason_row
        error = (feed.error if type(feed.error) is str
                 and feed.error in SAFE_NATIVE_FEED_ERROR_CODES
                 else "REDACTED_OR_UNKNOWN_NATIVE_FEED_ERROR")
        auth = feed._observed_authenticated
        sub = feed._observed_subscribed
        if sub and not auth:
            raise ValueError("IEX_REFUSAL_SAFE_SUBSCRIPTION_WITHOUT_AUTH")
    return {
        "feed_instantiated": True,
        "original_auth_ack_observed": auth,
        "original_subscription_ack_observed": sub,
        "last_native_error_code": error,
        "per_symbol_quote_diagnostics": per_symbol,
        "per_symbol_rejection_reason_counts": reasons,
        "observations_conclusive": False,
    }


def preserve_original_probe_refusal(original_response, feed):
    """Record limited source diagnostics while retaining original refusal.

    Call ONLY after an original selected native R24 probe has returned
    nonzero; a generic original refusal must never become data authorization.
    """
    if (type(original_response) is not dict
            or original_response != {
                "status": "REFUSED",
                "reason": "IEX_CONFIGURATION_OR_DATA_UNAVAILABLE",
            }):
        raise ValueError("IEX_REFUSAL_SAFE_UNRECOGNIZED_PROBE_RESPONSE")
    return {
        "schema": "ATLAS_IEX_ORIGINAL_REFUSAL_SAFE_COUNTS_V1",
        "status": "ORIGINAL_SELECTED_R24_DATA_ONLY_PROBE_REFUSED",
        "original_probe_refused": True,
        "count_only_diagnostics": refusal_safe_snapshot(feed),
        "raw_quote_frames_retained": False,
        "credentials_retained": False,
        "account_data_rights_accepted": False,
        "operational_source_accepted": False,
        "financial_accounts_created": False,
        "financial_paper_authorized": False,
        "live_money_authorized": False,
    }
