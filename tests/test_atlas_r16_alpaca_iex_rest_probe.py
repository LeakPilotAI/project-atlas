"""Selected R16 Alpaca IEX data-only one-GET: no financial acceptance.

No real network or credentials in tests. Genuine operator call to
--execute-data-only is separate and bounded to a single GET if approved.
"""
from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path

import pytest

from app.investment.alpaca_iex import Credentials
from scripts.observation_runtime import atlas_r16_alpaca_iex_rest_probe as r16


UTC_OBS=1794420000


def _payload(*, symbol="MSFT", quote_seconds=UTC_OBS):
    return {
        "symbol":symbol,
        "quote":{"t":datetime.fromtimestamp(
            quote_seconds, UTC).isoformat().replace("+00:00","Z")},
    }


class Response:
    def __init__(self,payload, *,status=200,endpoint=None,ctype="application/json"):
        self.status=status
        self._url=endpoint
        self._content=json.dumps(payload).encode()
        self.headers=Message()
        self.headers["Content-Type"]=ctype
    def geturl(self):return self._url
    def read(self,size):
        assert size==r16.LIMIT+1
        return self._content
    def __enter__(self):return self
    def __exit__(self, exc_type,exc,tb):return False


def _trial(monkeypatch,payload=None,*,status=200,ctype="application/json"):
    calls=[]
    def fake_creds(path):
        assert path==r16.CONFIG
        calls.append("CREDENTIALS")
        return Credentials(key="DISPOSABLE-TEST-KEY",secret="DISPOSABLE-TEST-SECRET")
    class Opener:
        def open(self,request,timeout):
            assert timeout==8
            assert request.get_method()=="GET"
            assert request.full_url=="https://data.alpaca.markets/v2/stocks/MSFT/quotes/latest?feed=iex"
            assert request.get_header("Apca-api-key-id")=="DISPOSABLE-TEST-KEY"
            assert request.get_header("Apca-api-secret-key")=="DISPOSABLE-TEST-SECRET"
            assert request.get_header("Accept")=="application/json"
            calls.append("ONE_DATA_ONLY_GET")
            return Response(payload or _payload(),status=status,
                            endpoint=request.full_url,ctype=ctype)
    return r16.probe(
        confirmed_scope=r16.SCOPE,symbol="MSFT",
        credential_reader=fake_creds,opener=Opener(),observed_at=UTC_OBS),calls


def test_current_real_selected_r16_no_network_inspection_is_no_financial_authority():
    v=r16.inspect()
    assert v["selected_native_revision"]==15
    assert v["status"]=="R16_SELECTED_RESEARCH_ONLY_NO_NETWORK"
    assert v["network_requests"]==0
    assert v["credentials_read"] is False
    assert v["financial_operating_gates_accepted"]==0
    assert v["paper_start_authorized"] is False
    assert v["live_trading_authorized"] is False
    assert v["independent_provider_license_verified"] is False
    assert v["full_robinhood_equity_etf_coverage_verified"] is False


def test_r16_one_exact_synthetic_rest_data_get_is_not_financial_rights(monkeypatch):
    row,calls=_trial(monkeypatch)
    assert calls==["CREDENTIALS","ONE_DATA_ONLY_GET"]
    assert row["schema"]==r16.SCHEMA
    assert row["status"]=="R16_BOUNDED_IEX_HTTPS_DATA_ONLY_OBSERVED_NO_FINANCIAL_GRANT"
    assert row["observed_symbol"]=="MSFT"
    assert row["quote_timestamp_present"] is True
    assert row["quote_timestamp_within_five_seconds_of_unqualified_host_clock"] is True
    assert row["http_data_endpoint_responded"] is True
    assert row["network_requests"]==1
    assert row["raw_bid_ask_prices_exposed"] is False
    assert row["credentials_exposed"] is False
    assert row["independent_provider_license_verified"] is False
    assert row["financial_operating_gates_accepted"]==0
    assert row["paper_start_authorized"] is False
    assert row["live_trading_authorized"] is False
    assert row["paper_orders_created"]==row["real_money_orders_created"]==0
    assert "DISPOSABLE-TEST-SECRET" not in str(row)


