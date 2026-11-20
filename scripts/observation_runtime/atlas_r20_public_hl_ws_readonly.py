"""One bounded, unauthenticated Hyperliquid PUBLIC WebSocket book observation.

Do not invoke an Atlas financial issuer, selected installation, source enrollment,
orders, wallets, or any private account. Genuine WS receipt != permission to trade.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from decimal import Decimal, InvalidOperation

import websockets

SCHEMA = "ATLAS_R20_HL_PUBLIC_WS_BOOK_CONTINUITY_READONLY_V1"
URL = "wss://api.hyperliquid.xyz/ws"
SYMBOLS = ("BTC", "ETH", "SOL")
MAX_MESSAGE_BYTES = 120_000
MAX_DURATION_SECONDS = 30
MAX_CONTINUITY_GAP_SECONDS = 5.0


def _positive_decimal(value):
    if type(value) is not str or len(value) > 40:
        raise ValueError("HL_WS_FINITE_PUBLIC_LEVEL_REQUIRED")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("HL_WS_FINITE_PUBLIC_LEVEL_REQUIRED") from exc
    if not number.is_finite() or not (0 < number < Decimal(1000000000000000)):
        raise ValueError("HL_WS_FINITE_PUBLIC_LEVEL_REQUIRED")
    return number


def validate_public_book(packet, *, observed_ms):
    """Strict structural and temporal check, not financial source authentication."""
    if (type(packet) is not dict or packet.get("channel") != "l2Book"
            or type(packet.get("data")) is not dict
            or type(observed_ms) is not int or observed_ms <= 0):
        raise ValueError("HL_WS_PUBLIC_BOOK_FRAME_REQUIRED")
    data = packet["data"]
    if (data.get("coin") not in SYMBOLS
            or type(data.get("time")) is not int
            or not -1000 <= observed_ms - data["time"] <= 10_000
            or type(data.get("levels")) is not list
            or len(data["levels"]) != 2):
        raise ValueError("HL_WS_BOOK_SYMBOL_TIMESTAMP_OR_SIDES_REFUSED")
    sides = []
    for side in data["levels"]:
        if type(side) is not list or not 1 <= len(side) <= 30:
            raise ValueError("HL_WS_BOOK_DEPTH_REFUSED")
        prices = []
        for level in side:
            if (type(level) is not dict
                    or not {"px", "sz", "n"} <= set(level)
                    or type(level["n"]) is not int or level["n"] <= 0):
                raise ValueError("HL_WS_BOOK_LEVEL_SHAPE_REFUSED")
            px = _positive_decimal(level["px"])
            _positive_decimal(level["sz"])
            prices.append(px)
        sides.append(prices)
    bids, asks = sides
    if (any(bids[i] <= bids[i + 1] for i in range(len(bids) - 1))
            or any(asks[i] >= asks[i + 1] for i in range(len(asks) - 1))
            or bids[0] >= asks[0]):
        raise ValueError("HL_WS_BOOK_CROSSED_OR_UNSORTED")
    return {
        "symbol": data["coin"],
        "source_ms": data["time"],
        "source_age_ms": observed_ms - data["time"],
        "bid_levels": len(bids),
        "ask_levels": len(asks),
    }


def require_fast_five_level_book(receipt):
    if (type(receipt) is not dict or type(receipt.get("bid_levels")) is not int
            or type(receipt.get("ask_levels")) is not int
            or not 1 <= receipt["bid_levels"] <= 5
            or not 1 <= receipt["ask_levels"] <= 5):
        raise ValueError("HL_FAST_BOOK_MAX_FIVE_LEVELS_REQUIRED")
    return receipt


def qualify_continuity(*, subscribed, counts, max_gap, last_message_gap,
                       invalid, total):
    return (subscribed == set(SYMBOLS)
            and all(counts[symbol] >= 2 for symbol in SYMBOLS)
            and all(max_gap[symbol] <= MAX_CONTINUITY_GAP_SECONDS
                    and last_message_gap[symbol] is not None
                    and last_message_gap[symbol] <= MAX_CONTINUITY_GAP_SECONDS
                    for symbol in SYMBOLS)
            and invalid == 0 and total < 1500)


async def observe(*, seconds=20, fast_books=False, connect=None, wall_ms=None, monotonic=None):
    if (type(seconds) is not int or not 10 <= seconds <= MAX_DURATION_SECONDS
            or type(fast_books) is not bool):
        raise ValueError("HL_WS_BOUNDED_WINDOW_REQUIRED")
    clock = wall_ms or (lambda: time.time_ns() // 1_000_000)
    steady = monotonic or time.monotonic
    connector = connect or websockets.connect
    subscribed = set()
    count = {symbol: 0 for symbol in SYMBOLS}
    last_source = {symbol: None for symbol in SYMBOLS}
    last_recv = {symbol: None for symbol in SYMBOLS}
    max_gap = {symbol: 0.0 for symbol in SYMBOLS}
    max_age = {symbol: 0 for symbol in SYMBOLS}
    max_depth = {symbol: 0 for symbol in SYMBOLS}
    invalid = 0
    total = 0
    began = steady()
    # Exactly one public mainnet connection; no reconnect or private endpoints.
    async with connector(
        URL, open_timeout=6, close_timeout=3, ping_interval=15,
        max_size=MAX_MESSAGE_BYTES,
    ) as socket:
        for symbol in SYMBOLS:
            subscription = {"type": "l2Book", "coin": symbol}
            if fast_books:
                subscription["fast"] = True
            await socket.send(json.dumps({
                "method": "subscribe", "subscription": subscription,
            }))
        until = began + seconds
        while steady() < until and total < 1500:
            remaining = max(0.0, until - steady())
            if remaining == 0:
                break
            try:
                raw = await asyncio.wait_for(socket.recv(), timeout=min(3.0, remaining))
            except TimeoutError:
                continue
            total += 1
            if type(raw) is not str or len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
                invalid += 1
                continue
            try:
                item = json.loads(raw)
                if type(item) is not dict:
                    invalid += 1
                    continue
                if item.get("channel") == "subscriptionResponse":
                    data = item.get("data")
                    subscription = data.get("subscription") if type(data) is dict else None
                    if (type(subscription) is dict and data.get("method") == "subscribe"
                            and subscription.get("type") == "l2Book"
                            and subscription.get("coin") in SYMBOLS
                            and (not fast_books or subscription.get("fast") is True)):
                        subscribed.add(subscription["coin"])
                    continue
                if item.get("channel") != "l2Book":
                    continue
                receipt = validate_public_book(item, observed_ms=clock())
                if fast_books:
                    require_fast_five_level_book(receipt)
                symbol = receipt["symbol"]
                if symbol not in subscribed:
                    invalid += 1
                    continue
                source = receipt["source_ms"]
                previous = last_source[symbol]
                if previous is not None and source <= previous:
                    # Identical timestamps are replay/snapshots, not evidence of
                    # fresh updates; backwards time is an unusable source.
                    if source < previous:
                        invalid += 1
                    continue
                last_source[symbol] = source
                moment = steady()
                prior = last_recv[symbol]
                if prior is not None:
                    max_gap[symbol] = max(max_gap[symbol], moment - prior)
                last_recv[symbol] = moment
                count[symbol] += 1
                max_age[symbol] = max(max_age[symbol], receipt["source_age_ms"])
                max_depth[symbol] = max(
                    max_depth[symbol], receipt["bid_levels"], receipt["ask_levels"]
                )
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                invalid += 1

    ended = steady()
    last_message_gap = {
        symbol: (None if last_recv[symbol] is None
                 else round(max(0.0, ended - last_recv[symbol]), 3))
        for symbol in SYMBOLS
    }
    complete = qualify_continuity(
        subscribed=subscribed, counts=count, max_gap=max_gap,
        last_message_gap=last_message_gap, invalid=invalid, total=total,
    )
    return {
        "schema": SCHEMA,
        "status": ("PUBLIC_BOOK_CONTINUITY_OBSERVED_DATA_ONLY"
                   if complete else "PUBLIC_BOOK_CONTINUITY_INCOMPLETE_DATA_ONLY"),
        "window_seconds": seconds,
        "endpoint": URL,
        "fast_five_level_mode_requested": fast_books,
        "full_depth_maker_queue_verified": False,
        "subscription_acknowledged": sorted(subscribed),
        "valid_book_messages": count,
        "maximum_observed_source_age_ms": max_age,
        "maximum_observed_depth_per_side": max_depth,
        "maximum_interarrival_gap_seconds": {
            symbol: round(max_gap[symbol], 3) for symbol in SYMBOLS
        },
        "end_of_window_last_message_age_seconds": last_message_gap,
        "maximum_permitted_gap_seconds": MAX_CONTINUITY_GAP_SECONDS,
        "invalid_or_unusable_messages": invalid,
        "bounded_total_messages": total,
        "one_socket_only": True,
        "provider_rights_verified": False,
        "financial_source_issuer_verified": False,
        "historical_funding_oracle_verified": False,
        "fee_schedule_verified": False,
        "continuous_financial_clock_verified": False,
        "paper_startup_authorized": False,
        "live_trading_authorized": False,
        "data_only_probe_passed": complete,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observe-public", action="store_true")
    parser.add_argument("--seconds", type=int, default=20)
    parser.add_argument("--fast-books", action="store_true")
    args = parser.parse_args(argv)
    if not args.observe_public:
        parser.error("Explicit read-only public WebSocket observation required")
    try:
        report = asyncio.run(observe(seconds=args.seconds, fast_books=args.fast_books))
        print(json.dumps(report, sort_keys=True))
        return 0 if report["data_only_probe_passed"] else 2
    except (OSError, ValueError, TypeError, websockets.WebSocketException, TimeoutError):
        print(json.dumps({
            "schema": SCHEMA, "status": "PUBLIC_WS_PROBE_REFUSED",
            "data_only_probe_passed": False,
            "paper_startup_authorized": False,
            "live_trading_authorized": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
