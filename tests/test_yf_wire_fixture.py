import asyncio
import builtins
import copy
import json
import sqlite3
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from test_market_replay_integration import fixture, quote_fixture

from scripts.observation_runtime.market_replay import ReplayStore, create_replay_app
from scripts.observation_runtime.r7e47ck_equities_budget import (
    EquitiesObservationBudget,
)
from scripts.observation_runtime.yf_wire_fixture import (
    DataFixture,
    Session,
    Step,
    VirtualDeadline,
    WireFixtureRefused,
    YFRateLimitError,
)

SOURCE=Path(__file__).resolve().parents[1]/'backend/.venv/Lib/site-packages/yfinance/data.py'
URL='https://query1.finance.yahoo.com/v8/finance/chart/SPY'
QUOTE='https://query1.finance.yahoo.com/v7/finance/quote'


def boot():return [Step('GET','COOKIE',cookie=True),Step('GET','CRUMB_BASIC',text='SYNTHETIC_CRUMB')]


def make(tmp_path,steps, *, limit=None,ceiling=30,retries=0,halt=True,deadline=None):
    budget=EquitiesObservationBudget(tmp_path/'fixture-budget.sqlite',access_approved=True,max_attempts=limit or len(steps))
    session=Session(budget,steps,timeout_ceiling=ceiling,halt_on_throttle=halt,deadline=deadline)
    return DataFixture(SOURCE,session,retries=retries),session,budget


def test_actual_pinned_sdk_fanout_debits_each_fake_hop_before_data_acknowledgement(tmp_path):
    payload={'synthetic':True};data,session,budget=make(tmp_path,boot()+[Step('GET','CHART',payload=payload)])
    assert data.request_json(URL)==payload
    assert [e['remaining_after_debit'] for e in session.events]==[2,1,0]
    assert [e['kind'] for e in session.events]==['COOKIE','CRUMB_BASIC','CHART']
    assert budget.remaining()==0 and data.report()['network_authorized'] is False
    assert data.report()['real_backend_verified'] is False


def test_sdk_transient_retry_is_an_additional_debited_attempt_with_virtual_backoff(tmp_path):
    steps=boot()+[Step('GET','CHART',error='TIMEOUT'),Step('GET','CHART',payload={'synthetic':True})]
    data,session,budget=make(tmp_path,steps,retries=1)
    assert data.request_json(URL)=={'synthetic':True}
    assert len(session.events)==4 and data.backoffs==[1] and budget.remaining()==0


def test_budget_exhaustion_stops_retry_and_latches_without_refund(tmp_path):
    steps=boot()+[Step('GET','CHART',error='TIMEOUT'),Step('GET','CHART',payload={'synthetic':True})]
    data,session,budget=make(tmp_path,steps,limit=3,retries=1)
    with pytest.raises(WireFixtureRefused):data.request_json(URL)
    assert len(session.events)==3 and budget.remaining()==0
    with pytest.raises(WireFixtureRefused):data.request_json(URL)
    assert len(session.events)==3


def test_complete_cookie_strategy_fallback_accounts_for_synthetic_consent_get_and_post(tmp_path):
    html='<input name="csrfToken" value="SYNTHETIC_CSRF"><input name="sessionId" value="SYNTHETIC_SESSION">'
    steps=[Step('GET','COOKIE'),Step('GET','COOKIE'),Step('GET','CRUMB_BASIC',text='<html>missing</html>'),
        Step('GET','CONSENT',text=html),Step('POST','COLLECT'),Step('GET','COPY',cookie=True),
        Step('GET','CRUMB_CSRF',text='SYNTHETIC_CRUMB'),Step('GET','CHART',payload={'synthetic':True})]
    data,session,budget=make(tmp_path,steps)
    assert data.request_json(URL)=={'synthetic':True} and len(session.events)==8
    assert [e['method'] for e in session.events].count('POST')==1 and budget.remaining()==0


def test_redirect_hop_and_consent_form_post_are_each_debited(tmp_path):
    consent='https://consent.yahoo.com/v2/collectConsent?sessionId=SYNTHETIC_SESSION'
    html='<form action="/v2/collectConsent"><input name="csrfToken" value="SYNTHETIC_CSRF"></form>'
    steps=boot()+[Step('GET','CHART',status=302,location=consent),Step('GET','COLLECT',text=html),
                  Step('POST','COLLECT',payload={'synthetic':True})]
    data,session,budget=make(tmp_path,steps)
    assert data.request_json(URL)=={'synthetic':True} and len(session.events)==5 and budget.remaining()==0


