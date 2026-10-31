"""Offline cleanup contracts: fake clients only; no settings or Redis connections."""

import asyncio

import pytest
from app.core import redis as module


class Client:
    def __init__(self, primary=None, fallback=None):
        self.primary = primary
        self.fallback = fallback
        self.calls = []

    async def aclose(self):
        self.calls.append("aclose")
        if self.primary is not None:
            raise self.primary

    async def close(self):
        self.calls.append("close")
        if self.fallback is not None:
            raise self.fallback


@pytest.mark.asyncio
async def test_both_fail_retains_owned_client_and_propagates(monkeypatch):
    first = OSError("synthetic primary failure")
    second = RuntimeError("synthetic fallback failure")
    client = Client(first, second)
    monkeypatch.setattr(module, "_redis", client)
    with pytest.raises(RuntimeError) as failure:
        await module.close_redis()
    assert failure.value is second
    assert second.__cause__ is first
    assert module.get_redis() is client
    assert client.calls == ["aclose", "close"]


@pytest.mark.asyncio
@pytest.mark.parametrize("primary", [None, OSError("synthetic")])
async def test_success_and_legacy_fallback_clear_reference(monkeypatch, primary):
    client = Client(primary)
    monkeypatch.setattr(module, "_redis", client)
    await module.close_redis()
    assert module.get_redis() is None
    assert client.calls == (["aclose"] if primary is None else ["aclose", "close"])
    await module.close_redis()
    assert len(client.calls) == (1 if primary is None else 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["primary", "fallback"])
async def test_cancellation_is_not_swallowed_or_reported_closed(monkeypatch, phase):
    client = Client(asyncio.CancelledError() if phase == "primary" else OSError(),
                    asyncio.CancelledError())
    monkeypatch.setattr(module, "_redis", client)
    with pytest.raises(asyncio.CancelledError):
        await module.close_redis()
    assert module.get_redis() is client
    assert client.calls == (["aclose"] if phase == "primary" else ["aclose", "close"])


@pytest.mark.asyncio
async def test_failed_cleanup_can_be_retried(monkeypatch):
    client = Client(OSError(), OSError())
    monkeypatch.setattr(module, "_redis", client)
    with pytest.raises(OSError):
        await module.close_redis()
    client.primary = None
    await module.close_redis()
    assert module.get_redis() is None
