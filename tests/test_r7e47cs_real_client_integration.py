"""Real Atlas Yahoo client integration, with provider I/O mocked."""

from datetime import datetime, timezone

import pandas as pd
import pytest

from app.investment.yfinance_client import YFinanceClient
from scripts.observation_runtime.r7e47ck_equities_budget import (
    EquitiesObservationBudget,
)
from scripts.observation_runtime.r7e47cq_signal_pipeline import (
    observe_equity_signals,
)


class OfflineTicker:
    def __init__(self, frame):
        self.frame = frame
        self.calls = []

    def history(self, **kwargs):
        self.calls.append(kwargs)
        return self.frame


@pytest.mark.asyncio
async def test_real_yahoo_client_offline_integration(
    tmp_path,
    monkeypatch,
):
    frame = pd.DataFrame(
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

    ticker = OfflineTicker(frame)

    client = YFinanceClient()

    monkeypatch.setattr(
        client,
        "_ticker",
        lambda symbol: ticker,
    )

    budget = EquitiesObservationBudget(
        tmp_path / "budget.sqlite",
        access_approved=True,
        max_attempts=1,
    )

    result = await observe_equity_signals(
        "AAPL",
        previous_close=100,
        client=client,
        budget=budget,
        now=datetime(
            2026, 10, 19, 13, 32,
            tzinfo=timezone.utc,
        ),
    )

    assert result["symbol"] == "AAPL"
    assert result["price"] == 105.0
    assert result["session"] == "REGULAR"
    assert result["premarket_gap_percent"] == 3.0
    assert result["premarket_volume"] == 3000
    assert result["regular_volume"] == 3000
    assert result["change_from_previous_close_percent"] == 5.0
    assert result["network_authorized"] is False
    assert result["trading_enabled"] is False

    assert len(ticker.calls) == 1
    assert ticker.calls[0]["interval"] == "1m"
    assert ticker.calls[0]["prepost"] is True
    assert ticker.calls[0]["auto_adjust"] is False
    assert ticker.calls[0]["period"] == "5d"

    assert budget.remaining() == 0
