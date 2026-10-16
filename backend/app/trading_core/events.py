from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict

from .models import ExitReason, PaperPosition, PositionStatus, Side


class TradingEventType(str, Enum):
    SIGNAL_CREATED = "SIGNAL_CREATED"
    INTENT_APPROVED = "INTENT_APPROVED"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_MARKED = "POSITION_MARKED"
    STOP_MOVED = "STOP_MOVED"
    POSITION_CLOSED = "POSITION_CLOSED"
    RECOVERY_RESTORED = "RECOVERY_RESTORED"
    DATA_STALE = "DATA_STALE"
    EXECUTION_REJECTED = "EXECUTION_REJECTED"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TradingEvent:
    event_id: str
    event_type: TradingEventType
    trade_id: str
    symbol: str
    timestamp: str
    sequence: int
    payload: Dict[str, Any]
    schema_version: str = "atlas-v4-event-1"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "schema_version": self.schema_version,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, row: Dict[str, Any]) -> "TradingEvent":
        return cls(
            event_id=str(row["event_id"]),
            event_type=TradingEventType(str(row["event_type"])),
            trade_id=str(row["trade_id"]),
            symbol=str(row["symbol"]).upper(),
            timestamp=str(row["timestamp"]),
            sequence=int(row["sequence"]),
            schema_version=str(row.get("schema_version") or "atlas-v4-event-1"),
            payload=dict(row.get("payload") or {}),
        )


def position_to_payload(position: PaperPosition) -> Dict[str, Any]:
    row = asdict(position)
    row["side"] = position.side.value
    row["status"] = position.status.value
    row["opened_at"] = position.opened_at.isoformat()
    row["last_timestamp"] = position.last_timestamp.isoformat() if position.last_timestamp else None
    row["closed_at"] = position.closed_at.isoformat() if position.closed_at else None
    row["exit_reason"] = position.exit_reason.value if position.exit_reason else None
    return row


def position_from_payload(row: Dict[str, Any]) -> PaperPosition:
    def _dt(value: Any):
        if value is None:
            return None
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    exit_reason = row.get("exit_reason")
    return PaperPosition(
        trade_id=str(row["trade_id"]),
        symbol=str(row["symbol"]).upper(),
        side=Side(str(row["side"])),
        strategy_version=str(row["strategy_version"]),
        opened_at=_dt(row["opened_at"]),
        signal_price=float(row["signal_price"]),
        entry_price=float(row["entry_price"]),
        initial_stop=float(row["initial_stop"]),
        working_stop=float(row["working_stop"]),
        target_price=float(row["target_price"]),
        target_r=float(row["target_r"]),
        risk_price=float(row["risk_price"]),
        risk_usd=float(row["risk_usd"]),
        quantity=float(row["quantity"]),
        status=PositionStatus(str(row.get("status") or "OPEN")),
        mfe_r=float(row.get("mfe_r") or 0.0),
        mae_r=float(row.get("mae_r") or 0.0),
        last_price=float(row["last_price"]) if row.get("last_price") is not None else None,
        last_timestamp=_dt(row.get("last_timestamp")),
        be_armed=bool(row.get("be_armed")),
        lock_armed=bool(row.get("lock_armed")),
        closed_at=_dt(row.get("closed_at")),
        exit_price=float(row["exit_price"]) if row.get("exit_price") is not None else None,
        exit_reason=ExitReason(str(exit_reason)) if exit_reason else None,
        gross_r=float(row["gross_r"]) if row.get("gross_r") is not None else None,
        net_r=float(row["net_r"]) if row.get("net_r") is not None else None,
        fees_usd=float(row.get("fees_usd") or 0.0),
    )
