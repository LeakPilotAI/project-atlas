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


def test_native_publication_path_binds_provider_quote(monkeypatch):
    import app.services.paper_source_publication as source_mod
    import app.services.personal_paper_iex_provider as provider_mod
    import app.services.personal_paper_strategy_signal as signal_mod
    class Published:
        def read_current(self):
            return {"schema": "QD_SCANNER_PUBLICATION_V1",
                    "bundles": [{"instrument": {"symbol": "MSFT"}}]}
    class Provider:
        def __init__(self, feed):
            assert isinstance(feed, Feed)
    monkeypatch.setattr(source_mod, "QualityDipsSourcePublication", Published)
    monkeypatch.setattr(provider_mod, "PersonalPaperIEXProvider", Provider)
    def evaluate(*, publication, provider, symbol, now):
        assert type(publication) is Published and type(provider) is Provider
        assert symbol == "MSFT"
        return {"candidate": True,
                "quote_evidence": {"provider_timestamp": "2026-11-07T00:00:00+00:00", "bid": "99.0", "ask": "100.00"}}
    monkeypatch.setattr(signal_mod, "evaluate_published_iex_v3_candidate", evaluate)
    monkeypatch.setattr(probe.Credentials, "load", lambda _: object())
    result = probe.bounded_clock_iex_observation(
        symbol="MSFT", seconds=3, credentials_path=Path("unused"),
        clock_factory=Clock, feed_factory=Feed, publication=Published())
    assert result["published_research_checked_count"] == 1
    assert result["published_research_candidate_count"] == 1
    assert result["forward_financial_write_authorized"] is False


def test_publication_requires_native_type_before_clock_or_credentials(monkeypatch):
    monkeypatch.setattr(probe.Credentials, "load", lambda _: pytest.fail("no credential access"))
    with pytest.raises(ValueError, match="CLOCK_IEX_NATIVE_PUBLICATION_REQUIRED"):
        probe.bounded_clock_iex_observation(
            symbol="MSFT", seconds=3, credentials_path=Path("unused"),
            clock_factory=Clock, feed_factory=Feed, publication={"source_verified": True})


def test_publication_quote_mismatch_refuses(monkeypatch):
    import app.services.paper_source_publication as source_mod
    import app.services.personal_paper_iex_provider as provider_mod
    import app.services.personal_paper_strategy_signal as signal_mod
    class Published:
        def read_current(self):
            return {"schema": "QD_SCANNER_PUBLICATION_V1",
                    "bundles": [{"instrument": {"symbol": "MSFT"}}]}
    class Provider:
        def __init__(self, feed):
            pass
    monkeypatch.setattr(source_mod, "QualityDipsSourcePublication", Published)
    monkeypatch.setattr(provider_mod, "PersonalPaperIEXProvider", Provider)
    monkeypatch.setattr(signal_mod, "evaluate_published_iex_v3_candidate",
                        lambda **kwargs: {"candidate": True,
                          "quote_evidence": {"provider_timestamp": "2026-11-06T23:59:59+00:00"}})
    monkeypatch.setattr(probe.Credentials, "load", lambda _: object())
    Clock.revoked = False
    with pytest.raises(ValueError, match="CLOCK_IEX_PUBLICATION_QUOTE_CHANGED"):
        probe.bounded_clock_iex_observation(
            symbol="MSFT", seconds=3, credentials_path=Path("unused"),
            clock_factory=Clock, feed_factory=Feed, publication=Published())
    assert Clock.revoked


def test_same_timestamp_different_price_refused(monkeypatch):
    import app.services.paper_source_publication as source_mod
    import app.services.personal_paper_iex_provider as provider_mod
    import app.services.personal_paper_strategy_signal as signal_mod
    class Published:
        def read_current(self):
            return {"schema": "QD_SCANNER_PUBLICATION_V1",
                    "bundles": [{"instrument": {"symbol": "MSFT"}}]}
    class Provider:
        def __init__(self, feed):
            pass
    monkeypatch.setattr(source_mod, "QualityDipsSourcePublication", Published)
    monkeypatch.setattr(provider_mod, "PersonalPaperIEXProvider", Provider)
    monkeypatch.setattr(signal_mod, "evaluate_published_iex_v3_candidate",
                        lambda **kwargs: {"candidate": True,
                          "quote_evidence": {"provider_timestamp": "2026-11-07T00:00:00+00:00",
                                             "bid": "98", "ask": "100"}})
    monkeypatch.setattr(probe.Credentials, "load", lambda _: object())
    Clock.revoked = False
    with pytest.raises(ValueError, match="CLOCK_IEX_PUBLICATION_QUOTE_CHANGED"):
        probe.bounded_clock_iex_observation(
            symbol="MSFT", seconds=3, credentials_path=Path("unused"),
            clock_factory=Clock, feed_factory=Feed, publication=Published())
    assert Clock.revoked


def test_stale_native_publication_refuses_before_credentials_or_socket(monkeypatch):
    import app.services.paper_source_publication as source_mod
    class StalePublication:
        def read_current(self):
            raise ValueError("SOURCE_CURRENT_CUSTODY_ROLLBACK_OR_FRESHNESS_REFUSED")
    monkeypatch.setattr(source_mod, "QualityDipsSourcePublication", StalePublication)
    monkeypatch.setattr(probe.Credentials, "load", lambda _: pytest.fail("credentials accessed"))
    class NoFeed:
        def __init__(self, symbols):
            pytest.fail("provider connection assembled")
    Clock.revoked = False
    with pytest.raises(ValueError, match="SOURCE_CURRENT_CUSTODY_ROLLBACK_OR_FRESHNESS_REFUSED"):
        probe.bounded_clock_iex_observation(
            symbol="MSFT", seconds=3, credentials_path=Path("unused"),
            clock_factory=Clock, feed_factory=NoFeed, publication=StalePublication())
    assert Clock.revoked


def test_publication_missing_symbol_refuses_before_credentials(monkeypatch):
    import app.services.paper_source_publication as source_mod
    class OtherSymbol:
        def read_current(self):
            return {"schema": "QD_SCANNER_PUBLICATION_V1",
                    "bundles": [{"instrument": {"symbol": "AVGO"}}]}
    monkeypatch.setattr(source_mod, "QualityDipsSourcePublication", OtherSymbol)
    monkeypatch.setattr(probe.Credentials, "load", lambda _: pytest.fail("credentials accessed"))
    Clock.revoked = False
    with pytest.raises(ValueError, match="CLOCK_IEX_PUBLISHED_SYMBOL_NOT_ENROLLED"):
        probe.bounded_clock_iex_observation(
            symbol="MSFT", seconds=3, credentials_path=Path("unused"),
            clock_factory=Clock, feed_factory=Feed, publication=OtherSymbol())
    assert Clock.revoked
