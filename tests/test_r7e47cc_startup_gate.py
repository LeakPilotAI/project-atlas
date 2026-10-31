import asyncio

import pytest

from app.adapters import hyperliquid_gate_registry as registry
from app.adapters.hyperliquid import HyperliquidAdapter
from app.adapters.hyperliquid_request_gate import RequestGateRefused


def test_connect_refuses_before_network_client_creation(monkeypatch):
    monkeypatch.setattr(registry, "_gate", None)

    adapter = HyperliquidAdapter()

    with pytest.raises(RequestGateRefused):
        asyncio.run(adapter.connect())

    assert adapter._client is None
    assert adapter._ws_task is None
    assert adapter._connected is False


def test_missing_gate_refuses_repeated_connect(monkeypatch):
    monkeypatch.setattr(registry, "_gate", None)

    adapter = HyperliquidAdapter()

    for _ in range(3):
        with pytest.raises(RequestGateRefused):
            asyncio.run(adapter.connect())

    assert adapter._client is None
    assert adapter._ws_task is None
