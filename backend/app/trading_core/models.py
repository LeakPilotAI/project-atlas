from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class Side(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"

    @property
    def direction(self) -> float:
        return 1.0 if self is Side.LONG else -1.0


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    ERROR = "ERROR"


class ExitReason(str, Enum):
    STOP = "STOP"
    TARGET = "TARGET"
    BREAKEVEN = "BREAKEVEN"
    LOCKED_STOP = "LOCKED_STOP"
    MANUAL = "MANUAL"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class MarketQuote:
    symbol: str
    price: float
    timestamp: datetime

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        if self.price <= 0:
            raise ValueError("price must be > 0")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")


@dataclass(frozen=True)
class TradeIntent:
    trade_id: str
    symbol: str
    side: Side
    signal_price: float
    stop_price: float
    target_r: float
    risk_usd: float
    signal_timestamp: datetime
    strategy_version: str

    def __post_init__(self) -> None:
        if not self.trade_id.strip():
            raise ValueError("trade_id is required")
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        if self.signal_price <= 0 or self.stop_price <= 0:
            raise ValueError("signal and stop prices must be > 0")
        if self.target_r <= 0:
            raise ValueError("target_r must be > 0")
        if self.risk_usd <= 0:
            raise ValueError("risk_usd must be > 0")
        if self.signal_timestamp.tzinfo is None:
            raise ValueError("signal_timestamp must be timezone-aware")
        if self.side is Side.LONG and self.stop_price >= self.signal_price:
            raise ValueError("LONG stop must be below signal price")
        if self.side is Side.SHORT and self.stop_price <= self.signal_price:
            raise ValueError("SHORT stop must be above signal price")


@dataclass(frozen=True)
class PaperExecutionConfig:
    entry_slippage_bps: float = 1.0
    exit_slippage_bps: float = 1.0
    fee_bps_per_side: float = 2.0
    breakeven_after_r: Optional[float] = None
    lock_after_r: Optional[float] = None
    lock_r: float = 0.0

    def __post_init__(self) -> None:
        for name in ("entry_slippage_bps", "exit_slippage_bps", "fee_bps_per_side"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0")
        if self.breakeven_after_r is not None and self.breakeven_after_r < 0:
            raise ValueError("breakeven_after_r must be >= 0")
        if self.lock_after_r is not None and self.lock_after_r < 0:
            raise ValueError("lock_after_r must be >= 0")
        if self.lock_r < 0:
            raise ValueError("lock_r must be >= 0")


@dataclass(frozen=True)
class PaperPosition:
    trade_id: str
    symbol: str
    side: Side
    strategy_version: str
    opened_at: datetime
    signal_price: float
    entry_price: float
    initial_stop: float
    working_stop: float
    target_price: float
    target_r: float
    risk_price: float
    risk_usd: float
    quantity: float
    status: PositionStatus = PositionStatus.OPEN
    mfe_r: float = 0.0
    mae_r: float = 0.0
    last_price: Optional[float] = None
    last_timestamp: Optional[datetime] = None
    be_armed: bool = False
    lock_armed: bool = False
    closed_at: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[ExitReason] = None
    gross_r: Optional[float] = None
    net_r: Optional[float] = None
    fees_usd: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.status is PositionStatus.OPEN

    def evolve(self, **changes) -> "PaperPosition":
        return replace(self, **changes)