def test_429_retry_with_changed_crumb_remains_bounded_and_accounted(tmp_path):
    steps=boot()+[Step('GET','CHART',status=429),Step('GET','CRUMB_CSRF',text='SYNTHETIC_CSRF_CRUMB'),Step('GET','CHART',status=429)]
    data,session,budget=make(tmp_path,steps,halt=False)
    with pytest.raises(YFRateLimitError):data.request_json(URL)
    assert len(session.events)==5 and budget.remaining()==0


def test_native_network_backends_and_user_caches_are_not_imported_or_called(tmp_path,monkeypatch):
    original=builtins.__import__
    def denied(name,*args,**kwargs):
        if name.split('.')[0] in {'yfinance','curl_cffi','requests','bs4'}:raise AssertionError('Real provider dependency imported')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',denied)
    data,session,_=make(tmp_path,boot()+[Step('GET','CHART',payload={'synthetic':True})])
    assert data.request_json(URL)=={'synthetic':True}
    assert data.cache_calls['store']>=1 and data.cache_calls['lookup']>=1
    assert all('SYNTHETIC_' not in json.dumps(event) for event in session.events)


def test_outer_request_timeout_does_not_authorize_sdk_bootstrap_default_30_seconds(tmp_path,monkeypatch):
    data,session,budget=make(tmp_path,boot()+[Step('GET','CHART',payload={})],ceiling=5)
    seen=[];original=session._request
    def capture(method,url,kwargs):
        seen.append((method,kwargs.get('timeout')))
        return original(method,url,kwargs)
    monkeypatch.setattr(session,'_request',capture)
    with pytest.raises(WireFixtureRefused):data.request_json(URL,timeout=5)
    assert seen==[('GET',30)] and session.events==[] and budget.remaining()==3


def test_missing_or_corrupt_ledger_prevents_fake_attempts_and_never_recreates_storage(tmp_path):
    data,session,budget=make(tmp_path,boot()+[Step('GET','CHART',payload={})])
    before=budget.path.read_bytes();budget.path.write_bytes(b'corrupt synthetic ledger')
    with pytest.raises(WireFixtureRefused):data.request_json(URL)
    assert session.events==[] and budget.path.read_bytes()!=before


def test_uncertain_commit_never_causes_fake_send_or_automatic_retry(tmp_path,monkeypatch):
    data,session,budget=make(tmp_path,boot()+[Step('GET','CHART',payload={})])
    original=budget.consume_before_attempt
    def uncertain():original();raise OSError('synthetic post-commit ambiguity')
    monkeypatch.setattr(budget,'consume_before_attempt',uncertain)
    with pytest.raises(WireFixtureRefused):data.request_json(URL)
    assert session.events==[] and budget.remaining()==2
    with pytest.raises(WireFixtureRefused):data.request_json(URL)
    assert budget.remaining()==2


def test_cached_sdk_response_never_overrides_latched_accounting_uncertainty(tmp_path):
    steps=boot()+[Step('GET','CHART',payload={'synthetic':True})]
    data,session,budget=make(tmp_path,steps)
    assert data.request_json(URL,cached=True)==data.request_json(URL,cached=True)=={'synthetic':True}
    assert len(session.events)==3
    with sqlite3.connect(budget.path) as db:db.execute('UPDATE budget SET attempted=0')
    with pytest.raises(WireFixtureRefused):data.request_json(URL,cached=True)


@pytest.mark.parametrize('url',['https://example.com','https://evilconsent.yahoo.com/v2/collectConsent',
    'https://query1.finance.yahoo.com/ws/obi-integration/v1/subscriptions',
    'https://user:password@query1.finance.yahoo.com/v8/finance/chart/SPY'])
def test_unapproved_origins_auth_endpoints_or_credentials_are_refused_before_debit(tmp_path,url):
    data,session,budget=make(tmp_path,boot()+[Step('GET','CHART',payload={})])
    with pytest.raises(WireFixtureRefused):data.request_json(url)
    assert session.events==[] and budget.remaining()==3


