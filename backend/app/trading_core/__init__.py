"""Atlas V4 deterministic trading core.

This package is intentionally isolated from network, Discord, FastAPI and storage.
It contains pure domain models and deterministic paper-execution logic that can be
replayed exactly in tests and research.
"""

from .models import (
    ExitReason,
    MarketQuote,
    PaperExecutionConfig,
    PaperPosition,
    PositionStatus,
    Side,
    TradeIntent,
)
from .paper_engine import PaperEngine

__all__ = [
    "ExitReason",
    "MarketQuote",
    "PaperExecutionConfig",
    "PaperPosition",
    "PositionStatus",
    "Side",
    "TradeIntent",
    "PaperEngine",
]
