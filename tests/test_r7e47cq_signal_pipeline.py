from datetime import datetime, timezone

import pandas as pd
import pytest

from scripts.observation_runtime.r7e47ck_equities_budget import (
    EquitiesObservationBudget,
    EquitiesBudgetRefused,
)
from scripts.observation_runtime.r7e47cq_signal_pipeline import (
    observe_equity_research,
    observe_equity_signals,
)


class FakeYahooClient:
    def __init__(self, frame):
        self.frame = frame
        self.calls = []

    async def history(self, symbol, **kwargs):
        self.calls.append((symbol, kwargs))
        return self.frame


def make_frame():
    return pd.DataFrame(
        {
            "Close": [102.0, 103.0, 105.0],
            "Volume": [1000, 2000, 3000],
        },
        index=pd.DatetimeIndex([
            "2026-10-19 08:00:00-04:00",
            "2026-10-19 09:00:00-04:00",
            "2026-10-19 09:31:00-04:00",
        ]),
    )


def make_budget(tmp_path):
    return EquitiesObservationBudget(
        tmp_path / "budget.sqlite",
        access_approved=True,
        max_attempts=1,
    )


@pytest.mark.asyncio
async def test_complete_signal_pipeline(tmp_path):
    client = FakeYahooClient(make_frame())
    budget = make_budget(tmp_path)

    result = await observe_equity_signals(
        "aapl",
        previous_close=100,
        client=client,
        budget=budget,
        now=datetime(
            2026, 10, 19, 13, 32,
            tzinfo=timezone.utc,
        ),
    )

    assert result["symbol"] == "AAPL"
    assert result["session"] == "REGULAR"
    assert result["price"] == 105.0
    assert result["previous_close"] == 100.0
    assert result["change_from_previous_close_percent"] == 5.0
    assert result["premarket_gap_percent"] == 3.0
    assert result["premarket_volume"] == 3000
    assert result["regular_volume"] == 3000
    assert result["relative_volume"] is None
    assert result["relative_volume_status"] == "BASELINE_REQUIRED"
    assert result["network_authorized"] is False
    assert result["trading_enabled"] is False
    assert budget.remaining() == 0
    assert len(client.calls) == 1


def test_research_bridge_integration_uses_offline_validation():
    now = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
    result = observe_equity_research(
        quote_observation={
            "symbol": "AAPL",
            "price": 102.5,
            "source": "ROBINHOOD",
            "session": "PRE_MARKET",
            "effective_timestamp": "2026-10-19T07:59:00-04:00",
            "research_only": True,
            "trading_enabled": False,
        },
        candle_data=[
            {"timestamp": datetime.fromisoformat("2026-10-19T07:59:00-04:00"), "Close": 101.0, "Volume": 1000},
            {"timestamp": datetime.fromisoformat("2026-10-19T08:00:00-04:00"), "Close": 102.5, "Volume": 2000},
        ],
        previous_close=100.0,
        now=now,
    )

    assert result["symbol"] == "AAPL"
    assert result["research_only"] is True
    assert result["network_authorized"] is False
    assert result["offline_only"] is True


@pytest.mark.asyncio
async def test_exhausted_budget_blocks_pipeline(tmp_path):
    client = FakeYahooClient(make_frame())
    budget = make_budget(tmp_path)
    budget.consume_before_attempt()

    with pytest.raises(EquitiesBudgetRefused):
        await observe_equity_signals(
            "AAPL",
            previous_close=100,
            client=client,
            budget=budget,
            now=datetime(
                2026, 10, 19, 13, 32,
                tzinfo=timezone.utc,
            ),
        )

    assert client.calls == []
