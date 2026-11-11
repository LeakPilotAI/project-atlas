"""Single-read-only-Alpaca-IEX-REST-access tests; never an order."""
import copy
import io
import json
from datetime import UTC,datetime,timedelta
from email.message import Message

import pytest

from app.investment.alpaca_iex import Credentials
from scripts.observation_runtime import alpaca_iex_rest_access_probe as rest


def quote(*,age=30,now=1794385732,symbol="MSFT"):
    observed=datetime.fromtimestamp(now-age,UTC).isoformat().replace("+00:00","Z")
    return {"symbol":symbol,
            "quote":{"t":observed,"bp":100,"ap":101,"bs":12,"as":11,
                     "bx":"V","ax":"V"}}


def test_stale_latest_rest_quote_never_becomes_execution_entitlement():
    now=1794385732
    data=quote(now=now,age=41624)
    old=copy.deepcopy(data)
    r=rest.interpret_latest(data,symbol="MSFT",observed_at=now)
    assert data==old
    assert r["schema"]==rest.SCHEMA
    assert r["reported_quote_age_seconds"]==41624
    assert r["http_data_endpoint_responded"] is True
    assert r["quote_timestamp_within_five_seconds_of_UNQUALIFIED_host_clock"] is False
    assert r["status"]=="LATEST_IEX_QUOTE_TIMESTAMP_STALE_OR_UNCERTAIN"
    assert r["raw_bid_ask_prices_exposed"] is False
    assert r["diagnostic_host_clock_is_not_independent_financial_utc"] is True
    assert not any(r[k] for k in ("independent_contract_license_verified",
                                 "continuous_quote_delivery_verified",
                                 "native_qualified_source_issuer_enrolled",
                                 "market_quotes_for_execution_authorized",
                                 "financial_operating_gate_accepted",
                                 "paper_start_authorized","live_trading_authorized"))
    assert r["account_files_written"]==r["paper_orders_created"]==0


@pytest.mark.parametrize("age",[-5,-1,0,1,5,6,31,86400])
def test_quote_age_is_diagnostic_only_and_never_a_financial_grant(age):
    now=1794385732
    r=rest.interpret_latest(quote(age=age,now=now),symbol="MSFT",
                            observed_at=now)
    assert r["quote_timestamp_within_five_seconds_of_UNQUALIFIED_host_clock"] is (0<=age<=5)
    assert r["financial_operating_gate_accepted"] is False
    assert r["market_quotes_for_execution_authorized"] is False
    assert r["live_trading_authorized"] is False


@pytest.mark.parametrize("damage",[
    "wrong_symbol","missing_symbol","missing_quote","wrong_quote",
    "missing_timestamp","wrong_timestamp","naive_timestamp",
    "foreign_timezone","malformed_timestamp","extra_field","empty_symbol",
    "noninteger_clock","future_invalid_clock",
])
def test_reject_malformed_or_foreign_latest_quote(damage):
    packet=quote()
    sym="MSFT"
    now=1794385732
    if damage=="wrong_symbol":sym="SPY"
    elif damage=="missing_symbol":packet.pop("symbol")
    elif damage=="missing_quote":packet.pop("quote")
    elif damage=="wrong_quote":packet["quote"]=[]
    elif damage=="missing_timestamp":packet["quote"].pop("t")
    elif damage=="wrong_timestamp":packet["quote"]["t"]=None
    elif damage=="naive_timestamp":packet["quote"]["t"]="2026-11-11T00:00:00"
    elif damage=="foreign_timezone":packet["quote"]["t"]="2026-11-11T00:00:00-06:00"
    elif damage=="malformed_timestamp":packet["quote"]["t"]="not a timestamp"
    elif damage=="extra_field":packet["not_seen"]="unexpected"
    elif damage=="empty_symbol":sym=""
    elif damage=="noninteger_clock":now="2026-11-11"
    elif damage=="future_invalid_clock":now=0
    with pytest.raises(ValueError):
        rest.interpret_latest(packet,symbol=sym,observed_at=now)


class StubResponse:
    status=200
    def __init__(self,url,payload,*,status=200,content="application/json"):
        self._url=url
        self.status=status
        self._payload=json.dumps(payload).encode()
        self.headers=Message()
        self.headers.add_header("Content-Type",content)
        self.closed=False
    def geturl(self):return self._url
    def read(self,n):return self._payload[:n]
    def __enter__(self):return self
    def __exit__(self,*args):self.closed=True


class StubOpener:
    def __init__(self,data):
        self.data=data
        self.called=0
        self.request=None
        self.response=None
    def open(self,req,timeout):
        self.called+=1
        self.request=req
        assert timeout==8
        assert req.full_url=="https://data.alpaca.markets/v2/stocks/MSFT/quotes/latest?feed=iex"
        assert req.get_method()=="GET"
        assert req.headers["Apca-api-key-id"]=="DUMMY_123456789"
        assert req.headers["Apca-api-secret-key"]=="DUMMY_123456789"
        self.response=StubResponse(req.full_url,self.data)
        return self.response


