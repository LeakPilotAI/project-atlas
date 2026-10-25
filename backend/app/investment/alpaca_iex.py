"""Data-only IEX socket/cache. No broker client, orders or financial writes.

IEX is a single venue, NOT NBBO. Sizes are round lots until an independently
verified instrument mapping supplies the shares-per-lot conversion.
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from threading import RLock

URL = "wss://stream.data.alpaca.markets/v2/iex"
FEED = "ALPACA_IEX_V1"
SYMBOL = re.compile(r"[A-Z][A-Z0-9.-]{0,14}\Z")


class IEXRefused(ValueError):
    """Only fixed, non-secret error codes cross the provider boundary."""


@dataclass(frozen=True)
class Credentials:
    key: str = field(repr=False)
    secret: str = field(repr=False)

    @classmethod
    def load(cls, path):
        try:
            values = {}
            for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                key, value = line.split("=", 1)
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key in values:
                    raise IEXRefused("IEX_CONFIG_DUPLICATE")
                values[key] = value
            if values.get("ALPACA_TRADING_ENABLED", "").lower() != "false":
                raise IEXRefused("IEX_TRADING_MUST_BE_DISABLED")
            if values.get("ALPACA_DATA_FEED", "iex").lower() != "iex":
                raise IEXRefused("IEX_ONLY_FEED_REQUIRED")
            key, secret = values.get("ALPACA_API_KEY", ""), values.get("ALPACA_API_SECRET", "")
            if not all(
                8 <= len(x) <= 256 and x.isascii() and not any(c.isspace() for c in x)
                for x in (key, secret)
            ):
                raise IEXRefused("IEX_CREDENTIALS_MISSING_OR_INVALID")
            return cls(key, secret)
        except IEXRefused:
            raise
        except (OSError, UnicodeError, ValueError):
            raise IEXRefused("IEX_CONFIGURATION_UNAVAILABLE") from None


def pairs(items):
    result = {}
    for k, v in items:
        if k in result:
            raise IEXRefused("IEX_DUPLICATE_FIELD")
        result[k] = v
    return result


def decode(raw):
    try:
        if len(raw) > 1024 * 1024:
            raise ValueError
        result = json.loads(
            raw,
            parse_float=Decimal,
            object_pairs_hook=pairs,
            parse_constant=lambda x: (_ for _ in ()).throw(ValueError()),
        )
        if (
            not isinstance(result, list)
            or not 1 <= len(result) <= 4096
            or any(type(x) is not dict for x in result)
        ):
            raise ValueError
        return result
    except (ValueError, TypeError, UnicodeError):
        raise IEXRefused("IEX_MALFORMED_MESSAGE") from None


class IEXFeed:
    def __init__(self, symbols, *, clock=time.time, max_age=5, position_symbols=None):
        if (
            not symbols
            or len(symbols) > 30
            or len(set(symbols)) != len(symbols)
            or any(not SYMBOL.fullmatch(s) for s in symbols)
        ):
            raise IEXRefused("IEX_BOUNDED_EXPLICIT_SYMBOLS_REQUIRED")
        if type(max_age) is not int or not 1 <= max_age <= 5:
            raise IEXRefused("IEX_FRESHNESS_BOUND")
        self.symbols, self.clock, self.max_age = tuple(symbols), clock, max_age
        self.lock, self.run_lock = RLock(), asyncio.Lock()
        self.quotes, self.rejected = {}, 0
        self.connection, self.authenticated, self.subscribed = "DISCONNECTED", False, False
        self.error, self.generation, self.observations = None, 0, 0
        self.roster_revision = 0
        self.position_symbols = position_symbols
        self.last_rotation = None

    def request_roster(self, roster):
        """Rotate on a closed/reopened socket, never overlapping connections.

        The research selector must pin all open-position symbols. A change first
        invalidates executable cache state; only a new exact subscription ACK can
        restore it. This is data subscription management, not trade authority.
        """
        symbols = roster.get("symbols")
        required = roster.get("required_symbols")
        pinned = self.position_symbols() if self.position_symbols is not None else None
        if (roster.get("schema") != "QD_IEX_ROSTER_V1" or type(symbols) is not list
                or not symbols or type(required) is not list
                or type(pinned) is not list or not set(pinned) <= set(required)
                or type(roster.get("capacity")) is not int
                or not len(symbols) <= roster["capacity"] <= 30
                or len(set(symbols)) != len(symbols)
                or any(type(s) is not str or not SYMBOL.fullmatch(s) for s in symbols)
                or not set(required) <= set(symbols)):
            raise IEXRefused("IEX_PINNED_ROSTER_REQUIRED")
        with self.lock:
            if tuple(symbols) != self.symbols:
                now = self.clock()
                if self.run_lock.locked() and self.last_rotation is not None and not now - self.last_rotation >= 30:
                    raise IEXRefused("IEX_ROTATION_RATE_LIMIT")
                self.symbols = tuple(symbols)
                self.last_rotation = now
                self.roster_revision += 1
                self.quotes.clear()
                self.disconnect("IEX_ROSTER_CHANGING")

    def disconnect(self, code="IEX_DISCONNECTED"):
        with self.lock:
            self.connection, self.authenticated, self.subscribed = "DISCONNECTED", False, False
            self.error = code

    def receive(self, raw):
        with self.lock:
            try:
                messages = decode(raw)
            except IEXRefused:
                self.disconnect("IEX_MALFORMED_MESSAGE")
                raise
            for message in messages:
                kind = message.get("T")
                if kind == "error":
                    code = message.get("code")
                    safe = {
                        402: "IEX_AUTH_FAILED",
                        401: "IEX_NOT_AUTHENTICATED",
                        404: "IEX_AUTH_TIMEOUT",
                        405: "IEX_SYMBOL_LIMIT",
                        406: "IEX_CONNECTION_LIMIT",
                        409: "IEX_ENTITLEMENT_FAILED",
                        407: "IEX_SLOW_CLIENT",
                        500: "IEX_SERVER_ERROR",
                    }.get(code, "IEX_PROTOCOL_REFUSED")
                    self.disconnect(safe)
                    raise IEXRefused(safe)
                if kind == "success":
                    if message.get("msg") == "authenticated":
                        self.authenticated = True
                    continue
                if kind == "subscription":
                    if not self.authenticated or sorted(message.get("quotes", [])) != sorted(
                        self.symbols
                    ):
                        self.disconnect("IEX_SUBSCRIPTION_MISMATCH")
                        raise IEXRefused("IEX_SUBSCRIPTION_MISMATCH")
                    self.subscribed, self.connection = True, "CONNECTED"
                    continue
                if kind == "q":
                    symbol = message.get("S")
                    try:
                        self._quote(message)
                    except (ValueError, KeyError, TypeError, ArithmeticError):
                        self.rejected += 1
                        if symbol in self.symbols:
                            self.quotes.pop(symbol, None)
                        self.error = "IEX_QUOTE_REJECTED"
                # No trade/bar/status message is reinterpreted as an executable quote.

    def _quote(self, m):
        if not self.authenticated or not self.subscribed or m["S"] not in self.symbols:
            raise ValueError
        for k in ("bp", "ap"):
            if type(m[k]) not in (int, Decimal) or not Decimal(m[k]).is_finite():
                raise ValueError
        bid, ask = Decimal(m["bp"]), Decimal(m["ap"])
        if not 0 < bid <= ask or (ask - bid) * 10000 / ask > 100:
            raise ValueError
        if any(type(m[k]) is not int or not 0 < m[k] <= 10**9 for k in ("bs", "as")):
            raise ValueError
        if m.get("c") != ["R"] or any(
            type(m.get(k)) is not str or not m[k] for k in ("bx", "ax", "z")
        ):
            raise ValueError
        stamp = m["t"]
        if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?Z", stamp):
            raise ValueError
        parsed = datetime.fromisoformat(stamp)
        fraction = stamp.split(".", 1)[1][:-1] if "." in stamp else ""
        source_ns = int(parsed.replace(microsecond=0).timestamp()) * 10**9 + int(
            fraction.ljust(9, "0") or "0"
        )
        source = source_ns / 10**9
        now = self.clock()
        if not 0 <= now - source <= self.max_age:
            raise ValueError
        old = self.quotes.get(m["S"])
        if old and (
            source_ns < old["source_ns"]
            or source_ns == old["source_ns"]
            and (str(bid), str(ask), m["bs"], m["as"])
            != (old["bid"], old["ask"], old["bid_lots"], old["ask_lots"])
        ):
            raise ValueError
        self.observations += 1
        self.quotes[m["S"]] = {
            "symbol": m["S"],
            "bid": str(bid),
            "ask": str(ask),
            "bid_lots": m["bs"],
            "ask_lots": m["as"],
            "timestamp": stamp,
            "source_timestamp": source,
            "source_ns": source_ns,
            "received_at": now,
            "generation": self.generation,
            "sequence": self.observations,
            "latency_ms": round((now - source) * 1000, 3),
        }

    def snapshot(self):
        with self.lock:
            now = self.clock()
            rows = []
            for symbol in self.symbols:
                q = self.quotes.get(symbol)
                fresh = (
                    q is not None
                    and self.connection == "CONNECTED"
                    and self.subscribed
                    and q["generation"] == self.generation
                    and 0 <= now - q["source_timestamp"] <= self.max_age
                )
                rows.append(
                    {
                        **(q or {"symbol": symbol, "bid": None, "ask": None, "timestamp": None}),
                        "state": "FRESH" if fresh else "STALE" if q else "UNAVAILABLE",
                    }
                )
            return {
                "schema": "ATLAS_ALPACA_IEX_VIEW_V1",
                "provider": "ALPACA",
                "feed": "IEX",
                "feed_id": FEED,
                "scope": "SINGLE_EXCHANGE_NOT_NBBO",
                "size_units": "ROUND_LOTS",
                "connection": self.connection,
                "authenticated": self.authenticated,
                "subscribed": self.subscribed,
                "observed_at": now,
                "error": self.error,
                "quotes": rows,
                "paper_startup_authorized": False,
            }

    async def run(self, credentials, *, seconds=30, connect=None, max_reconnects=2, stop=None):
        if (
            not isinstance(credentials, Credentials)
            or type(seconds) not in (int, float)
            or not 1 <= seconds <= 86400
            or type(max_reconnects) is not int
            or not 0 <= max_reconnects <= 3
        ):
            raise IEXRefused("IEX_BOUNDED_CONNECTION_REQUIRED")
        if self.run_lock.locked():
            raise IEXRefused("IEX_ALREADY_CONNECTED")
        if connect is None:
            from websockets.asyncio.client import connect
        # Never inherit a debug frame logger that could expose authentication.
        logger = logging.Logger("atlas.iex.private", level=logging.CRITICAL + 1)  # noqa: LOG001 - private logger cannot inherit frame handlers
        logger.disabled = True
        deadline, attempt = time.monotonic() + seconds, 0
        authenticated, subscribed = False, False
        async with self.run_lock:
            try:
                while time.monotonic() < deadline and not (stop and stop.is_set()):
                    try:
                        roster_revision = self.roster_revision
                        self.generation += 1
                        self.disconnect("IEX_RECONNECTING")
                        async with connect(
                            URL,
                            open_timeout=min(5, max(0.1, deadline - time.monotonic())),
                            close_timeout=2,
                            ping_interval=10,
                            ping_timeout=5,
                            max_size=1024 * 1024,
                            max_queue=16,
                            logger=logger,
                        ) as ws:
                            # Refuse redirect/namespace substitution before sending secrets.
                            if (
                                ws.request.headers.get("Host") != "stream.data.alpaca.markets"
                                or ws.request.path != "/v2/iex"
                            ):
                                raise IEXRefused("IEX_WEBSOCKET_IDENTITY_REFUSED")
                            await ws.send(
                                json.dumps(
                                    {
                                        "action": "auth",
                                        "key": credentials.key,
                                        "secret": credentials.secret,
                                    }
                                )
                            )
                            auth_deadline = min(deadline, time.monotonic() + 5)
                            while not self.authenticated:
                                self.receive(
                                    await asyncio.wait_for(
                                        ws.recv(), max(0.01, auth_deadline - time.monotonic())
                                    )
                                )
                            authenticated = True
                            await ws.send(
                                json.dumps({"action": "subscribe", "quotes": list(self.symbols)})
                            )
                            sub_deadline = min(deadline, time.monotonic() + 5)
                            while not self.subscribed:
                                self.receive(
                                    await asyncio.wait_for(
                                        ws.recv(), max(0.01, sub_deadline - time.monotonic())
                                    )
                                )
                            subscribed = True
                            self.error = None
                            while (time.monotonic() < deadline and not (stop and stop.is_set())
                                   and self.roster_revision == roster_revision):
                                try:
                                    raw = await asyncio.wait_for(
                                        ws.recv(), min(1, max(0.01, deadline - time.monotonic()))
                                    )
                                    self.receive(raw)
                                except TimeoutError:
                                    pass  # RFC6455 transport pings continue independently.
                            if self.roster_revision != roster_revision:
                                continue  # Original socket closes before the next connection.
                            break
                    except IEXRefused as error:
                        self.disconnect(str(error))
                        if self.roster_revision != roster_revision:
                            continue  # Roster changed during auth/ACK; no stale subscription adoption.
                        break  # No credential/entitlement/limit retry storm.
                    except asyncio.CancelledError:
                        raise
                    except Exception:  # noqa: BLE001 - never forward third-party transport errors or headers
                        self.disconnect(
                            "IEX_TRANSPORT_UNAVAILABLE"
                        )  # Never echo exceptions/headers.
                        if attempt >= max_reconnects:
                            break
                        attempt += 1
                        await asyncio.sleep(
                            min(2 ** (attempt - 1), max(0, deadline - time.monotonic()))
                        )
            finally:
                last_error = self.error
                self.disconnect(last_error or "IEX_BOUNDED_PROBE_COMPLETE")
        return {
            "authenticated": authenticated,
            "subscribed": subscribed,
            "endpoint": URL,
            "feed": "IEX",
            "quote_count": self.observations,
            "reconnects": attempt,
            "result": self.snapshot(),
        }

    def research_snapshot(self, symbol):
        from app.investment.market_hours import session_status

        view = self.snapshot()
        q = next((q for q in view["quotes"] if q["symbol"] == symbol), None)
        now = datetime.fromtimestamp(view["observed_at"], UTC)
        regular = session_status(now) == "MARKET_OPEN"
        fresh = q is not None and q["state"] == "FRESH"
        return {
            "symbol": symbol,
            "price": float(q["ask"]) if fresh else None,
            "display_price": float(q["ask"]) if q and q["ask"] else None,
            "trigger_price": float(q["ask"]) if fresh and regular else None,
            "bid": float(q["bid"]) if q and q["bid"] else None,
            "ask": float(q["ask"]) if q and q["ask"] else None,
            "source": "ALPACA_IEX_SINGLE_EXCHANGE_NOT_NBBO",
            "session": "REGULAR" if regular else "CLOSED",
            "market_state": "REGULAR" if regular else "CLOSED",
            "effective_timestamp": q["timestamp"] if q else None,
            "retrieved_at": now.isoformat(),
            "quality": "LIVE" if fresh else "STALE" if q else "UNAVAILABLE",
            "fresh_for_display": fresh,
            "tradable_for_ladder": fresh and regular,
            "is_live": fresh,
            "error": None if fresh else "IEX_QUOTE_UNAVAILABLE",
            "size_units": "ROUND_LOTS",
        }
