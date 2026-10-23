"""End-to-end offline equities observation pipeline."""

from __future__ import annotations

from datetime import datetime, timezone

from scripts.observation_runtime.r7e47cl_yahoo_observer import (
    YahooObservationController,
)
from scripts.observation_runtime.r7e47cm_equities_snapshot import (
    build_snapshot,
)
from scripts.observation_runtime.r7e47cn_yahoo_candles import (
    dataframe_to_candles,
)


async def observe_equity(
    symbol,
    *,
    client,
    budget,
    now=None,
):
    controller = YahooObservationController(client, budget)

    observation = await controller.observe(symbol)

    candles = dataframe_to_candles(observation.data, strict=True)

    snapshot = build_snapshot(
        observation.symbol,
        candles,
        now=now if now is not None else datetime.now(timezone.utc),
    )

    return {
        **snapshot,
        "provider": "YAHOO_STYLE_INJECTED",
        "provider_request_count": observation.logical_attempts,
        "wire_request_count": observation.wire_request_count,
        "transport_assurance": "INJECTED_CALLER_RESPONSIBILITY",
        "interval": observation.interval,
        "extended_hours": observation.extended_hours,
        "history_rows": observation.row_count,
        "network_authorized": False,
        "trading_enabled": False,
    }
