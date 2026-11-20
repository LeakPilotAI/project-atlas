"""Selected R16 full Basic IEX 30-symbol roster and provider ACK, offline.

All provider sessions here are synthetic. This tests the genuine catalog and
read-only native R16 source guards; it never grants market/finance authority.
"""
from __future__ import annotations
import copy

import pytest
from app.investment.alpaca_iex import Credentials
from scripts.observation_runtime import atlas_r16_iex_basic_research_roster as r16
from scripts.observation_runtime.alpaca_equity_catalog import inventory_snapshot


def catalog(n=100):
    return inventory_snapshot([
        {"class":"us_equity","symbol":f"S{i:03d}",
         "status":"active","tradable":True,
         "exchange":"NASDAQ","id":str(i)} for i in range(n)],
        captured_at="2026-11-11T09:00:00+00:00")


def example_plan(n=100,pins=("S000","S001"),offset=0):
    return r16.prepare(
        confirmed_scope=r16.SCOPE,offset=offset,
        pins=list(pins),snapshot=catalog(n))


def fake_result(roster, *, quoted=("S000","S001"),auth=True,subscribed=True):
    rows={s:{"received":1 if s in quoted else 0,
             "accepted":1 if s in quoted else 0,
             "rejected":0,"fresh_callbacks":0}
          for s in roster["requested_symbols"]}
    return {
        "authenticated":auth,"subscribed":subscribed,
        "endpoint":"wss://stream.data.alpaca.markets/v2/iex",
        "feed":"IEX","reconnects":0,
        "result":{"connection":"DISCONNECTED","paper_startup_authorized":False},
        "per_symbol_quote_diagnostics":rows,
        "quote_count":sum(v["accepted"] for v in rows.values()),
        "fresh_quote_observed_during_connection":bool(quoted),
    }


def _verify(roster,result):
    from scripts.observation_runtime.atlas_r16_alpaca_iex_rest_probe import (
        require_selected_r16_data_only,
    )
    from scripts.observation_runtime.personal_existing_native_resource_evidence import (
        inspect_two_lane_native_roots,
    )
    return r16.sanitize(
        roster,result,seconds=15,
        source_before=require_selected_r16_data_only(),
        source_after=require_selected_r16_data_only(),
        roots_before=inspect_two_lane_native_roots(),
        roots_after=inspect_two_lane_native_roots())


def test_actual_current_r16_catalog_is_larger_than_one_free_stream():
    plan=r16.inspect(offset=0,pins=("MSFT","SPY"))
    assert plan["schema"]==r16.SCHEMA
    assert plan["status"]=="R16_CURRENT_30_SYMBOL_CATALOG_PLAN_NO_PROVIDER_REQUEST"
    assert plan["catalog_total_research_symbols"]==13487
    assert plan["roster_requested_symbols_count"]==30
    assert plan["full_catalog_batches_minimum"]==482
    assert plan["pinned_research_symbols"]==["MSFT","SPY"]
    assert plan["network_requests"]==0
    assert plan["credentials_read"] is False
    assert plan["provider_subscription_accepted"] is False
    assert plan["paper_start_authorized"] is False
    assert plan["financial_operating_gates_accepted"]==0


def test_current_r16_full_30_symbol_subscription_ack_does_not_forge_quotes():
    roster=example_plan()
    assert roster["requested_symbol_count"]==30
    result=fake_result(roster)
    row=_verify(roster,result)
    assert row["schema"]==r16.SCHEMA
    assert row["source_release"]=="R16"
    assert row["status"]=="R16_AUTHENTICATED_30_SYMBOL_RESEARCH_ACK_NOT_MARKET_COVERAGE"
    assert row["catalog_total_research_symbols"]==100
    assert row["minimum_complete_catalog_subscription_batches"]==4
    assert row["websocket_authenticated"] is True
    assert row["exact_roster_subscription_acknowledged"] is True
    assert row["websocket_connections"]==1 and row["reconnects"]==0
    assert row["requested_symbols_without_accepted_quote"]==28
    assert row["symbols_with_at_least_one_accepted_quote"]==2
    assert row["subscription_ack_is_not_per_symbol_quote_liveness"] is True
    assert row["full_universe_realtime_coverage"] is False
    assert row["robinhood_instrument_eligibility_verified"] is False
    assert row["provider_licenses_independently_accepted"] is False
    assert row["supervised_paper_source_authorized"] is False
    assert row["financial_operating_gates_accepted"]==0
    assert row["paper_start_authorized"] is False
    assert row["live_trading_authorized"] is False
    assert row["native_financial_account_files_written"]==0
    assert row["hyperliquid_provider_requests"]==0
    assert "bid" not in str(row).lower()
    assert "ask" not in str(row).lower()


def test_silent_but_acknowledged_roster_is_not_thirty_live_quotes():
    roster=example_plan()
    raw=fake_result(roster,quoted=())
    row=_verify(roster,raw)
    assert row["symbols_requested_count"]==30
    assert row["symbols_with_at_least_one_accepted_quote"]==0
    assert row["requested_symbols_without_accepted_quote"]==30
    assert row["quote_messages_received"]==0
    assert row["provider_licenses_independently_accepted"] is False
    assert row["paper_start_authorized"] is False


