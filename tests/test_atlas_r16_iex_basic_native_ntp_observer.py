"""Original selected R16 clock-validated 30-symbol IEX coverage, offline refusal.

No real provider, NTP peer, credentials or finance file is used by these tests.
The live mode is only executed separately by the genuine installed R16 Python.
"""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path

import pytest

from scripts.observation_runtime import atlas_r16_iex_basic_native_ntp_observer as native
from scripts.observation_runtime import atlas_r16_iex_basic_research_roster as old


class Clock:
    def __init__(self):
        self.revoked=False
    def runtime_sample(self):
        if self.revoked:raise ValueError("REVOKED")
        return {
            "schema":"QD_AUTO_CLOCK_V3",
            "utc":1794420000,
            "monotonic_ns":time.perf_counter_ns(),
            "uncertainty_ms":139,
            "source_id":native.ORIGINAL["ntp_module"].SOURCE,
        }
    def verify_runtime_sample(self,s):return not self.revoked


def inputs():
    from scripts.observation_runtime.alpaca_equity_catalog import inventory_snapshot
    planned=native.rotation.plan(inventory_snapshot([
        {"class":"us_equity","symbol":f"S{i:03d}",
         "status":"active","tradable":True,
         "exchange":"NASDAQ","id":str(i)}
        for i in range(75)],captured_at="2026-11-11T10:00:00+00:00"),
        offset=0,monitored_symbols=["S000","S001"])
    c=Clock()
    ntp=native.ORIGINAL["NativeUtcUpperBound"](c)
    ntp()
    ntp.last_sample=None
    ntp()
    assert ntp.samples_verified==2
    rows={s:{"received":1 if s in ("S000","S001") else 0,
             "accepted":1 if s in ("S000","S001") else 0,
             "rejected":0,"fresh_callbacks":0}
          for s in planned["requested_symbols"]}
    raw={
        "authenticated":True,"subscribed":True,
        "endpoint":"wss://stream.data.alpaca.markets/v2/iex",
        "feed":"IEX","quote_count":2,
        "fresh_quote_observed_during_connection":True,"reconnects":0,
        "per_symbol_quote_diagnostics":rows,
        "result":{"connection":"DISCONNECTED","paper_startup_authorized":False},
    }
    native_row={"native_root_total":12,"all_twelve_distinct_and_empty":True}
    sel={"selected_native_head":native.ORIGINAL["R16_HEAD"],
         "financial_authority":False}
    return {
        "planned":planned,"raw":raw,"ntp":ntp,"seconds":15,
        "before":sel,"after":copy.deepcopy(sel),
        "roots_before":native_row,"roots_after":copy.deepcopy(native_row)}


def test_genuine_native_ntp_research_quote_counts_not_subscription_coverage():
    v=native.safe_result(**inputs())
    assert v["schema"]==native.SCHEMA
    assert v["status"]=="R16_NTP_IEX_FULL_ROSTER_SUBSCRIBED_PARTIAL_FRESH_QUOTES"
    assert v["selected_native_head"]==native.ORIGINAL["R16_HEAD"]
    assert v["requested_symbols_count"]==30
    assert v["research_catalog_size"]==75
    assert v["minimum_30_symbol_research_batches"]==3
    assert v["quote_messages_received"]==2
    assert v["quote_messages_accepted"]==2
    assert v["quote_messages_rejected"]==0
    assert v["symbols_with_at_least_one_accepted_quote"]==2
    assert v["symbols_without_any_accepted_quote"]==28
    assert v["native_ntp_samples_verified"]==2
    assert v["max_ntp_uncertainty_ms"]==139
    assert v["native_utc_bound_used_for_all_quote_freshness"] is True
    assert v["quotes_and_credentials_exposed"] is False
    assert v["provider_reconnects"]==0
    assert v["financial_operating_gates_accepted"]==0
    assert v["paper_start_authorized"] is False
    assert v["live_trading_authorized"] is False
    assert v["native_financial_account_files_created"]==0
    assert v["paper_orders_created"]==v["live_orders_created"]==0
    assert "bid" not in str(v).lower()
    assert "ask" not in str(v).lower()


def test_authenticated_all_30_but_zero_price_acceptance_is_not_successful_liveness():
    value=inputs()
    for row in value["raw"]["per_symbol_quote_diagnostics"].values():
        row.update({"received":0,"accepted":0,"rejected":0})
    value["raw"]["quote_count"]=0
    value["raw"]["fresh_quote_observed_during_connection"]=False
    v=native.safe_result(**value)
    assert v["status"]=="R16_NTP_IEX_ALL_SUBSCRIBED_NO_FRESH_QUOTES"
    assert v["symbols_with_at_least_one_accepted_quote"]==0
    assert v["symbols_without_any_accepted_quote"]==30
    assert v["full_iex_catalog_realtime_coverage"] is False
    assert v["paper_start_authorized"] is False


