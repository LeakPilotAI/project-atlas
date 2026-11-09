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
