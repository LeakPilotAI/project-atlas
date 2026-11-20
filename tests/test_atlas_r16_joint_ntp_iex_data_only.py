"""Selected R16 original native independent UTC + IEX transport integration.

Pure synthetic time/quote tests exercise safety gates. Actual production
module and Windows network observations are separately run ONLY from the
immovable installed R16 D: executable, never by this C: pytest runner.
"""
from __future__ import annotations

import copy
import time

import pytest

from scripts.observation_runtime import atlas_r16_joint_ntp_iex_data_only as joint


class FakeOriginalClock:
    def __init__(self):
        self.revoked=False
        self.verified=True
        self.source=joint.ntp_module.SOURCE
        self.timestamp=1794420000
    def runtime_sample(self):
        if self.revoked:
            raise ValueError("REVOKED")
        return {
            "schema":"QD_AUTO_CLOCK_V3",
            "utc":self.timestamp,
            "monotonic_ns":time.perf_counter_ns(),
            "uncertainty_ms":140,
            "source_id":self.source,
        }
    def verify_runtime_sample(self,sample):
        return self.verified and not self.revoked
    def revoke(self):
        self.revoked=True


def observer():
    fake=FakeOriginalClock()
    o=joint.NativeUtcUpperBound(fake)
    o()
    o.last_sample=None
    o()
    assert o.samples_verified==2
    assert o.max_uncertainty_ms==140
    return o,fake


def fixture(*, symbol="MSFT"):
    accepted={symbol}
    rows={symbol:{"received":1,"accepted":1,"rejected":0,"fresh_callbacks":1}}
    data={
        "authenticated":True,"subscribed":True,
        "quote_count":1,
        "fresh_quote_observed_during_connection":True,
        "result":{"connection":"DISCONNECTED"},
        "per_symbol_quote_diagnostics":rows,
    }
    origin={"selected_native_head":joint.R16_HEAD}
    roots={"all_twelve_distinct_and_empty":True}
    return {
        "data":data,"symbols":(symbol,),
        "observed":accepted,"callbacks":1,
        "native_utc":observer()[0],
        "elapsed_seconds":30.0,
        "selected_before":origin,"selected_after":copy.deepcopy(origin),
        "roots_before":roots,"roots_after":copy.deepcopy(roots),
    }


def test_explicit_scope_blocks_unauthorized_websocket_before_keys():
    assert joint.scope(seconds=20,symbols=["MSFT"],confirmed_scope=joint.SCOPE)==("MSFT",)
    assert joint.scope(seconds=60,symbols=["MSFT","SPY"],confirmed_scope=joint.SCOPE)==("MSFT","SPY")


@pytest.mark.parametrize("seconds,symbols,scope",[
    (9,["MSFT"],joint.SCOPE),(61,["MSFT"],joint.SCOPE),
    (True,["MSFT"],joint.SCOPE),("30",["MSFT"],joint.SCOPE),
    (30,[],joint.SCOPE),(30,["MSFT","MSFT"],joint.SCOPE),
    (30,["MSFT","SPY","AAPL"],joint.SCOPE),
    (30,["msft"],joint.SCOPE),(30,["BTC/USD"],joint.SCOPE),
    (30,["MSFT"],None),(30,["MSFT"],"TRADING"),
])
def test_wrong_scope_refused(seconds,symbols,scope):
    with pytest.raises(ValueError,match="EXACT_BOUNDED_DATA_ONLY_SCOPE_REQUIRED"):
        joint.scope(seconds=seconds,symbols=symbols,confirmed_scope=scope)


def test_native_utc_sample_is_conservative_and_retains_independent_source():
    clock,fake=observer()
    assert clock.samples_verified==2
    assert clock.max_uncertainty_ms==140
    value=clock()
    assert fake.timestamp<=value<=fake.timestamp+1.40
    assert clock()>=value


@pytest.mark.parametrize("changed,expected",[
    ("source","GENUINE_NATIVE_CLOCK_SAMPLE_REFUSED"),
    ("uncertainty","GENUINE_NATIVE_CLOCK_SAMPLE_REFUSED"),
    ("verify","GENUINE_NATIVE_CLOCK_SAMPLE_REFUSED"),
])
def test_forged_or_overuncertain_native_time_fails_closed(changed,expected):
    o=FakeOriginalClock()
    if changed=="source":o.source="HOST_WINDOWS_CLOCK"
    elif changed=="uncertainty":
        original=o.runtime_sample
        def elevated():
            s=original()
            s["uncertainty_ms"]=1001
            return s
        o.runtime_sample=elevated
    else:o.verified=False
    with pytest.raises(ValueError,match=expected):
        joint.NativeUtcUpperBound(o)()


