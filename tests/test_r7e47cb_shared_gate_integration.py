import asyncio

import pytest

from app.adapters import hyperliquid_cache
from app.adapters import hyperliquid_gate_registry as registry
from app.adapters.hyperliquid import HyperliquidAdapter
from app.adapters.hyperliquid_request_gate import (
    HyperliquidRequestGate,
    RequestGateRefused,
)


@pytest.fixture(autouse=True)
def reset_gate(monkeypatch):
    monkeypatch.setattr(registry, "_gate", None)


def test_adapter_and_cache_use_same_gate(tmp_path):
    gate = HyperliquidRequestGate(
        tmp_path / "shared.sqlite",
        rights_approved=True,
        budget_approved=True,
        max_attempts=2,
    )
    registry.install_gate(gate)

    adapter = HyperliquidAdapter()

    assert adapter._consume_request("HTTP") is None
    assert registry.consume_before_attempt("WEBSOCKET_CONNECT") == 0

    with pytest.raises(RequestGateRefused):
        registry.consume_before_attempt("HTTP")

    assert gate.remaining() == 0


def test_independent_setters_removed():
    adapter = HyperliquidAdapter()

    assert not hasattr(adapter, "set_request_gate")
    assert not hasattr(hyperliquid_cache, "set_request_gate")


def test_default_adapter_refuses():
    adapter = HyperliquidAdapter()

    with pytest.raises(RequestGateRefused):
        adapter._consume_request("HTTP")

    with pytest.raises(RequestGateRefused):
        adapter._consume_request("WEBSOCKET_CONNECT")


def test_cache_direct_uses_shared_gate(tmp_path, monkeypatch):
    gate = HyperliquidRequestGate(
        tmp_path / "shared.sqlite",
        rights_approved=True,
        budget_approved=True,
        max_attempts=1,
    )
    registry.install_gate(gate)

    class FakeClient:
        calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            self.calls += 1
            raise RuntimeError("Offline simulated send failure")

    fake = FakeClient()

    monkeypatch.setattr(
        hyperliquid_cache.httpx,
        "AsyncClient",
        lambda **kwargs: fake,
    )

    assert asyncio.run(hyperliquid_cache._fetch_direct()) == []
    assert fake.calls == 1
    assert gate.remaining() == 0

    with pytest.raises(RequestGateRefused):
        asyncio.run(hyperliquid_cache._fetch_direct())

    assert fake.calls == 1
