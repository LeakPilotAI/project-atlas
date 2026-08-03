from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class NormalizedTicker(BaseModel):
    symbol: str
    exchange: str
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume_24h: float = 0.0
    open_interest: float = 0.0
    funding_rate: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    raw: dict = Field(default_factory=dict)


class BaseExchangeAdapter(ABC):
    name: str = "base"

    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        ...

    @abstractmethod
    async def get_all_tickers(self) -> List[NormalizedTicker]:
        ...

    @abstractmethod
    async def get_candles(
        self, symbol: str, interval: str = "5m", limit: int = 100
    ) -> List[dict]:
        ...