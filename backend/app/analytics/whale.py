from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
import httpx

from app.core.logging import get_logger

logger = get_logger("whale")

HYPERLIQUID_INFO = "https://api.hyperliquid.xyz/info"

MIN_WHALE_USD = 50_000
LARGE_WHALE_USD = 250_000


@dataclass
class WhaleTrade:
    symbol: str
    side: str
    size_usd: float
    price: float
    timestamp: datetime
    is_large: bool = False


@dataclass
class WhaleFlow:
    symbol: str
    net_usd: float
    buy_usd: float
    sell_usd: float
    trade_count: int
    largest_trade: Optional[WhaleTrade] = None
    bias: str = "neutral"


async def fetch_recent_trades(symbol: str, limit: int = 50) -> List[dict]:
    payload = {"type": "recentTrades", "coin": symbol}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(HYPERLIQUID_INFO, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data[:limit]
            return []
    except Exception as e:
        logger.warning("Failed to fetch recent trades", symbol=symbol, error=str(e))
        return []


def _parse_trade(symbol: str, raw: dict) -> Optional[WhaleTrade]:
    try:
        price = float(raw.get("px") or raw.get("price") or 0)
        size = float(raw.get("sz") or raw.get("size") or 0)
        side_raw = str(raw.get("side") or "").lower()
        ts_ms = raw.get("time") or raw.get("timestamp") or 0

        if price <= 0 or size <= 0:
            return None

        size_usd = price * size
        if size_usd < MIN_WHALE_USD:
            return None

        side = "buy" if side_raw in ("b", "buy", "bid") else "sell"
        ts = (
            datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            if ts_ms
            else datetime.now(timezone.utc)
        )

        return WhaleTrade(
            symbol=symbol,
            side=side,
            size_usd=round(size_usd, 2),
            price=price,
            timestamp=ts,
            is_large=size_usd >= LARGE_WHALE_USD,
        )
    except Exception:
        return None


async def analyze_whale_flow(symbol: str) -> WhaleFlow:
    raw_trades = await fetch_recent_trades(symbol, limit=80)
    whales: List[WhaleTrade] = []

    for raw in raw_trades:
        t = _parse_trade(symbol, raw)
        if t:
            whales.append(t)

    buy_usd = sum(t.size_usd for t in whales if t.side == "buy")
    sell_usd = sum(t.size_usd for t in whales if t.side == "sell")
    net = buy_usd - sell_usd
    largest = max(whales, key=lambda x: x.size_usd) if whales else None

    if net > LARGE_WHALE_USD * 0.5:
        bias = "bullish"
    elif net < -LARGE_WHALE_USD * 0.5:
        bias = "bearish"
    else:
        bias = "neutral"

    return WhaleFlow(
        symbol=symbol,
        net_usd=round(net, 2),
        buy_usd=round(buy_usd, 2),
        sell_usd=round(sell_usd, 2),
        trade_count=len(whales),
        largest_trade=largest,
        bias=bias,
    )


def whale_boost_for_decision(flow: WhaleFlow, recommendation: str) -> float:
    if flow.bias == "neutral" or flow.trade_count == 0:
        return 0.0

    aligned = (
        (recommendation == "LONG" and flow.bias == "bullish")
        or (recommendation == "SHORT" and flow.bias == "bearish")
    )
    opposed = (
        (recommendation == "LONG" and flow.bias == "bearish")
        or (recommendation == "SHORT" and flow.bias == "bullish")
    )

    if aligned:
        if flow.largest_trade and flow.largest_trade.is_large:
            return 10.0
        return 6.0
    if opposed:
        return -8.0
    return 0.0


def format_whale_note(flow: WhaleFlow) -> str:
    if flow.trade_count == 0:
        return "No notable whale activity"
    parts = [
        f"Whale flow: {flow.bias.upper()}",
        f"Net ${flow.net_usd:+,.0f}",
        f"({flow.trade_count} large trades)",
    ]
    if flow.largest_trade:
        t = flow.largest_trade
        parts.append(f"Largest: {t.side.upper()} ${t.size_usd:,.0f} @ ${t.price:.4f}")
    return " | ".join(parts)