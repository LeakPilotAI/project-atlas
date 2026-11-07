from datetime import datetime, timezone

import pandas as pd
import pytest

from scripts.observation_runtime.r7e47cn_yahoo_candles import (
    YahooCandleRefused,
    dataframe_to_candles,
)
from scripts.observation_runtime.r7e47cm_equities_snapshot import (
    build_snapshot,
)


def test_dataframe_conversion_and_snapshot():
    index = pd.DatetimeIndex([
        "2026-10-19 09:30:00-04:00",
        "2026-10-19 09:31:00-04:00",
    ])

    frame = pd.DataFrame(
        {
            "Close": [100.0, 101.0],
            "Volume": [1200, 1500],
        },
        index=index,
    )

    candles = dataframe_to_candles(frame)

    assert len(candles) == 2
    assert candles[-1]["Close"] == 101.0
    assert candles[-1]["timestamp"].tzinfo is not None

    snapshot = build_snapshot(
        "AAPL",
        candles,
        now=datetime(
            2026, 10, 19, 13, 32,
            tzinfo=timezone.utc,
        ),
    )

    assert snapshot["session"] == "REGULAR"
    assert snapshot["price"] == 101.0
    assert snapshot["candle_volume"] == 1500


def test_naive_datetime_index_refused():
    frame = pd.DataFrame(
        {"Close": [100], "Volume": [1000]},
        index=pd.DatetimeIndex(["2026-10-19 09:30"]),
    )

    with pytest.raises(YahooCandleRefused):
        dataframe_to_candles(frame)


def test_empty_dataframe_refused():
    with pytest.raises(YahooCandleRefused):
        dataframe_to_candles(pd.DataFrame())


def test_missing_volume_refused():
    frame = pd.DataFrame(
        {"Close": [100]},
        index=pd.DatetimeIndex([
            "2026-10-19 09:30:00-04:00"
        ]),
    )

    with pytest.raises(YahooCandleRefused):
        dataframe_to_candles(frame)


def test_invalid_rows_filtered():
    frame = pd.DataFrame(
        {
            "Close": [100.0, -1.0],
            "Volume": [1000, 2000],
        },
        index=pd.DatetimeIndex([
            "2026-10-19 09:30:00-04:00",
            "2026-10-19 09:31:00-04:00",
        ]),
    )

    candles = dataframe_to_candles(frame)

    assert len(candles) == 1
    assert candles[0]["Close"] == 100.0
