"""Hyperliquid adapter — REST info + optional WebSocket allMids."""

from __future__ import annotations

import asyncio
import json
import time
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any, Optional

import httpx

try:
    import websockets
except ImportError:  # pragma: no cover
    websockets = None  # type: ignore

from app.adapters import hyperliquid_gate_registry
from app.core.logging import get_logger
from app.core.market_freshness import fresh_observation, positive_price

logger = get_logger("hyperliquid")

INFO_URL = "https://api.hyperliquid.xyz/info"
WS_URL = "wss://api.hyperliquid.xyz/ws"


def _paper_funding_observation(symbol, rows, start, end, started, observed):
    from decimal import Decimal

    if (symbol not in ("BTC", "ETH", "SOL") or any(type(v) is not int for v in (start, end, started, observed))
            or start <= 0 or start % 3600000 or end % 3600000 or not 0 < end - start <= 86400000
            or not 0 <= observed - started <= 10000 or end - 3600000 > observed
            or type(rows) is not list or len(rows) != (end - start) // 3600000):
        raise ValueError("Complete bounded hourly funding history required")
    output = []
    for index, row in enumerate(rows):
        if (type(row) is not dict or set(row) != {"coin", "fundingRate", "premium", "time"}
                or row["coin"] != symbol or type(row["time"]) is not int or row["time"] != start + index * 3600000
                or type(row["fundingRate"]) is not str or type(row["premium"]) is not str):
            raise ValueError("Missing, conflicting or unordered funding interval")
        rate, premium = Decimal(row["fundingRate"]), Decimal(row["premium"])
        if not rate.is_finite() or not premium.is_finite() or abs(rate) > Decimal("0.04"):
            raise ValueError("Finite bounded hourly funding rate required")
        output.append({"settlement_at_ms": row["time"], "hourly_rate": row["fundingRate"],
                       "premium": row["premium"], "settlement_oracle": None})
    return {"schema": "ATLAS_HYPERLIQUID_FUNDING_HISTORY_V1", "symbol": symbol, "provider": INFO_URL,
            "start_inclusive_ms": start, "end_exclusive_ms": end, "observed_at_ms": observed,
            "interval_seconds": 3600, "records": output, "rate_history_complete": True,
            "settlement_evidence_complete": False, "financial_execution_authorized": False,
            "startup_authorized": False}


def _paper_execution_observation(symbol, metadata, book, started, observed):
    """Strict Decimal-preserving public evidence parser, not a fill decision."""
    from decimal import Decimal

    def decimal(value, *, positive=False):
        if type(value) is not str:
            raise ValueError("Provider decimal string required")
        parsed = Decimal(value)
        if not parsed.is_finite() or (positive and parsed <= 0):
            raise ValueError("Finite provider quantity required")
        return parsed

    if (symbol not in ("BTC", "ETH", "SOL") or type(started) is not int or type(observed) is not int
            or not 0 <= observed - started <= 10000 or type(metadata) is not list or len(metadata) != 2
            or type(metadata[0]) is not dict or type(metadata[1]) is not list
            or type(book) is not dict or set(book) != {"coin", "time", "levels"}
            or book["coin"] != symbol or type(book["time"]) is not int
            or not 0 <= observed - book["time"] <= 5000):
        raise ValueError("Fresh exact Hyperliquid book/metadata evidence required")
    universe, contexts = metadata[0].get("universe"), metadata[1]
    if (type(universe) is not list or len(universe) != len(contexts)
            or any(type(x) is not dict or type(x.get("name")) is not str for x in universe)
            or len({x["name"] for x in universe}) != len(universe)):
        raise ValueError("Unambiguous instrument/context mapping required")
    indices = [i for i, item in enumerate(universe) if item["name"] == symbol]
    if len(indices) != 1:
        raise ValueError("Selected instrument absent")
    instrument, context = universe[indices[0]], contexts[indices[0]]
    if (instrument.get("isDelisted", False) is not False or type(instrument.get("maxLeverage")) is not int
            or instrument["maxLeverage"] < 1 or type(instrument.get("szDecimals")) is not int
            or not 0 <= instrument["szDecimals"] <= 18 or type(context) is not dict):
        raise ValueError("Verified provider instrument definition required")
    for key in ("markPx", "oraclePx"): decimal(context.get(key), positive=True)
    decimal(context.get("funding"))
    levels = book["levels"]
    if type(levels) is not list or len(levels) != 2 or any(type(side) is not list or not 1 <= len(side) <= 20 for side in levels):
        raise ValueError("Both executable book sides required")
    for index, side in enumerate(levels):
        previous = None
        for row in side:
            if (type(row) is not dict or set(row) != {"px", "sz", "n"}
                    or type(row["n"]) is not int or row["n"] < 1):
                raise ValueError("Malformed book level")
            px = decimal(row["px"], positive=True)
            decimal(row["sz"], positive=True)
            if previous is not None and not (px < previous if index == 0 else px > previous):
                raise ValueError("Unsorted or duplicate book level")
            previous = px
    if decimal(levels[0][0]["px"]) >= decimal(levels[1][0]["px"]):
        raise ValueError("Crossed/locked public book")
    # These are native provider facts, not a converted financial command. In
    # particular current funding is not settled history or historical oracle.
    return {"schema": "ATLAS_HYPERLIQUID_PUBLIC_BOOK_V1", "symbol": symbol,
            "provider": INFO_URL, "observed_at_ms": observed, "request_started_ms": started,
            "book_timestamp_ms": book["time"], "timestamp_basis": "PROVIDER_BOOK_MS",
            "bid": levels[0][0]["px"], "ask": levels[1][0]["px"],
            "bid_size": levels[0][0]["sz"], "ask_size": levels[1][0]["sz"],
            "mark": context["markPx"], "oracle": context["oraclePx"],
            "indicative_funding_rate": context["funding"], "funding_settlement": None,
            "historical_settlement_oracle": None, "fee_schedule": None,
            "size_decimals": instrument["szDecimals"], "provider_max_leverage": instrument["maxLeverage"],
            "margin_table_id": instrument.get("marginTableId"),
            "margin_tables": metadata[0].get("marginTables"),
            "market_book_validated": True, "financial_execution_authorized": False,
            "startup_authorized": False}


def candle_window(data, lookback):
    """Decode original provider bars and select the requested newest window.

    Raw inclusive API responses may contain N+1 bars; callers retain raw evidence.
    This parser grants no freshness, ranking or financial execution authority.
    """
    if type(lookback) is not int or lookback<1 or type(data) is not list:
        raise ValueError('Explicit candle response/window required')
    candles: list[dict[str, Any]] = []
    for c in data:
        if not isinstance(c, dict):
            continue
        try:
            candles.append(
                {
                    "time": int(c.get("t") or 0),
                    "open": float(c.get("o") or 0),
                    "high": float(c.get("h") or 0),
                    "low": float(c.get("l") or 0),
                    "close": float(c.get("c") or 0),
                    "volume": float(c.get("v") or 0),
                    "n": int(c.get("n") or 0),
                }
            )
        except (TypeError, ValueError):
            continue
    return candles[-lookback:]


@dataclass
class Ticker:
    symbol: str
    exchange: str = "hyperliquid"
    price: float = 0.0
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume_24h: float = 0.0
    open_interest: float = 0.0
    funding_rate: Optional[float] = None
    timestamp: str = ""
    timestamp_basis: str = "REST_REQUEST_START"
    price_source: str = "REST_MARK"
    raw: dict[str, Any] = field(default_factory=dict)


class HyperliquidAdapter:
    name = "hyperliquid"

    def __init__(self, *, paper_transport=None) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._connected = False
        self._universe_names: list[str] = []
        self._mids: dict[str, float] = {}
        self._mid_received_at: dict[str, datetime] = {}
        self._last_rest_observed_at: datetime | None = None
        self._last_rest_prices: dict[str, float] = {}
        self._ws_task: Optional[asyncio.Task] = None
        self._ws_running = False
        self._paper_cache_lock = RLock()
        self._paper_cache_revision = 0
        self._paper_cache: dict[str, Any] = {k: {} for k in ('books', 'funding', 'candles', 'trades')}
        self._paper_cache['markets'] = []
        self._paper_transport = self._paper_transport_bound = paper_transport

    def _cache_paper(self, role, key, value):
        """Parsed source facts only; not source authentication or a financial ACK."""
        with self._paper_cache_lock:
            if key is None:
                self._paper_cache[role] = deepcopy(value)
            else:
                self._paper_cache[role][key] = deepcopy(value)
            self._paper_cache_revision += 1

    def paper_source_snapshot(self):
        """Existing cache only. Never connects, refreshes, backfills or trades."""
        with self._paper_cache_lock:
            return {'schema': 'HL_SOURCE_CACHE_V1', 'revision': self._paper_cache_revision,
                    'connected': self._connected, 'facts': deepcopy(self._paper_cache)}

    def ingest_paper_trades(self, frame, *, received_ms, continuity_receipt):
        from app.services.paper_source_publication import parse_public_trades
        value = parse_public_trades(frame, received_ms=received_ms)
        value['continuity_receipt'] = deepcopy(continuity_receipt)
        self._cache_paper('trades', value['symbol'], value)

    def _consume_request(self, kind: str) -> None:
        hyperliquid_gate_registry.consume_before_attempt(kind)

    async def connect(self) -> None:
        # Refuse startup before allocating network clients or tasks.
        hyperliquid_gate_registry.require_gate()
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={"Content-Type": "application/json"},
            )
            logger.info("Hyperliquid HTTP client created")
        self._connected = True
        await self.refresh_universe()
        await self.start_mids_ws()

    async def close(self) -> None:
        with self._paper_cache_lock:
            self._paper_cache={k:{} for k in ('books','funding','candles','trades')}
            self._paper_cache['markets']=[]
            self._paper_cache_revision+=1
        self._ws_running = False
        self._mids.clear()
        self._mid_received_at.clear()
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False

    async def _post(self, body: dict[str, Any]) -> Any:
        if not self._client:
            await self.connect()
        assert self._client is not None
        self._consume_request('HTTP')
        r = await self._client.post(INFO_URL, json=body)
        r.raise_for_status()
        return r.json()

    # ── Universe / allowlist validation ──────────────────────────────

    def monitor_snapshot(self) -> dict[str, Any]:
        """Read existing adapter cache only: no connect, refresh or fallback.

        Mark observations are research evidence, never executable bid/ask or
        funding settlement history. A connected empty/expired cache is not ready.
        """
        stamp = self._last_rest_observed_at
        usable = (self._connected and stamp is not None and fresh_observation(stamp)
                  and bool(self._last_rest_prices)
                  and all(positive_price(p) for p in self._last_rest_prices.values()))
        return {"schema": "ATLAS_HYPERLIQUID_MONITOR_V1",
                "connection": "CONNECTED" if usable else "UNAVAILABLE",
                "observed_at": stamp.isoformat() if stamp is not None else None,
                "timestamp_basis": "REST_REQUEST_START", "session": "CONTINUOUS_24_7",
                "marks": dict(self._last_rest_prices) if usable else {},
                "bid_ask": None, "funding_history": None, "execution_eligible": False,
                "startup_authorized": False}

    async def paper_execution_observation(self, symbol: str, *, clock_ms) -> dict[str, Any]:
        """Two bounded info reads through the existing durable request gate.

        No wallet/account, fee-tier assumption, funding backfill or order route.
        TLS transport and parsed provider facts are not accepted trading authority.
        Caller supplies its independently accepted clock; this adapter creates none.
        """
        if symbol not in ("BTC", "ETH", "SOL") or not callable(clock_ms) or self._client is None:
            raise ValueError("Existing read client, explicit clock and selected instrument required")
        hyperliquid_gate_registry.require_gate()
        started = clock_ms()
        metadata = await self._post({"type": "metaAndAssetCtxs"})
        book = await self._post({"type": "l2Book", "coin": symbol})
        value = _paper_execution_observation(symbol, metadata, book, started, clock_ms())
        self._cache_paper('books', symbol, {'parsed': value, 'metadata': metadata, 'book': book})
        return value

    async def paper_funding_observation(self, symbol: str, start_ms: int, end_ms: int, *, clock_ms) -> dict[str, Any]:
        """At most 24 explicit hourly history rows; missing hours never become zero.

        Public rate history lacks settlement-time oracle evidence. This response
        therefore cannot itself authorize or calculate a financial settlement.
        """
        if (symbol not in ("BTC", "ETH", "SOL") or not callable(clock_ms) or self._client is None
                or type(start_ms) is not int or type(end_ms) is not int or start_ms <= 0
                or start_ms % 3600000 or end_ms % 3600000 or not 0 < end_ms - start_ms <= 86400000):
            raise ValueError("Bounded hourly funding interval and existing read client required")
        hyperliquid_gate_registry.require_gate()
        started = clock_ms()
        data = await self._post({"type": "fundingHistory", "coin": symbol, "startTime": start_ms, "endTime": end_ms - 1})
        value = _paper_funding_observation(symbol, data, start_ms, end_ms, started, clock_ms())
        self._cache_paper('funding', symbol, {'parsed': value, 'rows': data, 'started_ms': started})
        return value

    async def refresh_universe(self) -> list[str]:
        data = await self._post({"type": "meta"})
        universe = data.get("universe") if isinstance(data, dict) else None
        names: list[str] = []
        if isinstance(universe, list):
            for item in universe:
                if isinstance(item, dict) and item.get("name"):
                    names.append(str(item["name"]))
        self._universe_names = names
        logger.info("Hyperliquid universe loaded", count=len(names))
        return names

    def universe_names(self) -> list[str]:
        return list(self._universe_names)

    def validate_allowlist(self, allowlist: list[str]) -> dict[str, Any]:
        """
        Compare config allowlist to live meta names.
        Returns {matched, unknown, suggestions}.
        """
        live = {n.upper(): n for n in self._universe_names}
        matched: list[str] = []
        unknown: list[str] = []
        suggestions: dict[str, list[str]] = {}

        for raw in allowlist:
            key = raw.strip()
            if not key:
                continue
            up = key.upper()
            if up in live:
                matched.append(live[up])
                continue
            # fuzzy: substring / strip xyz suffix
            cands = [
                n
                for n in self._universe_names
                if up in n.upper() or n.upper() in up or up.replace("XYZ", "") in n.upper()
            ]
            unknown.append(key)
            if cands:
                suggestions[key] = cands[:8]
            else:
                suggestions[key] = []

        logger.info(
            "Allowlist validation",
            matched=len(matched),
            unknown=unknown,
            suggestions={k: v for k, v in suggestions.items() if v},
        )
        for u in unknown:
            logger.warning(
                "Allowlist symbol not on Hyperliquid meta",
                symbol=u,
                suggestions=suggestions.get(u, []),
            )
        return {
            "matched": matched,
            "unknown": unknown,
            "suggestions": suggestions,
            "live_count": len(self._universe_names),
        }

    # ── Tickers (metaAndAssetCtxs) ───────────────────────────────────

    async def get_all_tickers(self) -> list[Ticker]:
        observed_at = datetime.now(UTC)
        started = time.monotonic()
        data = await self._post({"type": "metaAndAssetCtxs"})
        if not fresh_observation(observed_at) or time.monotonic() - started > 30:
            raise ValueError("Hyperliquid REST observation expired during retrieval")
        if self._last_rest_observed_at and observed_at < self._last_rest_observed_at:
            raise ValueError("Out-of-order Hyperliquid REST observation")
        if not isinstance(data, list) or len(data) < 2:
            logger.warning("Unexpected metaAndAssetCtxs shape")
            return []

        meta, ctxs = data[0], data[1]
        universe = meta.get("universe") if isinstance(meta, dict) else []
        if not isinstance(universe, list) or not isinstance(ctxs, list):
            return []

        now = observed_at.isoformat()
        out: list[Ticker] = []
        for i, asset in enumerate(universe):
            if i >= len(ctxs):
                break
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "")
            if not name:
                continue
            ctx = ctxs[i] if isinstance(ctxs[i], dict) else {}

            mark = ctx.get("markPx") or ctx.get("midPx") or "0"
            # allMids has no exchange timestamp: a receipt cannot establish that
            # its price is newer than this REST snapshot. Never override REST.
            try:
                price = float(mark)
            except (TypeError, ValueError):
                price = 0.0
            if not positive_price(price):
                continue

            try:
                vol = float(ctx.get("dayNtlVlm") or 0)
            except (TypeError, ValueError):
                vol = 0.0
            try:
                oi = float(ctx.get("openInterest") or 0)
            except (TypeError, ValueError):
                oi = 0.0
            funding = None
            try:
                if ctx.get("funding") is not None:
                    funding = float(ctx["funding"])
            except (TypeError, ValueError):
                funding = None

            out.append(
                Ticker(
                    symbol=name,
                    price=price,
                    volume_24h=vol,
                    open_interest=oi,
                    funding_rate=funding,
                    timestamp=now,
                    raw=dict(ctx),
                )
            )
        prices = {row.symbol: row.price for row in out}
        if observed_at == self._last_rest_observed_at and prices != self._last_rest_prices:
            raise ValueError("Conflicting Hyperliquid observations at the same timestamp")
        self._last_rest_observed_at = observed_at
        self._last_rest_prices = prices
        logger.info("Fetched tickers", count=len(out))
        self._cache_paper('markets', None, [{'symbol':r.symbol, 'price':r.price, 'volume_24h':r.volume_24h,
            'open_interest':r.open_interest, 'funding_rate':r.funding_rate, 'timestamp':r.timestamp}
            for r in out if r.symbol in ('BTC', 'ETH', 'SOL')])
        return out

    # ── Candles ──────────────────────────────────────────────────────

    async def get_candles(
        self,
        symbol: str,
        interval: str = "15m",
        lookback: int = 96,
    ) -> list[dict[str, Any]]:
        # Approximate start from interval minutes
        mins = {
            "1m": 1,
            "3m": 3,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "2h": 120,
            "4h": 240,
            "8h": 480,
            "12h": 720,
            "1d": 1440,
        }.get(interval, 15)
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - lookback * mins * 60 * 1000

        data = await self._post(
            {
                "type": "candleSnapshot",
                "req": {
                    "coin": symbol,
                    "interval": interval,
                    "startTime": start_ms,
                    "endTime": end_ms,
                },
            }
        )
        if not isinstance(data, list):
            return []

        candles = candle_window(data, lookback)
        if symbol in ('BTC', 'ETH', 'SOL') and interval == '5m' and lookback <= 96:
            self._cache_paper('candles', symbol, {'interval': interval, 'observed_at_ms': end_ms, 'rows': candles})
        return candles

    # ── Funding history ──────────────────────────────────────────────

    async def get_funding_history(
        self,
        symbol: str,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """
        POST {"type":"fundingHistory","coin":symbol,"startTime":ms}
        Returns list of {time, fundingRate, ...}.
        """
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - hours * 3600 * 1000
        try:
            data = await self._post(
                {
                    "type": "fundingHistory",
                    "coin": symbol,
                    "startTime": start_ms,
                }
            )
        except Exception as e:
            logger.warning("fundingHistory failed", symbol=symbol, error=str(e))
            return []

        if not isinstance(data, list):
            return []

        rows: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                rows.append(
                    {
                        "time": int(item.get("time") or 0),
                        "funding_rate": float(
                            item.get("fundingRate")
                            or item.get("funding_rate")
                            or item.get("funding")
                            or 0
                        ),
                        "raw": item,
                    }
                )
            except (TypeError, ValueError):
                continue
        return rows

    async def funding_bias(self, symbol: str, hours: int = 8) -> dict[str, Any]:
        """
        Aggregate recent funding for long/short lean.
        Positive cumulative → crowded long → short bias.
        Negative → crowded short → long bias.
        """
        hist = await self.get_funding_history(symbol, hours=hours)
        if not hist:
            return {
                "symbol": symbol,
                "samples": 0,
                "sum_rate": 0.0,
                "avg_rate": 0.0,
                "lean": "neutral",
                "score_delta": 0.0,
            }

        rates = [h["funding_rate"] for h in hist]
        s = sum(rates)
        avg = s / len(rates)
        lean = "neutral"
        delta = 0.0
        # Hyperliquid funding is typically small decimals per interval
        if s >= 0.0005 or avg >= 0.00005:
            lean = "short"  # longs paying → fade longs
            delta = min(12.0, 4.0 + abs(s) * 5000)
        elif s <= -0.0005 or avg <= -0.00005:
            lean = "long"
            delta = min(12.0, 4.0 + abs(s) * 5000)

        return {
            "symbol": symbol,
            "samples": len(rates),
            "sum_rate": round(s, 8),
            "avg_rate": round(avg, 8),
            "lean": lean,
            "score_delta": round(delta, 2),
        }

    # ── WebSocket allMids ────────────────────────────────────────────

    async def start_mids_ws(self) -> None:
        if websockets is None:
            logger.warning("websockets package not installed — allMids WS disabled")
            return
        if self._ws_task and not self._ws_task.done():
            return
        self._ws_running = True
        self._ws_task = asyncio.create_task(self._mids_loop())
        logger.info("Hyperliquid allMids WebSocket starting")

    async def _mids_loop(self) -> None:
        backoff = 2.0
        while self._ws_running:
            transport=self._paper_transport
            stream=None
            try:
                if transport is not None and (transport is not self._paper_transport_bound
                        or transport.verify_subscription(self,('BTC','ETH','SOL')) is not True):
                    raise hyperliquid_gate_registry.RequestGateRefused('Accepted PAPER trade subscription required')
                self._consume_request('WEBSOCKET_CONNECT')
                async with websockets.connect(
                    WS_URL,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=8_000_000,
                ) as ws:
                    self._mids.clear()
                    self._mid_received_at.clear()
                    await ws.send(
                        json.dumps(
                            {
                                "method": "subscribe",
                                "subscription": {"type": "allMids"},
                            }
                        )
                    )
                    logger.info("Subscribed to allMids")
                    if transport is not None:
                        if transport is not self._paper_transport_bound or transport.verify_subscription(self,('BTC','ETH','SOL')) is not True:
                            raise hyperliquid_gate_registry.RequestGateRefused('Accepted PAPER trade subscription required')
                        stream=transport.open_stream(self)
                        for symbol in ('BTC','ETH','SOL'):
                            await ws.send(json.dumps({'method':'subscribe','subscription':{'type':'trades','coin':symbol}}))
                    backoff = 2.0
                    async for raw in ws:
                        if not self._ws_running:
                            break
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        channel = msg.get("channel")
                        data = msg.get("data")
                        if transport is not None:
                            receipt=transport.observe_message(stream,msg,int(time.time()*1000))
                            if channel=='trades':
                                if receipt is None:raise ValueError('Authenticated trade continuity receipt required')
                                self.ingest_paper_trades(msg,received_ms=int(time.time()*1000),continuity_receipt=receipt)
                        if channel == "allMids" and isinstance(data, dict):
                            mids = data.get("mids") if "mids" in data else data
                            if isinstance(mids, dict):
                                for k, v in mids.items():
                                    try:
                                        if positive_price(v):
                                            self._mids[str(k)] = float(v)
                                            self._mid_received_at[str(k)] = datetime.now(UTC)
                                    except (TypeError, ValueError):
                                        continue
            except asyncio.CancelledError:
                break
            except hyperliquid_gate_registry.RequestGateRefused:
                self._ws_running = False
                raise
            except Exception as e:
                self._mids.clear()
                self._mid_received_at.clear()
                logger.warning("allMids WS error — reconnecting", error=str(e))
                await asyncio.sleep(backoff)
                backoff = min(60.0, backoff * 1.5)
            finally:
                self._mids.clear()
                self._mid_received_at.clear()
                with self._paper_cache_lock:
                    self._paper_cache['trades']={}
                    self._paper_cache_revision+=1
                if transport is not None and stream is not None:
                    transport.invalidate_stream(stream)

    def get_mid(self, symbol: str) -> Optional[float]:
        # Short-lived receipt-based research hint, never an authoritative REST mark.
        if not fresh_observation(self._mid_received_at.get(symbol), max_age=5):
            return None
        value = self._mids.get(symbol)
        return value if positive_price(value) else None
