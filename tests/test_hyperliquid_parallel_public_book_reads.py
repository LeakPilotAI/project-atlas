"""Bounded parallel Hyperliquid public order-book read tests, no external HTTP.

Two actual durable SQLite request-budget attempts are consumed for each simulated
source observation; finance, wallet, private endpoints and startup remain closed.
"""
import asyncio
from copy import deepcopy

import pytest

from app.adapters import hyperliquid_gate_registry
from app.adapters.hyperliquid import (
    INFO_URL, HyperliquidAdapter, HyperliquidPublicBookAdmissionRefused,
)
from app.adapters.hyperliquid_request_gate import HyperliquidRequestGate
from test_hyperliquid_public_book import inputs


class _Reply:
    def __init__(self, data):
        self.data = deepcopy(data)

    def raise_for_status(self):
        pass

    def json(self):
        return deepcopy(self.data)


class _ParallelPublicClient:
    def __init__(self, metadata, book):
        self.metadata, self.book = deepcopy(metadata), deepcopy(book)
        self.calls = []
        self.both_started = asyncio.Event()
        self.closed = False

    async def aclose(self):
        self.closed = True

    async def post(self, url, json):
        assert url == INFO_URL
        self.calls.append(deepcopy(json))
        if len(self.calls) >= 2:
            self.both_started.set()
        # A sequential implementation times out: the first HTTP response
        # deliberately waits for the second to BEGIN.
        await asyncio.wait_for(self.both_started.wait(), timeout=0.6)
        return _Reply(self.metadata if json["type"] == "metaAndAssetCtxs" else self.book)


def _setup(monkeypatch, tmp_path, client):
    gate = HyperliquidRequestGate(
        tmp_path / "only-two-requests.sqlite",
        rights_approved=True, budget_approved=True, max_attempts=2,
    )
    # Synthetic entitlement flags are fixture-only, NOT real provider grants.
    monkeypatch.setattr(hyperliquid_gate_registry, "_gate", gate)
    adapter = HyperliquidAdapter()
    adapter._client = client
    return adapter, gate


@pytest.mark.asyncio
async def test_two_public_reads_overlap_and_consume_two_durable_attempts(monkeypatch, tmp_path):
    metadata, book = inputs()
    client = _ParallelPublicClient(metadata, book)
    adapter, gate = _setup(monkeypatch, tmp_path, client)
    times = iter([99999, 100001])
    parsed = await asyncio.wait_for(
        adapter.paper_execution_observation("BTC", clock_ms=lambda: next(times)), timeout=2
    )
    assert gate.remaining() == 0
    assert client.both_started.is_set()
    assert client.calls == [
        {"type": "metaAndAssetCtxs"}, {"type": "l2Book", "coin": "BTC"}
    ]
    assert parsed["bid"] == "100" and parsed["ask"] == "101"
    assert parsed["market_book_validated"] is True
    assert parsed["financial_execution_authorized"] is False
    assert parsed["startup_authorized"] is False
    assert parsed["fee_schedule"] is None
    assert parsed["historical_settlement_oracle"] is None
    assert adapter.paper_source_snapshot()["facts"]["books"]["BTC"]["parsed"] == parsed
    await adapter.close()


@pytest.mark.asyncio
async def test_any_public_response_failure_cancels_sibling_and_does_not_publish(
    monkeypatch, tmp_path,
):
    class FailingClient:
        def __init__(self):
            self.started = asyncio.Event()
            self.cancelled = False
            self.calls = []

        async def post(self, url, json):
            self.calls.append(deepcopy(json))
            if json["type"] == "metaAndAssetCtxs":
                self.started.set()
                try:
                    await asyncio.Event().wait()  # Must be cancelled on book failure.
                except asyncio.CancelledError:
                    self.cancelled = True
                    raise
            await self.started.wait()
            raise RuntimeError("SYNTHETIC_BOOK_PROVIDER_FAILURE")

    client = FailingClient()
    adapter, gate = _setup(monkeypatch, tmp_path, client)
    with pytest.raises(RuntimeError, match="SYNTHETIC_BOOK_PROVIDER_FAILURE"):
        await asyncio.wait_for(adapter.paper_execution_observation(
            "BTC", clock_ms=lambda: 99999), timeout=2)
    assert gate.remaining() == 0
    assert len(client.calls) == 2
    assert client.cancelled is True
    assert adapter.paper_source_snapshot()["facts"]["books"] == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("damage,reason", [
    ("stale", "BOOK_TIMESTAMP_STALE"),
    ("future", "BOOK_TIMESTAMP_FUTURE"),
    ("slow", "OBSERVATION_DURATION_EXCEEDED"),
])
async def test_parallel_latency_optimization_does_not_relax_original_book_bounds(
    monkeypatch, tmp_path, damage, reason,
):
    metadata, book = inputs()
    if damage == "stale":
        book["time"] = 94999
    elif damage == "future":
        book["time"] = 100002
    client = _ParallelPublicClient(metadata, book)
    adapter, gate = _setup(monkeypatch, tmp_path, client)
    stamps = iter([89999, 100001] if damage == "slow" else [99999, 100001])
    with pytest.raises(HyperliquidPublicBookAdmissionRefused) as exc:
        await asyncio.wait_for(adapter.paper_execution_observation(
            "BTC", clock_ms=lambda: next(stamps)), timeout=2)
    assert exc.value.reason_code == reason
    assert gate.remaining() == 0
    assert adapter.paper_source_snapshot()["facts"]["books"] == {}


