import asyncio

from app.adapters.axiom_perps import AxiomPerpAdapter


class FakeAxiomPerpAdapter(AxiomPerpAdapter):
    def __init__(self):
        super().__init__()
        self.calls = []

    async def _post(self, body):
        self.calls.append(dict(body))
        t = body.get("type")
        dex = body.get("dex", "")
        if t == "perpDexs":
            return [None, {"name": "xyz"}]
        if t == "meta":
            if dex == "xyz":
                return {"universe": [{"name": "AAPL"}, {"name": "NVDA"}]}
            return {"universe": [{"name": "BTC"}, {"name": "ETH"}]}
        if t == "metaAndAssetCtxs":
            if dex == "xyz":
                return [
                    {"universe": [{"name": "AAPL"}]},
                    [{"markPx": "232.5", "dayNtlVlm": "1200000", "openInterest": "450000", "funding": "0.0001"}],
                ]
            return [
                {"universe": [{"name": "BTC"}]},
                [{"markPx": "100000", "dayNtlVlm": "9000000", "openInterest": "3000000", "funding": "0.00005"}],
            ]
        raise AssertionError(body)


def test_axiom_adapter_discovers_native_and_hip3_markets():
    adapter = FakeAxiomPerpAdapter()
    names = asyncio.run(adapter.refresh_universe())
    assert names == ["BTC", "ETH", "xyz:AAPL", "xyz:NVDA"]
    assert adapter.universe_names() == names


def test_axiom_adapter_reads_mark_prices_across_dexes():
    adapter = FakeAxiomPerpAdapter()
    asyncio.run(adapter.refresh_universe())
    rows = asyncio.run(adapter.get_all_tickers())
    by_symbol = {row.symbol: row for row in rows}
    assert by_symbol["BTC"].price == 100000.0
    assert by_symbol["xyz:AAPL"].price == 232.5
    assert by_symbol["xyz:AAPL"].exchange == "axiom_perps"


def test_registry_key_remains_compatible_with_existing_manual_service():
    assert AxiomPerpAdapter.name == "hyperliquid"
