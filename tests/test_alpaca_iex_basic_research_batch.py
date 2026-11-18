"""Free Alpaca IEX 30-symbol single-session research survey, no money/orders."""
import asyncio
import json

import pytest
from app.investment.alpaca_iex import Credentials, IEXFeed

from scripts.observation_runtime import alpaca_iex_basic_research_batch as batch
from scripts.observation_runtime.alpaca_equity_catalog import inventory_snapshot


def catalog(n=76):
    return inventory_snapshot([
        {"class":"us_equity","symbol":f"S{i:03d}",
         "status":"active","tradable":True,"exchange":"NASDAQ","id":str(i)}
        for i in range(n)],captured_at="2026-11-10T14:00:00+00:00")


def admitted(monkeypatch):
    monkeypatch.setattr(batch,"inspect_selected_data_only",lambda:{
        "selected_revision":14,"trading_authorized":False,
        "provider_rights_independently_accepted":False})


def offline_plan(monkeypatch,offset=0,monitors=()):
    admitted(monkeypatch)
    return batch.prepare(scope=batch.SCOPE,offset=offset,
                         pinned_research_symbols=monitors,
                         snapshot=catalog())


def sample(roster,*,authenticated=True,subscribed=True,fresh=False):
    stats={s:{"received":0,"accepted":0,"rejected":0,"fresh_callbacks":0}
           for s in roster["requested_symbols"]}
    if fresh:
        stats[roster["requested_symbols"][0]]={
            "received":1,"accepted":1,"rejected":0,"fresh_callbacks":0}
    return {"endpoint":"wss://stream.data.alpaca.markets/v2/iex",
            "feed":"IEX","authenticated":authenticated,
            "subscribed":subscribed,"reconnects":0,
            "fresh_quote_observed_during_connection":fresh,
            "per_symbol_quote_diagnostics":stats,
            "quote_count":1 if fresh else 0,
            "result":{"connection":"DISCONNECTED",
                      "paper_startup_authorized":False,
                      "quotes":[{"bid":"100","ask":"101"}]}}


def test_one_batch_is_strictly_30_or_fewer_research_symbols(monkeypatch):
    p=offline_plan(monkeypatch,offset=17,monitors=["S000"])
    assert p["requested_symbol_count"]==30
    assert p["requested_symbols"][0]=="S000"
    assert p["next_offset"]==46
    assert p["catalog_count"]==76
    assert p["authenticated_iex_connection"] is False
    assert p["paper_execution_authorized"] is False


def test_research_catalog_reachable_in_three_disjoint_single_connection_plans(monkeypatch):
    source=catalog()
    admitted(monkeypatch)
    cursor=0
    seen=[]
    for expected in (30,30,16):
        p=batch.prepare(scope=batch.SCOPE,offset=cursor,snapshot=source)
        assert p["requested_symbol_count"]==expected
        assert len(p["requested_symbols"])==len(set(p["requested_symbols"]))
        seen.extend(p["requested_symbols"])
        cursor=p["next_offset"]
    assert cursor==76 and len(set(seen))==76
    assert seen==[r["symbol"] for r in source["rows"]]


@pytest.mark.parametrize("source",[
    None, "", "ANY", "ALPACA_PAPER_AUTO_START",
])
def test_wrong_session_scope_refuses_before_credentials(monkeypatch,source):
    admitted(monkeypatch)
    with pytest.raises(ValueError,match="EXPLICIT_DATA_ONLY_SCOPE"):
        batch.prepare(scope=source,offset=0,snapshot=catalog())


@pytest.mark.parametrize("bad",[
    -1,True,1.5,"0",
])
def test_noninteger_and_negative_cursor_refused(monkeypatch,bad):
    admitted(monkeypatch)
    with pytest.raises(ValueError,match="CURSOR_INVALID"):
        batch.prepare(scope=batch.SCOPE,offset=bad,snapshot=catalog())


def test_selected_runtime_financial_promotion_refused(monkeypatch):
    monkeypatch.setattr(batch,"inspect_selected_data_only",lambda:{
        "selected_revision":14,"trading_authorized":False,
        "provider_rights_independently_accepted":True})
    with pytest.raises(ValueError,match="EXACT_SELECTED"):
        batch.prepare(scope=batch.SCOPE,offset=0,snapshot=catalog())


@pytest.mark.parametrize("kind",[
    "foreign_host","stale_connection","stream_missing_ack","fake_reconnect",
    "fake_data_grant","extra_symbol","missing_symbol","fake_quote_count",
    "nonint_quote_count","fake_callback","corrupt_counter","future_quote_count",
    "nonboolean_auth","bad_stats","fresh_without_quote",
])
def test_report_rejects_unverified_connection_or_financial_counter_spoof(
        monkeypatch,kind):
    p=offline_plan(monkeypatch)
    d=sample(p)
    if kind=="foreign_host":d["endpoint"]="wss://example.com"
    elif kind=="stale_connection":d["result"]["connection"]="CONNECTED"
    elif kind=="stream_missing_ack":d["result"].pop("paper_startup_authorized")
    elif kind=="fake_reconnect":d["reconnects"]=1
    elif kind=="fake_data_grant":d["result"]["paper_startup_authorized"]=True
    elif kind=="extra_symbol":d["per_symbol_quote_diagnostics"]["AVGO"]={
        "received":0,"accepted":0,"rejected":0,"fresh_callbacks":0}
    elif kind=="missing_symbol":d["per_symbol_quote_diagnostics"].pop(
        p["requested_symbols"][0])
    elif kind=="fake_quote_count":d["quote_count"]=1
    elif kind=="nonint_quote_count":d["quote_count"]=True
    elif kind=="fake_callback":d["per_symbol_quote_diagnostics"][
        p["requested_symbols"][0]]["fresh_callbacks"]=1
    elif kind=="corrupt_counter":d["per_symbol_quote_diagnostics"][
        p["requested_symbols"][0]]["received"]=1
    elif kind=="future_quote_count":d["quote_count"]=-1
    elif kind=="nonboolean_auth":d["authenticated"]=1
    elif kind=="bad_stats":d["per_symbol_quote_diagnostics"]=[]
    elif kind=="fresh_without_quote":d["fresh_quote_observed_during_connection"]=True
    with pytest.raises((ValueError,TypeError,KeyError)):
        batch.sanitize(p,d,seconds=12)