def test_sdk_data_request_to_existing_bar_quote_storage_and_snapshot(tmp_path):
    now=datetime(2026,10,20,12,1,10,tzinfo=UTC)
    chart=fixture(now-timedelta(seconds=70));quote=quote_fixture(now-timedelta(seconds=2))
    originals=copy.deepcopy((chart,quote))
    steps=boot()+[Step('GET','CHART',payload=chart),Step('GET','QUOTE',payload=quote)]
    data,session,budget=make(tmp_path,steps)
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db)
        store.ingest(data.request_json(URL),observed_at=now,asset_class='US_ETF')
        store.ingest_quote(data.request_json(QUOTE),observed_at=now,asset_class='US_ETF')
        with store.read_view():
            assert store.snapshot(['SPY'],now=now)['rows'][0]['price']==101
            assert store.quote_snapshot(['SPY'],now=now)[0]['price']==103
    assert len(session.events)==4 and budget.remaining()==0 and (chart,quote)==originals


def test_default_throttle_policy_blocks_sdk_internal_retry_without_extra_debit(tmp_path):
    steps=boot()+[Step('GET','CHART',status=429),Step('GET','CRUMB_CSRF',text='SYNTHETIC_UNUSED')]
    data,session,budget=make(tmp_path,steps)
    with pytest.raises(WireFixtureRefused):data.request_json(URL)
    assert len(session.events)==3 and budget.remaining()==1
    with pytest.raises(WireFixtureRefused):data.request_json(URL)
    assert len(session.events)==3


def test_missing_ledger_is_never_recreated_during_accounting(tmp_path):
    data,session,budget=make(tmp_path,boot()+[Step('GET','CHART',payload={})])
    original=budget.path;before=original.read_bytes();budget.path=tmp_path/'missing.sqlite'
    with pytest.raises(WireFixtureRefused):data.request_json(URL)
    assert not budget.path.exists() and original.read_bytes()==before and session.events==[]


def test_unreviewed_source_copy_is_refused_before_execution(tmp_path):
    package=tmp_path/'yfinance';package.mkdir();source=package/'data.py';source.write_bytes(SOURCE.read_bytes()+b'\n# drift\n')
    budget=EquitiesObservationBudget(tmp_path/'budget.sqlite',access_approved=True,max_attempts=3)
    session=Session(budget,boot()+[Step('GET','CHART',payload={})])
    with pytest.raises(WireFixtureRefused,match='reviewed pin'):DataFixture(source,session)
    assert budget.remaining()==3 and session.events==[]


def test_bounded_redirects_do_not_continue_consuming_remaining_budget(tmp_path):
    steps=boot()+[Step('GET','CHART',status=302,location=URL) for _ in range(6)]
    data,session,budget=make(tmp_path,steps)
    with pytest.raises(WireFixtureRefused):data.request_json(URL)
    assert len(session.events)==6 and budget.remaining()==2


def test_shared_fixture_ledger_caps_competing_sessions_without_overshoot(tmp_path):
    budget=EquitiesObservationBudget(tmp_path/'shared.sqlite',access_approved=True,max_attempts=5)
    sessions=[Session(budget,boot()+[Step('GET','CHART',payload={'synthetic':True})]) for _ in range(2)]
    clients=[DataFixture(SOURCE,session) for session in sessions]
    def call(client):
        try:return client.request_json(URL)
        except WireFixtureRefused:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(call,clients))
    assert sum(result is not None for result in results)==1
    assert sum(len(session.events) for session in sessions)==5 and budget.remaining()==0


def test_provider_source_to_api_to_real_frontend_consumer_without_network(tmp_path):
    async def scenario():
        now=datetime(2026,10,20,12,1,10,tzinfo=UTC)
        steps=boot()+[Step('GET','CHART',payload=fixture(now-timedelta(seconds=70))),
                      Step('GET','QUOTE',payload=quote_fixture(now-timedelta(seconds=2)))]
        data,_,budget=make(tmp_path,steps)
        with sqlite3.connect(':memory:') as db:
            store=ReplayStore(db)
            store.ingest(data.request_json(URL),observed_at=now,asset_class='US_ETF')
            store.ingest_quote(data.request_json(QUOTE),observed_at=now,asset_class='US_ETF')
            app=create_replay_app(store,symbols=['SPY','MISSING'],clock=lambda:now)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as client:
                response=await client.get('/api/market-data');assert response.status_code==200
            root=Path(__file__).resolve().parents[1]
            expected=json.loads((root/'tests/fixtures/market-replay-v1/api.json').read_bytes())
            assert response.json()==expected and budget.remaining()==0
            wire=tmp_path/'actual-sdk-api.json';wire.write_bytes(response.content)
            return root,wire
    root,wire=asyncio.run(scenario())
    script="const fs=require('node:fs');const view=require(process.argv[1]);const r=view.parseExport(fs.readFileSync(process.argv[2],'utf8'));if(r.network_authorized!==false||r.rows.find(x=>x.symbol==='SPY').price!==101)throw Error('contract');process.stdout.write('PASS');"
    result=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,
        str(root/'frontend/offline/market-replay/view.cjs'),str(wire)],capture_output=True,text=True,timeout=10,check=False)
    assert result.returncode==0 and result.stdout=='PASS',result.stderr


