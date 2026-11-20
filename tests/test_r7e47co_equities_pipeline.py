from datetime import datetime, timezone

import pandas as pd
import pytest

from scripts.observation_runtime.r7e47ck_equities_budget import (
    EquitiesObservationBudget,
    EquitiesBudgetRefused,
)
from scripts.observation_runtime.r7e47co_equities_pipeline import (
    observe_equity,
)
from scripts.observation_runtime.r7e47cm_equities_snapshot import (
    SnapshotRefused,
)


class FakeYahooClient:
    def __init__(self, frame):
        self.frame = frame
        self.calls = []

    async def history(self, symbol, **kwargs):
        self.calls.append((symbol, kwargs))
        return self.frame


def make_budget(tmp_path):
    return EquitiesObservationBudget(
        tmp_path / "budget.sqlite",
        access_approved=True,
        max_attempts=1,
    )


def make_frame(timestamp, price=101.0, volume=1500):
    return pd.DataFrame(
        {"Close": [price], "Volume": [volume]},
        index=pd.DatetimeIndex([timestamp]),
    )


@pytest.mark.asyncio
async def test_regular_session_end_to_end(tmp_path):
    now = datetime(2026, 10, 19, 13, 32, tzinfo=timezone.utc)
    frame = make_frame("2026-10-19 09:31:00-04:00")
    client = FakeYahooClient(frame)
    budget = make_budget(tmp_path)

    result = await observe_equity(
        "aapl",
        client=client,
        budget=budget,
        now=now,
    )

    assert result["symbol"] == "AAPL"
    assert result["session"] == "REGULAR"
    assert result["price"] == 101.0
    assert result["candle_volume"] == 1500
    assert result["freshness"] == "FRESH"
    assert result["extended_hours"] is True
    assert result["network_authorized"] is False
    assert result["trading_enabled"] is False
    assert budget.remaining() == 0

    assert client.calls == [
        (
            "AAPL",
            {
                "period": "5d",
                "interval": "1m",
                "prepost": True,
            },
        )
    ]


@pytest.mark.asyncio
async def test_premarket_end_to_end(tmp_path):
    now = datetime(2026, 10, 19, 12, 2, tzinfo=timezone.utc)
    frame = make_frame("2026-10-19 08:01:00-04:00")
    client = FakeYahooClient(frame)

    result = await observe_equity(
        "MSFT",
        client=client,
        budget=make_budget(tmp_path),
        now=now,
    )

    assert result["session"] == "PRE_MARKET"


@pytest.mark.asyncio
async def test_stale_data_rejected(tmp_path):
    now = datetime(2026, 10, 19, 14, 0, tzinfo=timezone.utc)
    frame = make_frame("2026-10-19 09:30:00-04:00")
    client = FakeYahooClient(frame)

    with pytest.raises(SnapshotRefused):
        await observe_equity(
            "AAPL",
            client=client,
            budget=make_budget(tmp_path),
            now=now,
        )


@pytest.mark.asyncio
async def test_budget_exhaustion_blocks_second_call(tmp_path):
    now = datetime(2026, 10, 19, 13, 32, tzinfo=timezone.utc)
    frame = make_frame("2026-10-19 09:31:00-04:00")
    client = FakeYahooClient(frame)
    budget = make_budget(tmp_path)

    await observe_equity(
        "AAPL",
        client=client,
        budget=budget,
        now=now,
    )

    with pytest.raises(EquitiesBudgetRefused):
        await observe_equity(
            "MSFT",
            client=client,
            budget=budget,
            now=now,
        )

    assert len(client.calls) == 1