@pytest.mark.parametrize("field,value",[
    ("seconds",9),("seconds",36),("seconds",True),
    ("offset",-1),("offset",True),("pins","MSFT"),
    ("confirmed_scope","ALPACA_TRADING"),
])
def test_invalid_roster_scope_refuses_before_credentials(field,value):
    opts={"seconds":15,"offset":0,"pins":["MSFT","SPY"],
          "confirmed_scope":native.SCOPE}
    opts[field]=value
    with pytest.raises(ValueError,match="R16_NTP_IEX_RESEARCH_EXACT_DATA_ONLY_SCOPE_REQUIRED"):
        native.roster(**opts)


@pytest.mark.parametrize("damage",[
    "fake_quote","fake_callback","wrong_utc","wrong_ntp_samples",
    "native_account_occupied","native_head_changed","missing_ack",
    "foreign_endpoint","reconnect","flat_grant","wrong_raw_type",
    "quote_count_changed","unexpected_field",
])
def test_native_ntp_feed_false_data_or_financial_grant_does_not_promote(damage):
    v=inputs()
    r=v["raw"]
    if damage=="fake_quote":r["per_symbol_quote_diagnostics"]["S002"]["accepted"]=5
    elif damage=="fake_callback":r["per_symbol_quote_diagnostics"]["S002"]["fresh_callbacks"]=1
    elif damage=="wrong_utc":v["ntp"].max_uncertainty_ms=1500
    elif damage=="wrong_ntp_samples":v["ntp"].samples_verified=0
    elif damage=="native_account_occupied":v["roots_after"]["all_twelve_distinct_and_empty"]=False
    elif damage=="native_head_changed":v["after"]["selected_native_head"]="0"*64
    elif damage=="missing_ack":r["subscribed"]=False
    elif damage=="foreign_endpoint":r["endpoint"]="wss://stream.data.alpaca.markets/v2/sip"
    elif damage=="reconnect":r["reconnects"]=1
    elif damage=="flat_grant":r["result"]["paper_startup_authorized"]=True
    elif damage=="wrong_raw_type":v["raw"]="forged"
    elif damage=="quote_count_changed":r["quote_count"]=100
    elif damage=="unexpected_field":r["paper_fill_authorized"]=True
    with pytest.raises((ValueError,KeyError,TypeError)):
        native.safe_result(**v)


def test_original_selected_version_safe_lease_refuses_host_development_python():
    with pytest.raises((ValueError,TypeError)):
        native.ORIGINAL["require_original_selected_modules"]()


@pytest.mark.asyncio
async def test_old_host_clock_imported_observer_cannot_open_real_socket_or_keys():
    with pytest.raises(ValueError,match="UNQUALIFIED_HOST_CLOCK_REAL_FEED_DISABLED"):
        await old.observe(
            seconds=20,confirmed_scope=old.SCOPE,
            credential_reader=lambda _:pytest.fail(
                "MUST_REFUSE_BEFORE_PRIVATE_ALPACA_KEYS"))


def test_old_host_clock_probe_cli_is_disabled_before_credentials(monkeypatch,capsys):
    monkeypatch.setattr(
        old.Credentials,"load",
        lambda _:pytest.fail("DISABLED_HOST_CLOCK_MUST_NOT_READ_PRIVATE_CONFIG"))
    monkeypatch.setattr(
        old,"observe",
        lambda **kwargs:pytest.fail("DISABLED_HOST_CLOCK_MUST_NOT_CONNECT_IEX"))
    assert old.main([
        "--execute-data-only",
        "--confirm-scope",old.SCOPE,"--seconds","20"])==2
    val=json.loads(capsys.readouterr().out)
    assert val["status"]=="R16_HOST_WINDOWS_CLOCK_LIVE_RESEARCH_DISABLED_USE_ORIGINAL_NATIVE_NTP"
    assert val["financial_operating_gates_accepted"]==0
    assert val["paper_start_authorized"] is False


def test_new_native_observer_no_network_preflight_does_not_load_credentials(monkeypatch):
    monkeypatch.setattr(
        native.Credentials,"load",
        lambda path:pytest.fail("NO_KEYS_FOR_INSPECT"))
    with pytest.raises(ValueError,match="R16_NTP_IEX_ORIGINAL_RESEARCH_PLANNER_REQUIRED"):
        native.inspect(offset=0,pins=("MSFT","SPY"))