@pytest.mark.asyncio
async def test_absent_public_http_client_refuses_before_any_new_request(monkeypatch, tmp_path):
    gate = HyperliquidRequestGate(
        tmp_path / "unconsumed.sqlite", rights_approved=True,
        budget_approved=True, max_attempts=2
    )
    monkeypatch.setattr(hyperliquid_gate_registry, "_gate", gate)
    adapter = HyperliquidAdapter()
    with pytest.raises(ValueError, match="Existing read client"):
        await adapter.paper_execution_observation("BTC", clock_ms=lambda: 100001)
    assert gate.remaining() == 2


@pytest.mark.asyncio
async def test_cancelled_public_observation_cancels_both_pending_http_children(
    monkeypatch, tmp_path,
):
    class PausedClient:
        def __init__(self):
            self.started = asyncio.Event()
            self.calls = []
            self.cancelled = []

        async def post(self, url, json):
            assert url == INFO_URL
            kind = json["type"]
            self.calls.append(kind)
            if len(self.calls) == 2:
                self.started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled.append(kind)
                raise

    client = PausedClient()
    adapter, gate = _setup(monkeypatch, tmp_path, client)
    task = asyncio.create_task(
        adapter.paper_execution_observation("BTC", clock_ms=lambda: 99999)
    )
    await asyncio.wait_for(client.started.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=2)
    assert gate.remaining() == 0
    assert set(client.cancelled) == {"metaAndAssetCtxs", "l2Book"}
    assert adapter.paper_source_snapshot()["facts"]["books"] == {}


class _CoreCutResponse:
    def __init__(self, value):
        self.value = deepcopy(value)

    def raise_for_status(self):
        return None

    def json(self):
        return deepcopy(self.value)