@pytest.mark.parametrize('kwargs',[{'timeout':True},{'timeout':float('inf')},{'method':'DELETE'},{'cached':'yes'}])
def test_invalid_public_request_refuses_before_bootstrap_or_debit(tmp_path,kwargs):
    data,session,budget=make(tmp_path,boot()+[Step('GET','CHART',payload={})])
    with pytest.raises(WireFixtureRefused):data.request_json(URL,**kwargs)
    assert session.events==[] and budget.remaining()==3


@pytest.mark.parametrize('ack',[None,True,2])
def test_missing_malformed_or_uncommitted_ack_never_permits_fake_wire_attempt(tmp_path,monkeypatch,ack):
    data,session,budget=make(tmp_path,boot()+[Step('GET','CHART',payload={})])
    monkeypatch.setattr(budget,'consume_before_attempt',lambda:ack)
    with pytest.raises(WireFixtureRefused):data.request_json(URL)
    assert session.events==[] and budget.remaining()==3


def test_virtual_deadline_clamps_bootstrap_and_remaining_hops(tmp_path):
    steps=[Step('GET','COOKIE',cookie=True,elapsed=1),Step('GET','CRUMB_BASIC',text='SYNTHETIC',elapsed=1),Step('GET','CHART',payload={},elapsed=1)]
    data,session,_=make(tmp_path,steps,deadline=VirtualDeadline(5))
    assert data.request_json(URL,timeout=5)=={}
    assert [e['timeout'] for e in session.events]==[5,4,3]
    assert data.report()['virtual_deadline_elapsed']==3


def test_virtual_deadline_includes_sdk_backoff_and_forbids_retry_after_expiry(tmp_path):
    steps=boot()+[Step('GET','CHART',error='TIMEOUT',elapsed=1),Step('GET','CHART',payload={})]
    data,session,budget=make(tmp_path,steps,retries=1,deadline=VirtualDeadline(2))
    with pytest.raises(WireFixtureRefused):data.request_json(URL)
    assert data.backoffs==[1] and len(session.events)==3 and budget.remaining()==1
    with pytest.raises(WireFixtureRefused):data.request_json(URL)
    assert len(session.events)==3


def test_deadline_during_committed_debit_keeps_reservation_without_fake_send(tmp_path,monkeypatch):
    deadline=VirtualDeadline(1);data,session,budget=make(tmp_path,boot()+[Step('GET','CHART',payload={})],deadline=deadline)
    consume=budget.consume_before_attempt
    def delayed_debit():
        result=consume();deadline.advance(1);return result
    monkeypatch.setattr(budget,'consume_before_attempt',delayed_debit)
    with pytest.raises(WireFixtureRefused):data.request_json(URL)
    assert session.events==[] and budget.remaining()==2
    with pytest.raises(WireFixtureRefused):data.request_json(URL)
    assert budget.remaining()==2


def test_deadline_late_result_cannot_be_accepted_or_cached(tmp_path):
    data,session,budget=make(tmp_path,boot()+[Step('GET','CHART',payload={'late':True},elapsed=10)],deadline=VirtualDeadline(1))
    with pytest.raises(WireFixtureRefused):data.request_json(URL,cached=True)
    assert len(session.events)==3 and budget.remaining()==0
    with pytest.raises(WireFixtureRefused):data.request_json(URL,cached=True)


def test_redirect_elapsed_time_shares_one_virtual_deadline(tmp_path):
    steps=boot()+[Step('GET','CHART',status=302,location=URL,elapsed=1),Step('GET','CHART',payload={},elapsed=1)]
    data,session,budget=make(tmp_path,steps,deadline=VirtualDeadline(2))
    with pytest.raises(WireFixtureRefused):data.request_json(URL)
    assert [e['timeout'] for e in session.events]==[2,2,2,1] and budget.remaining()==0


@pytest.mark.parametrize('value',[True,0,-1,float('nan'),float('inf'),121])
def test_invalid_virtual_deadlines_are_refused(value):
    with pytest.raises(WireFixtureRefused):VirtualDeadline(value)