@pytest.mark.parametrize("source,offset,pins",[
    ("wrong",0,[]),(None,0,[]),(r16.SCOPE,-1,[]),
    (r16.SCOPE,True,[]),(r16.SCOPE,0,["S100"]),
    (r16.SCOPE,0,["S001","S001"]),
    (r16.SCOPE,0,list(range(11))),
])
def test_invalid_catalog_rotation_scope_refuses_before_credentials(source,offset,pins):
    with pytest.raises((ValueError,TypeError)):
        r16.prepare(
            confirmed_scope=source,offset=offset,
            pins=pins,snapshot=catalog())


@pytest.mark.parametrize("change",[
    {"authenticated":False},
    {"subscribed":False},
    {"reconnects":1},
    {"endpoint":"wss://stream.data.alpaca.markets/v2/sip"},
    {"feed":"SIP"},
    {"quote_count":99},
    {"fresh_quote_observed_during_connection":False},
])
def test_wrong_provider_response_does_not_claim_coverage(change):
    roster=example_plan()
    raw=fake_result(roster)
    raw.update(change)
    with pytest.raises(ValueError):
        _verify(roster,raw)


@pytest.mark.parametrize("mutation",[
    "fake_source","fake_root","false_price_live","invent_extra_quote",
    "false_ack","forged_live_fill","wrong_symbol_counter","wrong_counter_type",
])
def test_forged_account_provider_or_quote_counters_refused(mutation):
    roster=example_plan()
    raw=fake_result(roster)
    selected_before=r16.require_selected_r16_data_only()
    selected_after=copy.deepcopy(selected_before)
    roots_before=r16.inspect_two_lane_native_roots()
    roots_after=copy.deepcopy(roots_before)
    if mutation=="fake_source":
        selected_after["selected_revision"]=14
    elif mutation=="fake_root":
        roots_after["all_twelve_distinct_and_empty"]=False
    elif mutation=="false_price_live":
        raw["result"]["paper_startup_authorized"]=True
    elif mutation=="invent_extra_quote":
        raw["quote_count"]=9
    elif mutation=="false_ack":
        raw["subscribed"]=False
    elif mutation=="forged_live_fill":
        raw["live_order_authorized"]=True
    elif mutation=="wrong_symbol_counter":
        raw["per_symbol_quote_diagnostics"]["S000"]["accepted"]=2
    elif mutation=="wrong_counter_type":
        raw["per_symbol_quote_diagnostics"]["S000"]["received"]=True
    with pytest.raises(ValueError):
        r16.sanitize(
            roster,raw,seconds=15,
            source_before=selected_before,source_after=selected_after,
            roots_before=roots_before,roots_after=roots_after)


@pytest.mark.asyncio
async def test_one_synthetic_30_symbol_data_only_session_uses_current_selected_r16_before_credentials():
    seen=[]
    roster=example_plan()
    def credentials(path):
        assert path==r16.CONFIG
        seen.append("VALIDATED_KEYS")
        return Credentials(key="SYNTHETIC_TEST_KEY",secret="SYNTHETIC_TEST_SECRET")
    class Feed:
        def __init__(self,symbols):
            assert list(symbols)==roster["requested_symbols"]
            seen.append("ROSTER")
        async def run(self,keys,*,seconds,max_reconnects):
            assert seconds==15 and max_reconnects==0
            assert type(keys) is Credentials
            seen.append("ONE_SOCKET")
            return fake_result(roster)
    row=await r16.observe(
        seconds=15,confirmed_scope=r16.SCOPE,pins=("S000","S001"),
        snapshot=catalog(),credential_reader=credentials,feed_factory=Feed)
    assert seen==["VALIDATED_KEYS","ROSTER","ONE_SOCKET"]
    assert row["symbols_with_at_least_one_accepted_quote"]==2
    assert row["paper_start_authorized"] is False
    assert "SYNTHETIC_TEST_SECRET" not in str(row)


@pytest.mark.parametrize("seconds",[0,9,36,True,"20"])
@pytest.mark.asyncio
async def test_invalid_duration_never_reads_credentials_or_uses_provider(seconds):
    with pytest.raises(ValueError,match="R16_IEX_RESEARCH_BOUNDED_SECONDS_REQUIRED"):
        await r16.observe(
            seconds=seconds,confirmed_scope=r16.SCOPE,
            credential_reader=lambda _:pytest.fail("CREDENTIALS_FORBIDDEN"))


def test_real_native_selected_release_must_not_grant_paper_start():
    v=r16.require_selected_r16_data_only()
    r=r16.inspect_two_lane_native_roots()
    assert v["selected_revision"]==15
    assert v["paper_start_authorized"] is False
    assert v["live_trading_authorized"] is False
    assert r["native_root_total"]==12
    assert r["all_twelve_distinct_and_empty"] is True
