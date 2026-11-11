"""R16 selected IEX bounded WebSocket source probe: all tests offline.

Genuine current selected code/root readback; synthetic feed substitutes to
test the exact data-only boundaries. No broker order, provider socket or key.
"""
from __future__ import annotations

import copy

import pytest

from app.investment.alpaca_iex import Credentials
from scripts.observation_runtime import atlas_r16_alpaca_iex_stream_probe as r16


def _synthetic_feed_factory(seen, *, change=None):
    class FakeFeed:
        def __init__(self,symbols):
            seen.append(("symbols",list(symbols)))
            self.symbols=symbols
        async def run(self,credentials,*,seconds,max_reconnects,on_fresh_quote):
            assert credentials.key=="TEST-DATA-ONLY-KEY"
            assert seconds==12
            assert max_reconnects==0
            assert callable(on_fresh_quote)
            seen.append(("socket_connection_budget",1))
            event={
                "provider":"ALPACA_IEX","symbol":"MSFT",
                "timestamp":"2026-11-11T15:14:00Z",
                "paper_fill_authorized":False,"live_order_authorized":False,
            }
            on_fresh_quote(event)
            result={
                "authenticated":True,"subscribed":True,
                "quote_count":1,
                "fresh_quote_observed_during_connection":True,
                "result":{"connection":"DISCONNECTED"},
                "per_symbol_quote_diagnostics":{
                    "MSFT":{"received":1,"accepted":1,"rejected":0,"fresh_callbacks":1},
                    "SPY":{"received":0,"accepted":0,"rejected":0,"fresh_callbacks":0},
                },
            }
            if change is not None:
                change(result)
            return result
    return FakeFeed


def _credentials(path):
    assert path==r16.CONFIG
    return Credentials(key="TEST-DATA-ONLY-KEY",secret="TEST-DATA-ONLY-SECRET")


@pytest.mark.asyncio
async def test_current_r16_one_bounded_fake_stream_requires_authenticated_fresh_callback():
    calls=[]
    row=await r16.observe(
        seconds=12,symbols=["MSFT","SPY"],confirmed_scope=r16.SCOPE,
        credential_reader=_credentials,feed_factory=_synthetic_feed_factory(calls))
    assert calls==[("symbols",["MSFT","SPY"]),("socket_connection_budget",1)]
    assert row["schema"]==r16.SCHEMA
    assert row["selected_native_head_verified"] is True
    assert row["status"]=="R16_BOUNDED_AUTHENTICATED_FRESH_IEX_STREAM_NOT_FINANCIAL_ACCEPTANCE"
    assert row["authenticated"] is True and row["subscribed"] is True
    assert row["connection_closed"] is True
    assert row["request_symbols"]==["MSFT","SPY"]
    assert row["observed_fresh_symbols"]==["MSFT"]
    assert row["fresh_quote_callbacks"]==1
    assert row["per_symbol_counts"]["SPY"]["fresh_callbacks"]==0
    assert row["per_symbol_counts"]["MSFT"]["fresh_callbacks"]==1
    assert row["network_connection_budget"]==1
    assert row["max_reconnects"]==0
    assert row["independent_provider_license_verified"] is False
    assert row["continuous_quote_source_and_freshness_verified"] is False
    assert row["full_robinhood_equity_etf_coverage_verified"] is False
    assert row["paper_start_authorized"] is False
    assert row["live_trading_authorized"] is False
    assert row["paper_orders_created"]==0
    assert row["native_account_files_written"]==0
    assert "TEST-DATA-ONLY-SECRET" not in str(row)
    assert "2026-11-11T15" not in str(row)
    assert "bid" not in str(row).lower()


def test_real_r16_readonly_inspect_does_not_load_config_or_network():
    data=r16.inspect()
    assert data["status"]=="R16_SELECTED_IEX_STREAM_SCOPE_ONLY_NO_NETWORK"
    assert data["provider_connected"] is False
    assert data["credentials_read"] is False
    assert data["network_requests"]==0
    assert data["max_reconnects"]==0
    assert data["duration_bounds_seconds"]==[10,45]


