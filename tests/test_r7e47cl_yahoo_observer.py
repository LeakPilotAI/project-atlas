import pytest

from scripts.observation_runtime.r7e47ck_equities_budget import (
    EquitiesObservationBudget,
    EquitiesBudgetRefused,
)
from scripts.observation_runtime.r7e47cl_yahoo_observer import (
    YahooObservationController,
    YahooObservationRefused,
)


class FakeYahooClient:
    def __init__(self):
        self.calls = []

    async def history(self, symbol, **kwargs):
        self.calls.append((symbol, kwargs))
        return [
            {"Close": 100.0, "Volume": 1200},
            {"Close": 101.0, "Volume": 1500},
        ]


def budget(tmp_path, limit=1):
    return EquitiesObservationBudget(
        tmp_path / "budget.sqlite",
        access_approved=True,
        max_attempts=limit,
    )


@pytest.mark.asyncio
async def test_extended_hours_request_contract(tmp_path):
    client = FakeYahooClient()
    controller = YahooObservationController(
        client, budget(tmp_path)
    )

    result = await controller.observe("aapl")

    assert result.symbol == "AAPL"
    assert result.interval == "1m"
    assert result.extended_hours is True
    assert result.row_count == 2

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
async def test_exhausted_budget_blocks_client(tmp_path):
    client = FakeYahooClient()
    ledger = budget(tmp_path)
    ledger.consume_before_attempt()

    controller = YahooObservationController(
        client, ledger
    )

    with pytest.raises(EquitiesBudgetRefused):
        await controller.observe("AAPL")

    assert client.calls == []


@pytest.mark.asyncio
async def test_controller_single_use(tmp_path):
    client = FakeYahooClient()
    controller = YahooObservationController(
        client, budget(tmp_path)
    )

    await controller.observe("MSFT")

    with pytest.raises(YahooObservationRefused):
        await controller.observe("MSFT")

    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_invalid_symbol_no_budget_charge(tmp_path):
    client = FakeYahooClient()
    ledger = budget(tmp_path)
    controller = YahooObservationController(client, ledger)

    with pytest.raises(YahooObservationRefused):
        await controller.observe("INVALID SYMBOL!")

    assert ledger.remaining() == 1
    assert client.calls == []


@pytest.mark.asyncio
async def test_live_refused(tmp_path):
    client = FakeYahooClient()
    controller = YahooObservationController(
        client, budget(tmp_path)
    )

    with pytest.raises(YahooObservationRefused):
        await controller.observe_live("AAPL")

    assert client.calls == []