def test_exact_data_only_one_get_authenticated_response_never_financial(monkeypatch):
    monkeypatch.setattr(rest,"inspect_selected_data_only",lambda:{
        "selected_revision":14,"trading_authorized":False,
        "provider_rights_independently_accepted":False})
    opener=StubOpener(quote(age=42000))
    credentials_used=[]
    def fetch(path):
        credentials_used.append(path)
        return Credentials("DUMMY_123456789","DUMMY_123456789")
    result=rest.probe(symbol="MSFT",confirmed_scope=rest.SCOPE,
                      now=1794385732,credential_reader=fetch,opener=opener)
    assert opener.called==1 and opener.response.closed
    assert credentials_used==[rest.ROOT/"config/alpaca.env"]
    assert result["reported_quote_age_seconds"]==42000
    assert result["quote_timestamp_within_five_seconds_of_UNQUALIFIED_host_clock"] is False
    assert result["financial_operating_gate_accepted"] is False
    assert result["paper_start_authorized"] is False


@pytest.mark.parametrize("bad_scope,bad_symbol",[
    ("WRONG","MSFT"),(None,"MSFT"),("","MSFT"),
    (rest.SCOPE,"msft"),(rest.SCOPE,"A/B"),(rest.SCOPE,""),
    (rest.SCOPE,"LONGSYMBOL1234567"),
])
def test_scope_and_symbol_refused_before_credentials_and_network(
        monkeypatch,bad_scope,bad_symbol):
    monkeypatch.setattr(rest,"inspect_selected_data_only",
                        lambda:pytest.fail("must refuse before selected read"))
    with pytest.raises(ValueError,match="EXPLICIT_EXACT_DATA_ONLY_SCOPE"):
        rest.probe(symbol=bad_symbol,confirmed_scope=bad_scope,
                   credential_reader=lambda _:pytest.fail("credentials never"),
                   opener=object())


def test_wrong_release_refused_before_credentials(monkeypatch):
    monkeypatch.setattr(rest,"inspect_selected_data_only",lambda:{
        "selected_revision":13,"trading_authorized":False,
        "provider_rights_independently_accepted":False})
    with pytest.raises(ValueError,match="SELECTED_R15_NONFINANCIAL"):
        rest.probe(symbol="MSFT",confirmed_scope=rest.SCOPE,
                   credential_reader=lambda _:pytest.fail("not opened"),
                   opener=object())


def test_selected_source_cannot_declare_provider_rights_before_test(monkeypatch):
    monkeypatch.setattr(rest,"inspect_selected_data_only",lambda:{
        "selected_revision":14,"trading_authorized":False,
        "provider_rights_independently_accepted":True})
    with pytest.raises(ValueError,match="SELECTED_R15_NONFINANCIAL"):
        rest.probe(symbol="MSFT",confirmed_scope=rest.SCOPE,
                   credential_reader=lambda _:pytest.fail("not opened"),
                   opener=object())


def test_wrong_config_path_refused_without_credentials(monkeypatch):
    monkeypatch.setattr(rest,"inspect_selected_data_only",lambda:{
        "selected_revision":14,"trading_authorized":False,
        "provider_rights_independently_accepted":False})
    with pytest.raises(ValueError,match="LOCAL_EXACT_CONFIG_PATH"):
        rest.probe(symbol="MSFT",confirmed_scope=rest.SCOPE,
                   credential_path=rest.ROOT/"config/foreign.env",
                   credential_reader=lambda _:pytest.fail("not opened"),
                   opener=object())


def test_cli_offline_inspect_does_not_read_credentials_or_contact_provider(monkeypatch,capsys):
    monkeypatch.setattr(rest.Credentials,"load",lambda *_:pytest.fail("credentials"))
    monkeypatch.setattr(rest.urllib.request,"build_opener",lambda *_:pytest.fail("network"))
    assert rest.main(["--inspect"])==0
    status=json.loads(capsys.readouterr().out)
    assert status["credentials_read"] is False
    assert status["network_called"] is False
    assert status["financial_operating_gate_accepted"] is False
    assert rest.main(["--inspect","--confirm-scope",rest.SCOPE])==2


def test_real_rest_mode_requires_scope_and_redacts_errors(capsys):
    assert rest.main(["--execute-data-only","--symbol","MSFT"])==2
    row=json.loads(capsys.readouterr().out)
    assert row["status"]=="DATA_ONLY_ENDPOINT_REFUSED"
    assert row["financial_operating_gate_accepted"] is False
