from datetime import UTC, datetime
from pathlib import Path

import pytest

import scripts.observation_runtime.personal_clock_iex_probe as probe


class Clock:
    revoked = False
    def __init__(self, **kwargs):
        self.evidence = {"bound_ms": 388}
    def require_operational(self, runtime_id):
        return self
    def __call__(self):
        return datetime(2026, 11, 7, tzinfo=UTC).timestamp()
    def revoke(self):
        Clock.revoked = True


class Feed:
    called = False
    def __init__(self, symbols):
        assert symbols == ["MSFT"]
    async def run(self, credentials, *, seconds, max_reconnects, on_fresh_quote):
        Feed.called = True
        assert seconds == 3 and max_reconnects == 0
        on_fresh_quote({"symbol": "MSFT", "bid": 99, "ask": 100,
                        "bid_lots": 2, "ask_lots": 2,
                        "timestamp": "2026-11-07T00:00:00+00:00"})
        return {"authenticated": True, "subscribed": True,
                "result": {"connection": "DISCONNECTED"}}


def test_bounded_native_clock_iex_accepts_fresh_callback_without_authority(monkeypatch):
    monkeypatch.setattr(probe.Credentials, "load", lambda _: object())
    Clock.revoked = False
    result = probe.bounded_clock_iex_observation(
        symbol="MSFT", seconds=3, credentials_path=Path("unused"),
        clock_factory=Clock, feed_factory=Feed)
    assert result["fresh_validated_quote_count"] == 1
    assert result["forward_financial_write_authorized"] is False
    assert result["live_order_authorized"] is False
    assert Clock.revoked


def test_clock_failure_blocks_credential_read_and_feed(monkeypatch):
    def no_credentials(_):
        pytest.fail("credentials must not be read before clock gate")
    monkeypatch.setattr(probe.Credentials, "load", no_credentials)
    class RefusedClock:
        def __init__(self, **kwargs):
            raise ValueError("CLOCK_UNCERTAINTY_EXCEEDED")
    with pytest.raises(ValueError, match="CLOCK_UNCERTAINTY_EXCEEDED"):
        probe.bounded_clock_iex_observation(
            symbol="MSFT", seconds=3, credentials_path=Path("unused"),
            clock_factory=RefusedClock, feed_factory=Feed)


def test_quote_replay_refuses_and_revokes_clock(monkeypatch):
    monkeypatch.setattr(probe.Credentials, "load", lambda _: object())
    class ReplayingFeed(Feed):
        async def run(self, credentials, *, seconds, max_reconnects, on_fresh_quote):
            quote = {"symbol": "MSFT", "bid": 99, "ask": 100,
                     "bid_lots": 2, "ask_lots": 2,
                     "timestamp": "2026-11-07T00:00:00+00:00"}
            on_fresh_quote(quote)
            on_fresh_quote(quote)
    Clock.revoked = False
    with pytest.raises(ValueError, match="CLOCK_IEX_PROVIDER_REPLAY_REFUSED"):
        probe.bounded_clock_iex_observation(
            symbol="MSFT", seconds=3, credentials_path=Path("unused"),
            clock_factory=Clock, feed_factory=ReplayingFeed)
    assert Clock.revoked