@pytest.mark.parametrize("seconds,symbols,scope",[
    (9,["MSFT"],r16.SCOPE),(46,["MSFT"],r16.SCOPE),
    (True,["MSFT"],r16.SCOPE),("20",["MSFT"],r16.SCOPE),
    (12,[],r16.SCOPE),(12,["MSFT","MSFT"],r16.SCOPE),
    (12,["MSFT","SPY","AAPL","NVDA"],r16.SCOPE),
    (12,["MSFT","spy"],r16.SCOPE),(12,["BTC/USD"],r16.SCOPE),
    (12,["MSFT"],None),(12,["MSFT"],"TRADING_ENABLED"),
])
def test_bad_scope_or_oversized_stream_refused_before_credentials(seconds,symbols,scope):
    with pytest.raises(ValueError,match="R16_IEX_WEBSOCKET_EXACT_BOUNDED_NO_TRADING_SCOPE_REQUIRED"):
        r16.validate_scope(seconds=seconds,symbols=symbols,confirmed_scope=scope)


@pytest.mark.parametrize("field,value",[
    ("selected_revision",14),
    ("selected_native_head","0"*64),
    ("paper_start_authorized",True),
    ("provider_source_operational_accepted",True),
    ("financial_writer_operational_accepted",True),
    ("live_trading_authorized",True),
])
@pytest.mark.asyncio
async def test_changed_selected_native_release_refuses_before_credentials(monkeypatch,field,value):
    from scripts.observation_runtime import atlas_r16_alpaca_iex_rest_probe as rest
    original=rest.selected_code()
    replaced=copy.deepcopy(original)
    replaced[field]=value
    monkeypatch.setattr(rest,"selected_code",lambda:replaced)
    called=[]
    def creds(_):
        called.append("CREDENTIAL_LOADED")
        return _credentials(_)
    with pytest.raises(ValueError,match="R16_IEX_CURRENT_CODE_ONLY_NO_TRADING_SELECTED_REQUIRED"):
        await r16.observe(
            seconds=12,symbols=["MSFT"],confirmed_scope=r16.SCOPE,
            credential_reader=creds)
    assert not called


@pytest.mark.asyncio
async def test_non_empty_real_native_financial_root_refuses_before_credentials(monkeypatch):
    original=r16.inspect_two_lane_native_roots()
    modified=copy.deepcopy(original)
    modified["all_twelve_distinct_and_empty"]=False
    monkeypatch.setattr(r16,"inspect_two_lane_native_roots",lambda:modified)
    with pytest.raises(ValueError,match="R16_IEX_STREAM_ORIGINAL_NATIVE_ACCOUNT_ROOTS_NOT_EMPTY"):
        await r16.observe(
            seconds=12,symbols=["MSFT"],confirmed_scope=r16.SCOPE,
            credential_reader=lambda _: pytest.fail("MUST_NOT_READ_KEYS"))


@pytest.mark.parametrize("change",[
    lambda x: x.update(authenticated=False),
    lambda x: x.update(subscribed=False),
    lambda x: x.update(quote_count=0),
    lambda x: x.update(fresh_quote_observed_during_connection=False),
    lambda x: x["result"].update(connection="CONNECTED"),
    lambda x: x["per_symbol_quote_diagnostics"]["MSFT"].update(fresh_callbacks=0),
    lambda x: x["per_symbol_quote_diagnostics"]["MSFT"].update(rejected=1),
])
@pytest.mark.asyncio
async def test_incomplete_or_inconsistent_stream_never_claims_acceptance(change):
    calls=[]
    with pytest.raises((ValueError,TypeError,KeyError)):
        await r16.observe(
            seconds=12,symbols=["MSFT","SPY"],confirmed_scope=r16.SCOPE,
            credential_reader=_credentials,
            feed_factory=_synthetic_feed_factory(calls,change=change))


def test_missing_callback_source_never_qualifies_stream():
    selected=r16.require_selected_r16_data_only()
    fake={
        "schema":"ATLAS_IEX_BOUNDED_DATA_ONLY_PROBE_V1",
        "status":"BOUNDED_FRESH_IEX_OBSERVED_NOT_FINANCIAL_AUTHORITY",
        "authenticated":True,"subscribed":True,"connection_closed":True,
        "fresh_quote_observed_during_connection":True,
        "quote_count":1,"callback_quote_count":1,
        "observed_symbols":["MSFT"],
        "paper_fill_authorized":False,"live_order_authorized":False,
        "provider_rights_independently_accepted":False,
        "continuous_executable_prices_verified":False,
    }
    with pytest.raises(ValueError,match="PER_SYMBOL_PROVIDER_DIAGNOSTICS_REQUIRED"):
        r16._convert(fake,requested=["MSFT"],before=selected,after=selected)
