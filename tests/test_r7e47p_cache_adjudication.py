"""Synthetic REST responses demonstrate synchronous loop binding and refusal."""

import asyncio
from types import SimpleNamespace

import pytest
from app.adapters import hyperliquid_cache as module
from app.adapters import registry as registry_module


def install_client(monkeypatch, payload=None, failure=None):
    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            if failure is not None:
                raise failure
            return Response()

    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **_kwargs: Client())


@pytest.mark.asyncio
async def test_loop_parser_reads_current_symbol_synchronously(monkeypatch):
    install_client(monkeypatch, [{"universe": [{"name": "BTC"}, {"name": "ETH"}]},
                                [{"markPx": "100", "openInterest": "2"},
                                 {"markPx": "20", "openInterest": "3"}]])
    rows = await module._fetch_direct()
    assert [(row["symbol"], row["price"], row["open_interest"]) for row in rows] == [
        ("BTC", 100, 200), ("ETH", 20, 60)]


@pytest.mark.asyncio
async def test_malformed_universe_returns_no_authoritative_rows(monkeypatch):
    install_client(monkeypatch, [{"universe": 42}, []])
    assert await module._fetch_direct() == []


@pytest.mark.asyncio
async def test_direct_fetch_does_not_swallow_cancellation(monkeypatch):
    install_client(monkeypatch, failure=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await module._fetch_direct()


@pytest.mark.asyncio
async def test_missing_hyperliquid_never_uses_another_exchange(monkeypatch):
    class Foreign:
        async def get_all_tickers(self):
            pytest.fail("Unrelated exchange must not be queried as Hyperliquid")

    monkeypatch.setattr(registry_module, "registry",
                        SimpleNamespace(_adapters={"foreign": Foreign()}))
    assert await module._fetch_via_adapter() == []


@pytest.mark.asyncio
async def test_named_legacy_dictionary_adapter_is_still_supported(monkeypatch):
    expected = [{"symbol": "BTC", "price": 100}]

    class Adapter:
        async def get_all_tickers(self):
            return expected

    monkeypatch.setattr(registry_module, "registry",
                        SimpleNamespace(_adapters={"hyperliquid": Adapter()}))
    assert await module._fetch_via_adapter() is expected
