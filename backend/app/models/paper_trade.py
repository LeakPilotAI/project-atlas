from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin


class PaperTrade(Base, TimestampMixin):
    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # LONG or SHORT

    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Adaptive evaluation
    status: Mapped[str] = mapped_column(String(32), default="open")  
    # open | closed | expired

    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exit_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Performance metrics
    pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_favorable_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # MFE
    max_adverse_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)    # MAE
    is_winner: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Context
    opportunity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confidence_at_entry: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Adaptive window
    evaluate_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)