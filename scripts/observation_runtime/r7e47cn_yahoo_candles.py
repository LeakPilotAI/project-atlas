"""Convert caller-supplied Yahoo DataFrames into timestamped candles."""

from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite


class YahooCandleRefused(ValueError):
    pass


def dataframe_to_candles(frame, *, strict=False):
    if frame is None or not hasattr(frame, "iterrows"):
        raise YahooCandleRefused("Expected a pandas-style DataFrame")

    if getattr(frame, "empty", True):
        raise YahooCandleRefused("Yahoo history is empty")

    columns = getattr(frame, "columns", [])

    if "Close" not in columns or "Volume" not in columns:
        raise YahooCandleRefused("Required candle columns missing")

    candles = []

    for index, row in frame.iterrows():
        if not hasattr(index, "to_pydatetime"):
            continue

        timestamp = index.to_pydatetime()

        if not isinstance(timestamp, datetime):
            continue

        if timestamp.tzinfo is None:
            continue

        if strict and (isinstance(row["Close"], bool) or isinstance(row["Volume"], bool)):
            raise YahooCandleRefused("Boolean candle values refused")

        try:
            close = float(row["Close"])
            volume = float(row["Volume"])
        except (TypeError, ValueError, OverflowError):
            continue

        if not isfinite(close) or close <= 0:
            continue

        if not isfinite(volume) or volume < 0:
            continue

        candles.append({
            "timestamp": timestamp.astimezone(timezone.utc),
            "Close": close,
            "Volume": volume,
        })

    if not candles:
        raise YahooCandleRefused(
            "No valid timestamped Yahoo candles"
        )

    if strict and len(candles) != len(frame):
        raise YahooCandleRefused("Invalid rows cannot be silently removed from research history")

    return sorted(
        candles,
        key=lambda candle: candle["timestamp"],
    )
