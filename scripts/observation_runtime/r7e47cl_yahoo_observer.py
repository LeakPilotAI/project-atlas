"""Offline-testable equities observer.

An injected client supplies history data. This module does not create
network clients or authorize live Yahoo requests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scripts.observation_runtime.r7e47ck_equities_budget import (
    EquitiesObservationBudget,
)


class YahooObservationRefused(RuntimeError):
    pass


@dataclass(frozen=True)
class YahooObservation:
    symbol: str
    source: str
    interval: str
    extended_hours: bool
    row_count: int
    data: Any
    logical_attempts: int = 1
    wire_request_count: int | None = None
    provider_authorized: bool = False


class YahooObservationController:
    def __init__(
        self,
        client: Any,
        budget: EquitiesObservationBudget,
    ) -> None:
        if type(budget) is not EquitiesObservationBudget:
            raise YahooObservationRefused(
                "A durable equities budget is required"
            )

        if client is None or not callable(
            getattr(client, "history", None)
        ):
            raise YahooObservationRefused(
                "A history-capable client is required"
            )

        self.client = client
        self.budget = budget
        self._used = False

    async def observe(
        self,
        symbol: str,
    ) -> YahooObservation:
        if self._used:
            raise YahooObservationRefused(
                "Controller already used"
            )

        if not isinstance(symbol, str):
            raise YahooObservationRefused(
                "Invalid equity symbol"
            )

        symbol = symbol.strip().upper()

        if not symbol or len(symbol) > 12:
            raise YahooObservationRefused(
                "Invalid equity symbol"
            )

        if not all(
            char.isascii() and (
                char.isalnum() or char in ".-"
            )
            for char in symbol
        ):
            raise YahooObservationRefused(
                "Unsupported equity symbol"
            )

        self._used = True

        # Charges one high-level history operation, not each HTTP request.
        self.budget.consume_before_attempt()

        result = await self.client.history(
            symbol,
            period="5d",
            interval="1m",
            prepost=True,
        )

        return YahooObservation(
            symbol=symbol,
            source="INJECTED_CLIENT",
            interval="1m",
            extended_hours=True,
            row_count=len(result),
            data=result,
        )

    async def observe_live(self, symbol: str):
        raise YahooObservationRefused(
            "Live Yahoo requests are not authorized"
        )
