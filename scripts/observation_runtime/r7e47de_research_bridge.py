"""Offline research-analysis bridge for quote observations and minute candles.

This module intentionally does not fetch data or issue network requests. It validates
an already supplied quote observation together with separately supplied candle data,
then reuses the offline market-signal logic for a fail-closed, research-only signal.
"""

from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any
from zoneinfo import ZoneInfo

from app.investment.offline_research import (
    ResearchInputRefused as ResearchBridgeRefused,
)
from app.investment.offline_research import (
    close_reference,
    equity_session,
    symbol_identity,
)

from scripts.observation_runtime.r7e47cm_equities_snapshot import (
    build_snapshot,
)
from scripts.observation_runtime.r7e47cp_market_signals import analyze_market

EASTERN = ZoneInfo("America/New_York")


def _normalize_symbol(value: Any) -> str:
    return symbol_identity(value)


def _coerce_utc(value: Any, *, field_name: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ResearchBridgeRefused(f"Invalid {field_name}") from exc
    if not isinstance(value, datetime):
        raise ResearchBridgeRefused(f"{field_name} must be a timezone-aware datetime")
    if value.tzinfo is None:
        raise ResearchBridgeRefused(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _coerce_positive_float(value: Any, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise ResearchBridgeRefused(f"Invalid {field_name}")
    try:
        float_value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ResearchBridgeRefused(f"Invalid {field_name}") from exc
    if not isfinite(float_value) or float_value <= 0:
        raise ResearchBridgeRefused(f"Invalid {field_name}")
    return float_value


def _resolve_inputs(*args, **kwargs):
    allowed = {"observation", "candles", "previous_close", "now", "symbol",
               "quote_observation", "candle_data", "reference_close", "current_time",
               "max_quote_age_seconds", "max_candle_age_seconds", "historical_candles",
               "minimum_baseline_sessions"}
    if set(kwargs) - allowed:
        raise TypeError("Unknown research bridge arguments")
    bound = ("observation", "candles", "previous_close")[:len(args)]
    if len(args) == 4:
        bound = ("observation", "candles", "previous_close")
    if any(k in kwargs for k in bound):
        raise TypeError("Conflicting positional and keyword research inputs")
    for primary, alias in (("observation", "quote_observation"), ("candles", "candle_data"),
                           ("previous_close", "reference_close"), ("now", "current_time")):
        if primary in kwargs and alias in kwargs:
            raise TypeError("Conflicting research input aliases")
    if len(args) > 4 or (len(args) == 4 and not isinstance(args[0], str)):
        raise TypeError("Unsupported research bridge arguments")
    observation = kwargs.get("observation")
    candles = kwargs.get("candles")
    previous_close = kwargs.get("previous_close")
    now = kwargs.get("now")

    if len(args) == 3:
        observation, candles, previous_close = args
    elif len(args) == 4 and isinstance(args[0], str):
        symbol_hint, observation, candles, previous_close = args
        if isinstance(observation, dict) and "symbol" in observation and _normalize_symbol(observation["symbol"]) != _normalize_symbol(symbol_hint):
            raise ResearchBridgeRefused("Symbol hint conflicts with observation")
        if isinstance(observation, dict) and "symbol" not in observation:
            observation = {**observation, "symbol": symbol_hint}
    elif len(args) == 1:
        observation = args[0]
    elif len(args) == 2:
        observation, candles = args
    elif len(args) == 0:
        pass

    if observation is None and kwargs.get("quote_observation") is not None:
        observation = kwargs["quote_observation"]
    if candles is None and kwargs.get("candle_data") is not None:
        candles = kwargs["candle_data"]
    if previous_close is None and kwargs.get("reference_close") is not None:
        previous_close = kwargs["reference_close"]
    if now is None and kwargs.get("current_time") is not None:
        now = kwargs["current_time"]

    if observation is None:
        raise TypeError("observation is required")
    if candles is None:
        raise TypeError("candles are required")
    if previous_close is None:
        raise TypeError("previous_close is required")

    return observation, candles, previous_close, now


def _quote_session_for(ts: datetime) -> str:
    return equity_session(ts)


def bridge_research(*args, **kwargs):
    """Validate and bridge a quote observation and minute candles into a signal.

    The bridge accepts a quote observation dict and the associated minute candles as
    separate, caller-supplied inputs. It refuses unsafe or mismatched data instead of
    inventing a close, baseline, or RVOL.
    """
    observation, candles, previous_close, now = _resolve_inputs(*args, **kwargs)
    now = now if now is not None else datetime.now(timezone.utc)
    now_utc = _coerce_utc(now, field_name="Current time")

    if not isinstance(observation, dict):
        raise ResearchBridgeRefused("Observation must be a mapping")
    if not isinstance(candles, (list, tuple)) or not candles:
        raise ResearchBridgeRefused("No candle data supplied")

    for candle in candles:
        if isinstance(candle, dict) and "symbol" in candle:
            candle_symbol = _normalize_symbol(candle["symbol"])
            expected_symbol = _normalize_symbol(observation.get("symbol") or kwargs.get("symbol"))
            if candle_symbol != expected_symbol:
                raise ResearchBridgeRefused("Symbol mismatch between observation and candles")

    symbol = _normalize_symbol(observation.get("symbol") or kwargs.get("symbol"))
    if kwargs.get("symbol") is not None and _normalize_symbol(kwargs["symbol"]) != symbol:
        raise ResearchBridgeRefused("Symbol hint conflicts with observation")
    quote_price = _coerce_positive_float(observation.get("price"), field_name="Quote price")
    quote_source = observation.get("source") or observation.get("provider")
    if not isinstance(quote_source, str) or not quote_source.strip() or len(quote_source) > 64 or quote_source.upper() == "UNKNOWN":
        raise ResearchBridgeRefused("Observation source is required")

    quote_ts_raw = observation.get("effective_timestamp")
    if quote_ts_raw is None:
        quote_ts_raw = observation.get("timestamp")
    if quote_ts_raw is None:
        raise ResearchBridgeRefused("Observation timestamp is required")
    quote_ts = _coerce_utc(quote_ts_raw, field_name="Quote timestamp")
    if quote_ts > now_utc:
        raise ResearchBridgeRefused("Observation timestamp is in the future")

    observation_session = str(observation.get("session") or _quote_session_for(quote_ts)).upper()
    observation_session = "AFTER_HOURS" if observation_session == "POST_MARKET" else observation_session
    if observation_session != _quote_session_for(quote_ts):
        raise ResearchBridgeRefused("Declared session does not match quote timestamp")
    if observation_session not in {"PRE_MARKET", "REGULAR", "AFTER_HOURS", "POST_MARKET"}:
        raise ResearchBridgeRefused("Unsupported observation session")

    observation_age_seconds = (now_utc - quote_ts).total_seconds()
    if observation_age_seconds < 0:
        raise ResearchBridgeRefused("Observation timestamp is in the future")
    max_quote_age = kwargs.get("max_quote_age_seconds", 900.0)
    if type(max_quote_age) not in (int, float) or not isfinite(max_quote_age) or max_quote_age <= 0:
        raise ResearchBridgeRefused("Invalid quote freshness threshold")
    if observation_age_seconds > float(max_quote_age):
        raise ResearchBridgeRefused("Quote observation is stale")

    # Preserve existing metadata, but refuse a missing or invalid previous close.
    if isinstance(previous_close, dict) and "symbol" in previous_close and _normalize_symbol(previous_close["symbol"]) != symbol:
        raise ResearchBridgeRefused("Previous close symbol mismatch")
    _, reference_status, _ = close_reference(previous_close, observation_time=quote_ts)
    symbol_from_candles = kwargs.get("symbol")
    if symbol_from_candles is not None:
        symbol = _normalize_symbol(symbol_from_candles)

    normalized_candles = []
    for candle in candles:
        if not isinstance(candle, dict):
            normalized_candles.append(candle)
            continue
        normalized = dict(candle)
        timestamp = normalized.get("timestamp")
        if isinstance(timestamp, str):
            try:
                normalized["timestamp"] = datetime.fromisoformat(timestamp)
            except ValueError as exc:
                raise ResearchBridgeRefused("Invalid candle timestamp") from exc
        normalized_candles.append(normalized)

    snapshot = build_snapshot(symbol, normalized_candles, now=now_utc, max_age_seconds=kwargs.get("max_candle_age_seconds", 180.0))
    snapshot_symbol = _normalize_symbol(snapshot["symbol"])
    if snapshot_symbol != symbol:
        raise ResearchBridgeRefused("Symbol mismatch between observation and candles")

    if observation.get("symbol") is not None and _normalize_symbol(observation["symbol"]) != snapshot_symbol:
        raise ResearchBridgeRefused("Observation symbol does not match candle symbol")

    candle_ts = _coerce_utc(datetime.fromisoformat(snapshot["timestamp"]), field_name="Candles timestamp")
    if candle_ts > now_utc:
        raise ResearchBridgeRefused("Candles contain future-dated data")

    snapshot_session = str(snapshot.get("session") or "").upper()
    if snapshot_session != observation_session:
        raise ResearchBridgeRefused("Observation and candles are from incompatible sessions")

    quote_local = quote_ts.astimezone(EASTERN)
    candle_local = candle_ts.astimezone(EASTERN)
    if quote_local.date() != candle_local.date():
        raise ResearchBridgeRefused("Observation and candles are from different trading dates")

    if observation.get("research_only", True) is not True or observation.get("trading_enabled", False) is not False:
        raise ResearchBridgeRefused("Observation must be strictly research-only")

    if observation.get("execution_authority") is not None and bool(observation.get("execution_authority")):
        raise ResearchBridgeRefused("Execution authority is not allowed in research-only bridge")

    signal = analyze_market(symbol, normalized_candles, previous_close, now=now_utc,
                            max_age_seconds=kwargs.get("max_candle_age_seconds", 180.0),
                            historical_candles=kwargs.get("historical_candles"),
                            minimum_baseline_sessions=kwargs.get("minimum_baseline_sessions", 5))
    signal["symbol"] = symbol
    signal["source"] = quote_source
    signal["provider"] = quote_source
    signal["quote_source"] = quote_source
    signal["candle_source"] = snapshot.get("source", "CALLER_SUPPLIED_CANDLES")
    signal["quote_price"] = round(float(quote_price), 6)
    signal["quote_timestamp"] = quote_ts.isoformat()
    signal["quote_session"] = observation_session
    signal["quote_age_seconds"] = round(observation_age_seconds, 3)
    signal["candle_timestamp"] = candle_ts.isoformat()
    signal["trading_enabled"] = False
    signal["research_only"] = True
    signal["execution_authority"] = False
    signal["previous_close_source"] = reference_status
    signal["relative_volume_status"] = signal.get("relative_volume_status", "BASELINE_REQUIRED")
    signal["provider_request_count"] = 0
    signal["wire_request_count"] = 0
    signal["transport_assurance"] = "NO_TRANSPORT_INVOKED"
    signal["network_authorized"] = False
    signal["offline_only"] = True

    return signal


def analyze_research(*args, **kwargs):
    return bridge_research(*args, **kwargs)


def build_research_signal(*args, **kwargs):
    return bridge_research(*args, **kwargs)


__all__ = [
    "ResearchBridgeRefused",
    "analyze_research",
    "bridge_research",
    "build_research_signal",
]
