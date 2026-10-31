import asyncio

import pytest

from app.adapters.hyperliquid import HyperliquidAdapter
from app.adapters.hyperliquid_request_gate import (
    HyperliquidRequestGate,
    RequestGateRefused,
)
from app.adapters import hyperliquid_cache
from app.adapters import hyperliquid_gate_registry


@pytest.fixture(autouse=True)
def reset_gate(monkeypatch):
    monkeypatch.setattr(hyperliquid_gate_registry, '_gate', None)


def test_adapter_http_refuses_without_gate():
    class FakeClient:
        calls = 0

        async def post(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("Network boundary reached")

    async def check():
        adapter = HyperliquidAdapter()
        fake = FakeClient()
        adapter._client = fake

        with pytest.raises(RequestGateRefused):
            await adapter._post({"type": "meta"})

        assert fake.calls == 0

    asyncio.run(check())


def test_adapter_http_consumes_before_sender(tmp_path):
    gate = HyperliquidRequestGate(
        tmp_path / "shared.sqlite",
        rights_approved=True,
        budget_approved=True,
        max_attempts=1,
    )

    class FakeClient:
        calls = 0

        async def post(self, *args, **kwargs):
            self.calls += 1
            raise RuntimeError("Simulated send failure")

    async def check():
        adapter = HyperliquidAdapter()
        hyperliquid_gate_registry.install_gate(gate)
        fake = FakeClient()
        adapter._client = fake

        with pytest.raises(RuntimeError, match="Simulated send failure"):
            await adapter._post({"type": "meta"})

        assert fake.calls == 1
        assert gate.remaining() == 0

        with pytest.raises(RequestGateRefused):
            await adapter._post({"type": "meta"})

        assert fake.calls == 1

    asyncio.run(check())


def test_cache_and_adapter_share_budget(tmp_path, monkeypatch):
    gate = HyperliquidRequestGate(
        tmp_path / "shared.sqlite",
        rights_approved=True,
        budget_approved=True,
        max_attempts=1,
    )

    adapter = HyperliquidAdapter()
    hyperliquid_gate_registry.install_gate(gate)

    async def check():
        adapter._consume_request("HTTP")

        with pytest.raises(RequestGateRefused):
            hyperliquid_gate_registry.consume_before_attempt("HTTP")

        assert gate.remaining() == 0

    asyncio.run(check())


def test_websocket_attempt_requires_gate():
    adapter = HyperliquidAdapter()

    with pytest.raises(RequestGateRefused):
        adapter._consume_request("WEBSOCKET_CONNECT")
