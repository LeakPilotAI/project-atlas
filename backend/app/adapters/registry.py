"""Exchange adapter registry."""

from __future__ import annotations

from typing import Any, Optional

from app.adapters.base import BaseExchangeAdapter, MarketAdapter
from app.core.logging import get_logger

logger = get_logger("registry")


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, Any] = {}

    def register(self, adapter: Any) -> None:
        name = getattr(adapter, "name", None) or adapter.__class__.__name__.lower()
        self._adapters[str(name).lower()] = adapter
        logger.info("Adapter registered", name=name)

    def get(self, name: str) -> Optional[Any]:
        return self._adapters.get(name.lower())

    def all(self) -> list[Any]:
        return list(self._adapters.values())

    def names(self) -> list[str]:
        return list(self._adapters.keys())

    async def connect_all(self) -> None:
        for name, adapter in self._adapters.items():
            try:
                if hasattr(adapter, "connect"):
                    await adapter.connect()
                    logger.info("Adapter connected", name=name)
            except Exception as e:
                logger.error("Adapter connect failed", name=name, error=str(e))

    async def close_all(self) -> None:
        for name, adapter in self._adapters.items():
            try:
                if hasattr(adapter, "close"):
                    await adapter.close()
            except Exception as e:
                logger.warning("Adapter close failed", name=name, error=str(e))


registry = AdapterRegistry()