def test_stale_quote_is_research_only_without_source_authority(monkeypatch):
    row,calls=_trial(monkeypatch,_payload(quote_seconds=UTC_OBS-100))
    assert calls==["CREDENTIALS","ONE_DATA_ONLY_GET"]
    assert row["quote_timestamp_within_five_seconds_of_unqualified_host_clock"] is False
    assert row["continuous_quote_source_and_freshness_verified"] is False
    assert row["financial_operating_gates_accepted"]==0


@pytest.mark.parametrize("scope,symbol",[
    (None,"MSFT"),("SYNTHETIC_APPROVED","MSFT"),
    (r16.SCOPE,"msft"),(r16.SCOPE,"BTC/USD"),
    (r16.SCOPE,"MSFT;DROP"),(r16.SCOPE,"A"*16),
])
def test_bad_scope_or_market_symbol_refused_pre_credentials(monkeypatch,scope,symbol):
    def forbidden(*args,**kwargs):
        pytest.fail("INVALID_SCOPE_MUST_NOT_OPEN_CREDENTIALS_OR_PROVIDER")
    with pytest.raises(ValueError,match="R16_IEX_EXACT_BOUNDED_DATA_ONLY_SCOPE_REQUIRED"):
        r16.probe(confirmed_scope=scope,symbol=symbol,credential_reader=forbidden,opener=forbidden)


@pytest.mark.parametrize("field,value",[
    ("selected_revision",14),
    ("selected_native_head","a"*64),
    ("installed_artifact_digest","f"*64),
    ("code_selection_accepted",False),
    ("provider_source_operational_accepted",True),
    ("paper_start_authorized",True),
    ("financial_writer_operational_accepted",True),
    ("live_trading_authorized",True),
])
def test_changed_selected_r16_or_promoted_financial_claim_refused(monkeypatch,field,value):
    authentic=r16.selected_code()
    changed=copy.deepcopy(authentic)
    changed[field]=value
    monkeypatch.setattr(r16,"selected_code",lambda:changed)
    with pytest.raises(ValueError,match="R16_IEX_CURRENT_CODE_ONLY_NO_TRADING_SELECTED_REQUIRED"):
        r16.require_selected_r16_data_only()


def test_data_get_refuses_if_original_native_roots_not_empty(monkeypatch):
    originals=r16.inspect_two_lane_native_roots()
    changed=copy.deepcopy(originals)
    changed["all_twelve_distinct_and_empty"]=False
    monkeypatch.setattr(r16,"inspect_two_lane_native_roots",lambda:changed)
    with pytest.raises(ValueError,match="R16_IEX_REAL_NATIVE_ROOTS_NOT_EMPTY_REFUSE"):
        _trial(monkeypatch)


@pytest.mark.parametrize("kind",["bad_status","bad_mime","wrong_symbol","oversize"])
def test_malformed_http_provider_response_never_authorizes_account_or_order(monkeypatch,kind):
    payload=_payload()
    status,ctype=200,"application/json"
    if kind=="bad_status":status=302
    elif kind=="bad_mime":ctype="text/plain"
    elif kind=="wrong_symbol":payload["symbol"]="AAPL"
    elif kind=="oversize":payload["extra"]="A"*(r16.LIMIT+1)
    with pytest.raises((ValueError,TypeError)):
        _trial(monkeypatch,payload,status=status,ctype=ctype)


def test_current_r16_data_only_get_does_not_consume_hyperliquid_quota(monkeypatch):
    row,calls=_trial(monkeypatch)
    assert row["provider"]=="ALPACA"
    assert row["hyperliquid_data_source_not_covered"] is True
    assert len(calls)==2
    assert row["paper_start_authorized"] is False
