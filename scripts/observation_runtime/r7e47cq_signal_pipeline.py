"""Offline end-to-end equities observation with market signals."""

from __future__ import annotations

from datetime import datetime, timezone

from scripts.observation_runtime.r7e47cl_yahoo_observer import (
    YahooObservationController,
)
from scripts.observation_runtime.r7e47cn_yahoo_candles import (
    dataframe_to_candles,
)
from scripts.observation_runtime.r7e47cp_market_signals import (
    analyze_market,
)
from scripts.observation_runtime.r7e47de_research_bridge import (
    bridge_research,
)


async def observe_equity_signals(
    symbol,
    *,
    previous_close,
    client,
    budget,
    now=None,
    quote_observation=None,
    candle_data=None,
    historical_candles=None,
    minimum_baseline_sessions=5,
):
    effective_now = now if now is not None else datetime.now(timezone.utc)

    if quote_observation is not None or candle_data is not None:
        if quote_observation is None or candle_data is None:
            raise ValueError("quote_observation and candle_data must both be supplied together")
        result = bridge_research(
            quote_observation,
            candle_data,
            previous_close,
            now=effective_now,
            historical_candles=historical_candles,
            minimum_baseline_sessions=minimum_baseline_sessions,
        )
        return {
            **result,
            "provider": str(quote_observation.get("source") or "CALLER_SUPPLIED_QUOTE"),
            "interval": "research_bridge",
            "extended_hours": result.get("session") in {"PRE_MARKET", "AFTER_HOURS"},
            "history_rows": len(candle_data),
            "network_authorized": False,
            "trading_enabled": False,
        }

    controller = YahooObservationController(client, budget)
    observation = await controller.observe(symbol)

    candles = dataframe_to_candles(observation.data, strict=True)

    result = analyze_market(
        observation.symbol,
        candles,
        previous_close,
        now=effective_now,
        historical_candles=historical_candles,
        minimum_baseline_sessions=minimum_baseline_sessions,
    )

    return {
        **result,
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


def observe_equity_research(*, quote_observation, candle_data, previous_close, now=None,
                            historical_candles=None, minimum_baseline_sessions=5):
    return bridge_research(
        quote_observation,
        candle_data,
        previous_close,
        now=now if now is not None else datetime.now(timezone.utc),
        historical_candles=historical_candles,
        minimum_baseline_sessions=minimum_baseline_sessions,
    )
