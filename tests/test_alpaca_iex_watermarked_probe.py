"""Read-only probe CLI refusal tests; never contact a live provider."""
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts.observation_runtime.alpaca_iex_watermarked_probe import bounded_observation
from scripts.observation_runtime.paper_readonly_watermark import advance_watermark, read_watermark


def test_probe_refuses_unenrolled_watermark_before_provider_start(tmp_path, monkeypatch):
    class Credentials:
        @staticmethod
        def load(path):
            return object()
    monkeypatch.setattr("scripts.observation_runtime.alpaca_iex_watermarked_probe.Credentials", Credentials)
    with pytest.raises(ValueError, match="PRIOR_STATE_REQUIRED"):
        bounded_observation(symbol="MSFT", seconds=1, watermark=tmp_path / "missing.json",
                            credentials_path=tmp_path / "credentials",
                            feed_factory=lambda symbols: pytest.fail("feed started without enrollment"))


def test_probe_accepts_only_bounded_explicit_symbols(tmp_path):
    for symbol, seconds in [("msft", 1), ("MSFT;X", 1), ("MSFT", 0), ("MSFT", 61)]:
        with pytest.raises(ValueError, match="ARGUMENTS_REFUSED"):
            bounded_observation(symbol=symbol, seconds=seconds, watermark=tmp_path / "unused",
                                credentials_path=tmp_path / "missing")


def test_bounded_probe_persists_unique_authenticated_event_and_refuses_replay(tmp_path, monkeypatch):
    from datetime import timedelta
    from app.investment.alpaca_iex import IEXRefused
    from scripts.observation_runtime.alpaca_iex_watermarked_probe import bounded_observation
    stamp = datetime(2026, 11, 7, tzinfo=UTC)
    previous = (stamp - timedelta(seconds=1)).isoformat()
    path = tmp_path / "probe.json"
    advance_watermark(path, symbol="MSFT", provider_timestamp=previous)
    class Credentials:
        @staticmethod
        def load(path):
            return object()
    monkeypatch.setattr("scripts.observation_runtime.alpaca_iex_watermarked_probe.Credentials", Credentials)
    event = {"symbol": "MSFT", "provider": "ALPACA_IEX", "timestamp": stamp.isoformat(),
             "bid": "100", "ask": "100.1", "bid_lots": 1, "ask_lots": 2,
             "paper_fill_authorized": False, "live_order_authorized": False}
    class FakeFeed:
        def __init__(self, symbols):
            assert symbols == ["MSFT"]
        async def run(self, credentials, *, seconds, max_reconnects, on_fresh_quote):
            assert seconds == 1 and max_reconnects == 0
            on_fresh_quote(event)
            return {"authenticated": True, "subscribed": True,
                    "result": {"connection": "DISCONNECTED"}}
    result = bounded_observation(symbol="MSFT", seconds=1, watermark=path,
                                 credentials_path=tmp_path / "fake", feed_factory=FakeFeed)
    assert result["accepted_events"] == 1
    assert result["paper_fill_authorized"] is False
    assert read_watermark(path, symbol="MSFT") == stamp.isoformat()
    with pytest.raises(ValueError, match="REPLAY_REFUSED"):
        bounded_observation(symbol="MSFT", seconds=1, watermark=path,
                            credentials_path=tmp_path / "fake", feed_factory=FakeFeed)
    assert read_watermark(path, symbol="MSFT") == stamp.isoformat()


def test_probe_checks_watermark_before_credentials(tmp_path, monkeypatch):
    class Credentials:
        @staticmethod
        def load(path):
            pytest.fail("credentials accessed before watermark admission")
    monkeypatch.setattr("scripts.observation_runtime.alpaca_iex_watermarked_probe.Credentials", Credentials)
    with pytest.raises(ValueError, match="PRIOR_STATE_REQUIRED"):
        bounded_observation(symbol="MSFT", seconds=1, watermark=tmp_path / "absent",
                            credentials_path=tmp_path / "missing")