def test_revoked_native_clock_cannot_refresh_for_any_feed():
    o=FakeOriginalClock()
    b=joint.NativeUtcUpperBound(o)
    b()
    b.last_sample=None
    o.revoke()
    with pytest.raises(ValueError,match="REVOKED"):
        b()


def test_authenticated_two_peer_and_iex_same_process_pure_admission_only():
    item=fixture()
    result=joint.admit(**item)
    assert result["status"]=="R16_SAME_PROCESS_NATIVE_NTP_AND_IEX_FRESH_QUOTE_OBSERVED"
    assert result["selected_native_revision"]==15
    assert result["selected_native_head"]==joint.R16_HEAD
    assert result["same_process_independent_utc_quote_freshness_verified"] is True
    assert result["independent_utc_upper_bound_samples_verified"]>=2
    assert result["independent_utc_uncertainty_bound_max_ms"]==140
    assert result["fresh_quote_callbacks"]==1
    assert result["provider_reconnects"]==0
    assert result["provider_rights_independently_accepted"] is False
    assert result["independent_financial_clock_lease_accepted"] is False
    assert result["continuous_financial_source_published"] is False
    assert result["paper_start_authorized"] is False
    assert result["live_trading_authorized"] is False
    assert result["native_financial_account_files_created"]==0
    assert result["paper_orders_created"]==result["live_orders_created"]==0
    assert "SECRET" not in str(result)
    assert "bid" not in str(result).lower()


@pytest.mark.parametrize("damage",[
    "unverified_utc","unqualified_uncertainty","new_native_head",
    "native_root_occupied","different_native_roots","no_fresh_quote",
    "bad_subscription","no_callback","fake_connection_not_closed",
    "forged_per_symbol_counts","unauthorized_callback_count",
    "bad_elapsed","finance_fill_invented","not_a_provider_result",
])
def test_mixed_or_fake_provider_and_clock_evidence_refuses(damage):
    item=fixture()
    if damage=="unverified_utc":item["native_utc"].samples_verified=1
    elif damage=="unqualified_uncertainty":item["native_utc"].max_uncertainty_ms=1001
    elif damage=="new_native_head":item["selected_after"]["selected_native_head"]="0"*64
    elif damage=="native_root_occupied":item["roots_after"]["all_twelve_distinct_and_empty"]=False
    elif damage=="different_native_roots":item["roots_after"]["new"]="FORGED"
    elif damage=="no_fresh_quote":item["data"]["quote_count"]=0
    elif damage=="bad_subscription":item["data"]["subscribed"]=False
    elif damage=="no_callback":item["callbacks"]=0
    elif damage=="fake_connection_not_closed":item["data"]["result"]["connection"]="CONNECTED"
    elif damage=="forged_per_symbol_counts":
        item["data"]["per_symbol_quote_diagnostics"]["MSFT"]["rejected"]=1
    elif damage=="unauthorized_callback_count":
        item["data"]["per_symbol_quote_diagnostics"]["MSFT"]["fresh_callbacks"]=2
    elif damage=="bad_elapsed":item["elapsed_seconds"]=180.0
    elif damage=="finance_fill_invented":item["data"]["paper_fill_authorized"]=True
    elif damage=="not_a_provider_result":item["data"]="FRAUDULENT_RESPONSE"
    with pytest.raises((ValueError,TypeError,KeyError)):
        joint.admit(**item)


def test_offline_inspect_does_not_touch_clock_or_credentials(monkeypatch):
    monkeypatch.setattr(
        joint,"NativeVersionSafePaperOperatorClock",
        lambda **kwargs:pytest.fail("INSPECT_MUST_NOT_CONNECT_NTP"))
    monkeypatch.setattr(
        joint.Credentials,"load",
        lambda _:pytest.fail("INSPECT_MUST_NOT_READ_KEYS"))
    row=joint.inspect()
    assert row["status"]=="R16_ORIGINAL_NATIVE_NTP_IEX_DATA_ONLY_SCOPE_PRECHECK"
    assert row["network_requests"]==0 and row["credential_bytes_read"] is False
    assert row["paper_start_authorized"] is False


def test_original_native_source_pinning_refuses_c_development_interpreter():
    # No data-provider credentials or clock network needed: check local image
    # provenance before calling any operational NTP constructor.
    with pytest.raises(ValueError,match="R16_NTP_IEX_ORIGINAL_SELECTED_READONLY_PYTHON_REQUIRED"):
        joint.require_original_selected_modules()
