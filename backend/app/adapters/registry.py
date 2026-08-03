from typing import Dict, List, Optional

from app.adapters.base import BaseExchangeAdapter
from app.core.logging import get_logger

logger = get_logger("registry")


class AdapterRegistry:
    def __init__(self):
        self._adapters: Dict[str, BaseExchangeAdapter] = {}

    def register(self, adapter: BaseExchangeAdapter) -> None:
        self._adapters[adapter.name] = adapter
        logger.info("Adapter registered", name=adapter.name)

    def get(self, name: str) -> Optional[BaseExchangeAdapter]:
        return self._adapters.get(name)

    def all(self) -> List[BaseExchangeAdapter]:
        return list(self._adapters.values())

    async def connect_all(self) -> None:
        for adapter in self._adapters.values():
            try:
                await adapter.connect()
                logger.info("Adapter connected", name=adapter.name)
            except Exception as e:
                logger.error("Failed to connect adapter", name=adapter.name, error=str(e))

    async def disconnect_all(self) -> None:
        for adapter in self._adapters.values():
            try:
                await adapter.disconnect()
            except Exception as e:
                logger.warning("Error disconnecting adapter", name=adapter.name, error=str(e))


# Global singleton
registry = AdapterRegistry()