class _CoreCutPublicClient:
    """Ten public-only replies: 1 ticker, 3 x (book, candle, meta)."""

    def __init__(self, *, now_ms, damage=None):
        self.now_ms, self.damage = now_ms, damage
        self.calls = []
        self.closed = False
        self.symbols = ("BTC", "ETH", "SOL")

    async def aclose(self):
        self.closed = True

    async def post(self, url, json):
        assert url == INFO_URL
        self.calls.append(deepcopy(json))
        symbols = self.symbols
        kind = json["type"]
        if kind == "metaAndAssetCtxs":
            items = [dict(name=coin, szDecimals=5, maxLeverage=50,
                          marginTableId=56) for coin in symbols]
            if self.damage == "missing_sol" and len(self.calls) == 1:
                items = items[:2]
            contexts = [dict(markPx="100.5", oraclePx="100.4",
                             funding="0.0000125", dayNtlVlm="10000",
                             openInterest="500") for _ in items]
            return _CoreCutResponse([
                {"universe":items,
                 "marginTables":[[56,{"marginTiers":[{
                     "lowerBound":"0","maxLeverage":50}]}]]}, contexts
            ])
        coin = json["coin"] if kind == "l2Book" else json["req"]["coin"]
        assert coin in symbols
        if kind == "l2Book":
            if self.damage == "invalid_eth" and coin == "ETH":
                return _CoreCutResponse({"coin": coin, "time": self.now_ms,
                                         "levels":[[], []]})
            return _CoreCutResponse({
                "coin":coin, "time":self.now_ms-500,
                "levels":[[{"px":"100","sz":"1.25","n":2}],
                          [{"px":"101","sz":"2.5","n":1}]],
            })
        assert kind == "candleSnapshot"
        assert json["req"]["interval"] == "5m"
        stamp=(self.now_ms // 300000)*300000
        return _CoreCutResponse([
            {"t":stamp-(95-index)*300000,
             "o":"100","h":"101","l":"99","c":"100.5",
             "v":"20","n":3} for index in range(96)
        ])


def _original_core_fixture(monkeypatch, tmp_path, *, damage=None):
    import time
    current=int(time.time()*1000)
    gate=HyperliquidRequestGate(
        tmp_path/"original-core-10-public-requests.sqlite",
        rights_approved=True, budget_approved=True, max_attempts=10,
    )
    monkeypatch.setattr(hyperliquid_gate_registry, "_gate", gate)
    client=_CoreCutPublicClient(now_ms=current, damage=damage)
    adapter=HyperliquidAdapter()
    adapter._client=client
    adapter._connected=True
    return adapter,gate,client


@pytest.mark.asyncio
async def test_complete_original_core_cycle_uses_only_ten_gated_public_requests(
        monkeypatch,tmp_path):
    import time
    adapter,gate,client=_original_core_fixture(monkeypatch,tmp_path)
    original=await adapter.refresh_paper_core_public_inputs(
        clock_ms=lambda:int(time.time()*1000))
    assert gate.remaining()==0
    assert client.closed is False
    assert len(client.calls)==10
    assert [r["type"] for r in client.calls].count("metaAndAssetCtxs")==4
    assert [r["type"] for r in client.calls].count("l2Book")==3
    assert [r["type"] for r in client.calls].count("candleSnapshot")==3
    assert all(r["type"] in {"metaAndAssetCtxs","l2Book","candleSnapshot"}
               for r in client.calls)
    assert original == adapter.paper_source_snapshot()
    assert original["connected"] is True
    facts=original["facts"]
    assert set(facts["books"])=={"BTC","ETH","SOL"}
    assert set(facts["candles"])=={"BTC","ETH","SOL"}
    assert [r["symbol"] for r in facts["markets"]]==["BTC","ETH","SOL"]
    assert facts["funding"]=={} and facts["trades"]=={}
    for symbol in ("BTC","ETH","SOL"):
        assert facts["books"][symbol]["parsed"][
            "financial_execution_authorized"] is False
        assert facts["books"][symbol]["parsed"]["funding_settlement"] is None
        assert len(facts["books"][symbol]["metadata"][0]["universe"])==1
        assert len(facts["candles"][symbol]["rows"])==96
    await adapter.close()
    assert adapter.paper_source_snapshot()["connected"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("damage",["missing_sol","invalid_eth"])
async def test_incomplete_original_core_rejects_and_discards_all_partial_cache(
        monkeypatch,tmp_path,damage):
    import time
    adapter,gate,client=_original_core_fixture(
        monkeypatch,tmp_path,damage=damage)
    with pytest.raises(ValueError):
        await adapter.refresh_paper_core_public_inputs(
            clock_ms=lambda:int(time.time()*1000))
    assert client.closed is True
    value=adapter.paper_source_snapshot()
    assert value["connected"] is False
    assert value["facts"]["books"] == {}
    assert value["facts"]["candles"] == {}
    assert value["facts"]["markets"] == []
    assert gate.remaining() < 10


@pytest.mark.asyncio
async def test_original_core_refuses_missing_client_before_provider_or_gate(
        monkeypatch,tmp_path):
    adapter=HyperliquidAdapter()
    gate=HyperliquidRequestGate(
        tmp_path/"unused-source-budget.sqlite",
        rights_approved=True,budget_approved=True,max_attempts=10)
    monkeypatch.setattr(hyperliquid_gate_registry,"_gate",gate)
    with pytest.raises(ValueError, match="EXISTING_CLIENT_REQUIRED"):
        await adapter.refresh_paper_core_public_inputs(
            clock_ms=lambda:1000000)
    assert gate.remaining()==10
    assert adapter.paper_source_snapshot()["facts"]["books"]=={}


@pytest.mark.asyncio
async def test_original_core_utc_expiration_latches_and_rejects_cached_legacy(
        monkeypatch,tmp_path):
    import time
    adapter,gate,client=_original_core_fixture(monkeypatch,tmp_path)
    tick=[0]
    def clock_ms():
        tick[0]+=1
        return int(time.time()*1000) + (6000 if tick[0]>=8 else 0)
    with pytest.raises(ValueError):
        await adapter.refresh_paper_core_public_inputs(clock_ms=clock_ms)
    assert client.closed is True
    assert adapter.paper_source_snapshot()["connected"] is False
    assert adapter.paper_source_snapshot()["facts"]["markets"] == []


@pytest.mark.asyncio
async def test_operational_candle_timestamp_uses_original_utc_not_windows_wall(
        monkeypatch,tmp_path):
    import time
    adapter,gate,client=_original_core_fixture(monkeypatch,tmp_path)
    trusted_utc=int(time.time()*1000)-882
    rows=await adapter.get_candles(
        "BTC",interval="5m",lookback=96,clock_ms=lambda:trusted_utc)
    assert len(rows)==96
    assert adapter.paper_source_snapshot()["facts"]["candles"]["BTC"][
        "observed_at_ms"]==trusted_utc
    assert client.calls==[{
        "type":"candleSnapshot",
        "req":{"coin":"BTC","interval":"5m",
               "startTime":trusted_utc-96*300000,"endTime":trusted_utc}
    }]
    assert gate.remaining()==9
    await adapter.close()


@pytest.mark.asyncio
async def test_bogus_injected_candle_clock_refuses_before_a_provider_attempt(
        monkeypatch,tmp_path):
    adapter,gate,client=_original_core_fixture(monkeypatch,tmp_path)
    with pytest.raises(ValueError,match="CANDLE_UTC_MS_REQUIRED"):
        await adapter.get_candles(
            "BTC",interval="5m",lookback=96,clock_ms=lambda:True)
    assert gate.remaining()==10
    assert client.calls==[]
    await adapter.close()