def test_successful_provider_ack_without_quotes_is_not_current_market_source(monkeypatch):
    p=offline_plan(monkeypatch,offset=100)
    r=batch.sanitize(p,sample(p),seconds=12)
    assert r["status"]=="AUTHENTICATED_30_SYMBOL_DATA_ONLY_OBSERVATION"
    assert r["catalog_count"]==76
    assert r["requested_symbols_count"]==30
    assert r["quote_messages_received"]==0
    assert r["symbols_with_accepted_quote"]==0
    assert r["authenticated"] is True
    assert r["all_requested_symbols_subscription_acknowledged"] is True
    assert r["current_qualified_market_source"] is False
    assert r["independent_provider_contract_rights_accepted"] is False
    assert r["paper_start_authorized"] is False
    assert r["orders_created"]==0
    assert "quotes" not in r and "bid" not in str(r) and "ask" not in str(r)


def test_one_fresh_quote_is_research_only_and_prices_never_escape(monkeypatch):
    p=offline_plan(monkeypatch)
    r=batch.sanitize(p,sample(p,fresh=True),seconds=12)
    assert r["quote_messages_received"]==1
    assert r["symbols_with_accepted_quote"]==1
    assert r["fresh_quotes_seen_during_connection"] is True
    assert r["raw_quotes_or_prices_published"] is False
    assert r["paper_start_authorized"] is False
    assert "100" not in json.dumps(r)


def test_one_research_survey_uses_real_iexfeed_one_no_reconnect_async_session(monkeypatch):
    admitted(monkeypatch)
    calls=[]
    async def fake_runner(feed,credentials,seconds):
        assert type(feed) is IEXFeed
        assert feed.position_symbols is None
        assert len(feed.symbols)==30
        assert isinstance(credentials,Credentials)
        calls.append((tuple(feed.symbols),seconds))
        p=batch.prepare(scope=batch.SCOPE,offset=2,snapshot=catalog())
        return sample(p)
    result=asyncio.run(batch.observe_one(
        scope=batch.SCOPE,offset=2,snapshot=catalog(),seconds=12,
        credential_loader=lambda:Credentials("DUMMY_TEST","DUMMY_SECRET"),
        runner=fake_runner))
    assert len(calls)==1
    assert result["websocket_closed_after_batch"] is True
    assert result["next_research_offset_uncommitted"]==32
    assert result["financial_position_owner_verified"] is False
    assert result["cursor_durably_committed"] is False


@pytest.mark.parametrize("duration",[0,4,21,30,"12",True])
def test_no_unbounded_or_ambiguous_connection_duration(monkeypatch,duration):
    admitted(monkeypatch)
    with pytest.raises(ValueError,match="BOUNDED_SESSION_SECONDS"):
        asyncio.run(batch.observe_one(scope=batch.SCOPE,offset=0,
                   snapshot=catalog(),seconds=duration,
                   credential_loader=lambda:pytest.fail("credentials must not be read")))


def test_cli_inspect_is_truly_offline(monkeypatch,capsys):
    admitted(monkeypatch)
    monkeypatch.setattr(batch.Credentials,"load",
        lambda _:pytest.fail("inspection must not open credentials"))
    assert batch.main(["--inspect","--offset","100","--monitor-research","MSFT"])==0
    row=json.loads(capsys.readouterr().out)
    assert row["schema"]==batch.SCHEMA
    assert row["requested_symbols_count"]==30
    assert row["data_provider_called"] is False
    assert row["paper_start_authorized"] is False


def test_cli_live_mode_requires_specific_scope_without_provider_network(capsys):
    assert batch.main(["--execute-data-only","--seconds","12"])==2
    row=json.loads(capsys.readouterr().out)
    assert row["status"]=="DATA_ONLY_SCOPE_REFUSED"
    assert row["prices_exposed"] is False
    assert row["orders_created"]==0

def test_selected_r22_research_roster_and_report_remain_research_only(monkeypatch):
    monkeypatch.setattr(batch, "inspect_selected_data_only", lambda: {
        "selected_revision": 22, "trading_authorized": False,
        "provider_rights_independently_accepted": False})
    roster = batch.prepare(scope=batch.SCOPE, offset=0, snapshot=catalog())
    assert roster["selected_native_release"] == "R22"
    assert roster["requested_symbol_count"] == 30
    report = batch.sanitize(roster, sample(roster), seconds=12)
    assert report["selected_native_release"] == "R22"
    assert report["current_qualified_market_source"] is False
    assert report["paper_start_authorized"] is False
    assert report["raw_quotes_or_prices_published"] is False


@pytest.mark.parametrize("revision", [13, 15, 21, 23, True, "22"])
def test_nonselected_or_unknown_iex_revision_blocks_roster_before_transport(
        monkeypatch, revision):
    monkeypatch.setattr(batch, "inspect_selected_data_only", lambda: {
        "selected_revision": revision, "trading_authorized": False,
        "provider_rights_independently_accepted": False})
    with pytest.raises(ValueError, match="EXACT_SELECTED"):
        batch.prepare(scope=batch.SCOPE, offset=0, snapshot=catalog())
