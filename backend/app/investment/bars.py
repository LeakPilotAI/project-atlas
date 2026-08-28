"""OHLCV bar + provider failure records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional


@dataclass
class OhlcvBar:
    session_date: str  # YYYY-MM-DD
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    adjusted_close: Optional[float] = None
    source: str = ""
    retrieved_at: Optional[datetime] = None
    effective_timestamp: Optional[datetime] = None
    quality: str = "UNKNOWN"
    issues: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "date": self.session_date,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "adjusted_close": self.adjusted_close,
            "source": self.source,
            "retrieved_at": self.retrieved_at.isoformat() if self.retrieved_at else None,
            "effective_timestamp": self.effective_timestamp.isoformat() if self.effective_timestamp else None,
            "quality": self.quality,
            "issues": list(self.issues),
        }


@dataclass
class ProviderFailure:
    code: str
    message: str
    source: str
    symbol: str = ""
    retryable: bool = True

    def as_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "source": self.source,
            "symbol": self.symbol,
            "retryable": self.retryable,
        }


def parse_session_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    s = str(value)[:10]
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return s
    return None
