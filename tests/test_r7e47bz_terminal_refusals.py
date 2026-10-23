import asyncio

import pytest

from app.adapters.hyperliquid import HyperliquidAdapter
from app.adapters import hyperliquid_cache
from app.adapters.hyperliquid_request_gate import RequestGateRefused


def test_cache_direct_refusal_propagates(monkeypatch):
    hyperliquid_cache._request_gate = None

    class FakeClient:
        calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("Network attempted")

    fake = FakeClient()
    monkeypatch.setattr(
        hyperliquid_cache.httpx,
        "AsyncClient",
        lambda **kwargs: fake,
    )

    with pytest.raises(RequestGateRefused):
        asyncio.run(hyperliquid_cache._fetch_direct())

    assert fake.calls == 0


def test_cache_adapter_refusal_stops_fallback(monkeypatch):
    async def denied():
        raise RequestGateRefused("Budget exhausted")

    async def forbidden():
        raise AssertionError("Fallback should not run")

    monkeypatch.setattr(
        hyperliquid_cache,
        "_fetch_via_adapter",
        denied,
    )
    monkeypatch.setattr(
        hyperliquid_cache,
        "_fetch_direct",
        forbidden,
    )

    with pytest.raises(RequestGateRefused):
        asyncio.run(hyperliquid_cache.get_tickers_cached(force=True))


def test_websocket_refusal_stops_loop(monkeypatch):
    adapter = HyperliquidAdapter()
    adapter._ws_running = True

    class FakeWebsockets:
        calls = 0

        def connect(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("WebSocket connection attempted")

    fake = FakeWebsockets()

    monkeypatch.setattr(
        "app.adapters.hyperliquid.websockets",
        fake,
    )

    with pytest.raises(RequestGateRefused):
        asyncio.run(adapter._mids_loop())

    assert fake.calls == 0
    assert adapter._ws_running is False
