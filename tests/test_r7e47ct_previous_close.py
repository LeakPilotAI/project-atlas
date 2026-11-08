from datetime import datetime, timezone

import pandas as pd
import pytest

from scripts.observation_runtime.r7e47ct_previous_close import (
    PreviousCloseRefused,
    extract_previous_close,
)


def test_prior_friday_close_used_on_monday():
    frame = pd.DataFrame(
        {"Close": [100.0, 105.0]},
        index=pd.DatetimeIndex([
            "2026-10-16 00:00:00-04:00",
            "2026-10-19 00:00:00-04:00",
        ]),
    )

    result = extract_previous_close(
        frame,
        observation_time=datetime(
            2026, 10, 19, 13, 32,
            tzinfo=timezone.utc,
        ),
    )

    assert result["previous_close"] == 100.0
    assert result["previous_session_date"] == "2026-10-16"


def test_today_candle_not_used():
    frame = pd.DataFrame(
        {"Close": [105.0]},
        index=pd.DatetimeIndex([
            "2026-10-19 00:00:00-04:00"
        ]),
    )

    with pytest.raises(PreviousCloseRefused):
        extract_previous_close(
            frame,
            observation_time=datetime(
                2026, 10, 19, 13, 32,
                tzinfo=timezone.utc,
            ),
        )


def test_naive_daily_timestamp_refused():
    frame = pd.DataFrame(
        {"Close": [100.0]},
        index=pd.DatetimeIndex(["2026-10-16"]),
    )

    with pytest.raises(PreviousCloseRefused):
        extract_previous_close(
            frame,
            observation_time=datetime(
                2026, 10, 19, 13, 32,
                tzinfo=timezone.utc,
            ),
        )


def test_invalid_prior_close_refused():
    frame = pd.DataFrame(
        {"Close": [-100.0]},
        index=pd.DatetimeIndex([
            "2026-10-16 00:00:00-04:00"
        ]),
    )

    with pytest.raises(PreviousCloseRefused):
        extract_previous_close(
            frame,
            observation_time=datetime(
                2026, 10, 19, 13, 32,
                tzinfo=timezone.utc,
            ),
        )
