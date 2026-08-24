from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trade_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    side: Mapped[str] = mapped_column(String(8))  # LONG / SHORT
    status: Mapped[str] = mapped_column(String(16), default="OPEN", index=True)
    entry: Mapped[float] = mapped_column(Float)
    stop: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tp1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tp2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_usd: Mapped[float] = mapped_column(Float, default=1.0)
    pnl_r: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    result: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # TP1 / TP2 / STOP
    source: Mapped[str] = mapped_column(String(32), default="perp_micro")
    regime: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_paper_trades_symbol_status", "symbol", "status"),
        Index("ix_paper_trades_opened", "opened_at"),
    )