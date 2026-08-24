"""Adapter base types."""

from __future__ import annotations

from typing import Any, Optional, Protocol


class MarketAdapter(Protocol):
    """Protocol for exchange adapters."""

    name: str

    async def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def get_all_tickers(self) -> list[Any]: ...

    async def get_candles(
        self,
        symbol: str,
        interval: str = "15m",
        lookback: int = 100,
    ) -> list[dict[str, float]]: ...


class BaseExchangeAdapter:
    """
    Concrete base class used by registry / older imports.
    Subclass or treat HyperliquidAdapter as standalone.
    """

    name: str = "base"

    def __init__(self) -> None:
        self._connected = False

    async def connect(self) -> None:
        self._connected = True

    async def close(self) -> None:
        self._connected = False

    async def get_all_tickers(self) -> list[Any]:
        raise NotImplementedError

    async def get_candles(
        self,
        symbol: str,
        interval: str = "15m",
        lookback: int = 100,
    ) -> list[dict[str, float]]:
        return []


# Back-compat aliases
ExchangeAdapter = BaseExchangeAdapter