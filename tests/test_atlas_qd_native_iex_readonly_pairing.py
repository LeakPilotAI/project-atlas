"""Source-only native Quality Dips publisher -> Alpaca IEX quote pairing checks.

The original QD publication uses disposable native-custody/authority fixtures.
All quote frames are synthetic. No real provider, account, trading or startup.
"""
import copy
import json
from datetime import UTC, datetime

import pytest
from app.investment.alpaca_iex import IEXFeed
from scripts.observation_runtime import atlas_qd_native_iex_readonly_pairing as pairing
from test_quality_dips_current_producer import fixture as current_fixture


def setup(monkeypatch, symbols=("MSFT", "AAPL"), quote_symbols=None):
    s = current_fixture(monkeypatch, symbols)
    publication = s.owner.publish_current()
    assert publication["revision"] == 1
    roster = list(symbols if quote_symbols is None else quote_symbols)
    feed = IEXFeed(roster, clock=s.s.clock)
    feed.receive('[{"T":"success","msg":"authenticated"}]')
    feed.receive(json.dumps([{"T":"subscription","quotes":roster}]))
    return s, feed


def send(feed, now, symbol, *, condition="R"):
    timestamp=datetime.fromtimestamp(now, UTC).isoformat().replace("+00:00", "Z")
    feed.receive(json.dumps([{"T":"q", "S":symbol, "bp":100, "ap":100.1,
                             "bs":2, "as":3, "bx":"V", "ax":"V", "z":"C",
                             "c":[condition], "t":timestamp}]))


def test_disposable_native_source_and_two_current_iex_instruments_pair_without_orders(monkeypatch):
    source, feed = setup(monkeypatch)
    for symbol in ("MSFT", "AAPL"):
        send(feed, source.s.now[0], symbol)
    unchanged = copy.deepcopy(source.s.s.files)
    result = pairing.inspect(source=source.owner, feed=feed)
    assert result["schema"] == pairing.SCHEMA
    assert result["source_execution_domain"] == "DISPOSABLE"
    assert result["required_symbols"] == ["AAPL", "MSFT"]
    assert result["fresh_quote_symbols"] == ["AAPL", "MSFT"]
    assert result["missing_or_stale_quote_symbols"] == []
    assert result["complete_data_only_pairing"] is True
    assert result["source_readback_invoked"] is True
    for flag in ("source_issuer_independently_accepted",
                 "entitlements_independently_accepted",
                 "financial_clock_independently_qualified",
                 "continuous_quote_delivery_proven",
                 "native_financial_issuer_published",
                 "financial_paper_accounts_created",
                 "paper_orders_authorized",
                 "live_orders_authorized", "startup_authorized"):
        assert result[flag] is False
    assert source.s.s.files == unchanged


def test_data_only_pairing_reports_missing_per_symbol_without_fake_entry(monkeypatch):
    source, feed = setup(monkeypatch)
    send(feed, source.s.now[0], "MSFT")
    result = pairing.inspect(source=source.owner, feed=feed)
    assert result["complete_data_only_pairing"] is False
    assert result["fresh_quote_symbols"] == ["MSFT"]
    assert result["missing_or_stale_quote_symbols"] == ["AAPL"]
    assert result["status"] == "DATA_ONLY_REQUIRED_QUOTE_MISSING_NO_FINANCIAL_AUTHORITY"
    assert result["startup_authorized"] is False


def test_invalid_quote_condition_does_not_generate_fresh_pairing(monkeypatch):
    source, feed = setup(monkeypatch)
    send(feed, source.s.now[0], "AAPL")
    send(feed, source.s.now[0], "MSFT", condition="H")
    result = pairing.inspect(source=source.owner, feed=feed)
    assert result["missing_or_stale_quote_symbols"] == ["MSFT"]
    assert result["complete_data_only_pairing"] is False


def test_missing_subscription_for_native_symbol_fails_closed(monkeypatch):
    source, feed = setup(monkeypatch, quote_symbols=["MSFT"])
    send(feed, source.s.now[0], "MSFT")
    with pytest.raises(ValueError, match="ALL_REQUIRED_SYMBOLS_MUST_BE_SUBSCRIBED"):
        pairing.inspect(source=source.owner, feed=feed)


def test_expired_quote_is_not_continuous_coverage(monkeypatch):
    source, feed = setup(monkeypatch)
    for symbol in ("MSFT", "AAPL"):
        send(feed, source.s.now[0], symbol)
    source.s.now[0] += 6
    result=pairing.inspect(source=source.owner, feed=feed)
    assert result["complete_data_only_pairing"] is False
    assert result["missing_or_stale_quote_symbols"] == ["AAPL", "MSFT"]


def test_disconnect_refuses_previously_cached_quotes(monkeypatch):
    source, feed=setup(monkeypatch)
    for symbol in ("MSFT","AAPL"):
        send(feed, source.s.now[0], symbol)
    feed.disconnect()
    with pytest.raises(ValueError, match="CONNECTED_AUTHENTICATED_FEED_REQUIRED"):
        pairing.inspect(source=source.owner, feed=feed)


def test_clock_owner_mismatch_refused_without_source_read(monkeypatch):
    source, feed=setup(monkeypatch)
    feed.clock=lambda:source.s.now[0]
    source.owner.read_publication=lambda *args:pytest.fail("FOREIGN_CLOCK_BEFORE_SOURCE")
    with pytest.raises(ValueError, match="EXPLICIT_SOURCE_AND_CLOCK_REQUIRED"):
        pairing.inspect(source=source.owner, feed=feed)


def test_native_publication_revision_mutation_between_readbacks_refuses(monkeypatch):
    source,feed=setup(monkeypatch)
    for symbol in ("MSFT","AAPL"):
        send(feed, source.s.now[0], symbol)
    original=source.owner.read_publication
    count=[0]
    def mutate(timeout):
        value=original(timeout)
        count[0]+=1
        if count[0]==2:
            value["revision"]+=1
        return value
    source.owner.read_publication=mutate
    with pytest.raises(ValueError, match="NATIVE_OR_QUOTE_CUT_CHANGED"):
        pairing.inspect(source=source.owner, feed=feed)


def test_iex_quote_changed_between_readbacks_refuses(monkeypatch):
    source,feed=setup(monkeypatch)
    for symbol in ("MSFT","AAPL"):
        send(feed, source.s.now[0], symbol)
    original=feed.snapshot
    calls=[0]
    def mutated():
        value=original()
        calls[0]+=1
        if calls[0]==2:
            value["quotes"][0]["sequence"]+=1
        return value
    feed.snapshot=mutated
    with pytest.raises(ValueError, match="NATIVE_OR_QUOTE_CUT_CHANGED"):
        pairing.inspect(source=source.owner, feed=feed)


def test_revoked_source_authority_refuses_even_with_valid_feed(monkeypatch):
    source,feed=setup(monkeypatch)
    for symbol in ("MSFT","AAPL"):
        send(feed, source.s.now[0], symbol)
    source.flags.accepted=False
    with pytest.raises((ValueError, AssertionError)):
        pairing.inspect(source=source.owner,feed=feed)


def test_no_publication_ports_or_defaults_refuse():
    with pytest.raises(ValueError,match="EXPLICIT_SOURCE_AND_CLOCK_REQUIRED"):
        pairing.inspect(source=None,feed=None)
