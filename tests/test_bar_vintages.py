import asyncio
import copy
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier

import httpx
import pytest
from test_retained_research import chart, populate, reference

from scripts.observation_runtime import bar_vintages as vintage
from scripts.observation_runtime.market_replay import ReplayStore
from scripts.observation_runtime.research_replay import fingerprint, replay_research


def seeded(db):
    store=vintage.BarVintageStore(db);now,ref=populate(store)
    return store,now,ref


def corrected(store,now,price=120, *, seconds=20):
    stamp=now.replace(second=0)-timedelta(minutes=1)
    return store.ingest(chart([stamp],price=price),observed_at=now+timedelta(seconds=seconds),asset_class='US_ETF')


def test_provider_fixture_original_correction_confirmation_and_reversion_are_preserved():
    with sqlite3.connect(':memory:') as db:
        store,now,ref=seeded(db);original=store.archive('SPY',now=now)
        assert corrected(store,now)==1 and corrected(store,now)==0
        assert corrected(store,now,seconds=30)==1
        assert corrected(store,now,price=103,seconds=40)==1
        archive=store.archive('SPY',now=now+timedelta(minutes=1))
        assert archive['record_n']==original['record_n']+3
        before=vintage.project_history(archive,now=now)
        changed=vintage.project_history(archive,now=now+timedelta(seconds=20))
        confirmed=vintage.project_history(archive,now=now+timedelta(seconds=30))
        reverted=vintage.project_history(archive,now=now+timedelta(seconds=40))
        assert before['history']['rows'][-1]['close']==103
        assert changed['history']['rows'][-1]['close']==120
        assert changed['history']['rows']==confirmed['history']['rows']
        assert confirmed['confirmation_n']==1 and confirmed['correction_n']==1
        assert reverted['history']['rows'][-1]['close']==103 and reverted['correction_n']==2
        assert store.archive('SPY',now=now)==original
        report=vintage.replay_vintages(archive,[ref],[now,now+timedelta(seconds=20)])
        assert [c['report']['analysis']['bar_close'] for c in report['cases']]==[103,120]
        assert report['bar_revisions_supported'] is True and report['network_authorized'] is False


def test_future_correction_cannot_change_prior_decision_evidence_or_source_bytes():
    with sqlite3.connect(':memory:') as db:
        store,now,ref=seeded(db);old=store.archive('SPY',now=now)
        first=vintage.replay_vintages(old,[ref],[now])
        corrected(store,now);archive=store.archive('SPY',now=now+timedelta(minutes=1));saved=copy.deepcopy(archive)
        later=vintage.replay_vintages(archive,[ref],[now,now+timedelta(seconds=20)])
        assert first['cases'][0]==later['cases'][0] and first['archive_sha256']!=later['archive_sha256']
        assert archive==saved
        legacy=replay_research(vintage.project_history(old,now=now)['history'],[ref],[now])
        assert {k:v for k,v in first['cases'][0].items() if k in legacy['cases'][0]}==legacy['cases'][0]


def test_unknown_references_and_unobserved_bars_remain_in_plan():
    with sqlite3.connect(':memory:') as db:
        store,now,ref=seeded(db);archive=store.archive('SPY',now=now)
        report=vintage.replay_vintages(archive,[],[now])
        assert report['status_counts']['INSUFFICIENT_REFERENCE']==1
        empty=store.archive('QQQ',now=now)
        qref={**ref,'symbol':'QQQ'}
        report=vintage.replay_vintages(empty,[qref],[now])
        assert report['status_counts']['INSUFFICIENT_HISTORY']==1


@pytest.mark.parametrize('fault',['digest','tail','sequence','receipt','ohlc','asset','authority','head','extra','count_bool','duplicate','future','symbol'])
def test_invalid_archives_are_refused_before_research(fault):
    with sqlite3.connect(':memory:') as db:
        store,now,_=seeded(db);archive=store.archive('SPY',now=now)
    if fault=='digest':archive['records'][0]['digest']='0'*64
    if fault=='tail':archive['records'].pop();archive['record_n']-=1
    if fault=='sequence':archive['records'][0]['sequence']=True
    if fault=='receipt':archive['records'][-1]['row']['observed_at']=archive['records'][0]['row']['observed_at']
    if fault=='ohlc':archive['records'][-1]['row']['close']=-1
    if fault=='asset':archive['records'][-1]['row']['asset_class']='US_EQUITY'
    if fault=='authority':archive['network_authorized']=True
    if fault=='head':archive['head']='1'*64
    if fault=='extra':archive['records'][-1]['row']['secret']='not allowed'
    if fault=='count_bool':archive['record_n']=True
    if fault=='duplicate':archive['records'].append(copy.deepcopy(archive['records'][-1]));archive['record_n']+=1
    if fault=='future':archive['asof']=(now-timedelta(days=10)).isoformat()
    if fault=='symbol':archive['symbol']='spy'
    if fault in ('receipt','ohlc','asset','extra','duplicate'):
        previous=vintage.ZERO
        for i,record in enumerate(archive['records'],1):
            record['sequence']=i;record['previous']=previous
            record['digest']=fingerprint({k:v for k,v in record.items() if k!='digest'});previous=record['digest']
        archive['head']=previous
    with pytest.raises(ValueError):vintage.project_history(archive,now=now)


def test_exact_retry_backdating_and_identity_conflicts_do_not_mutate_committed_state():
    with sqlite3.connect(':memory:') as db:
        store,now,_=seeded(db);corrected(store,now);before=store.archive('SPY',now=now+timedelta(minutes=1))
        for price,seconds,asset in [(121,20,'US_ETF'),(120,10,'US_ETF'),(120,40,'US_EQUITY')]:
            stamp=now.replace(second=0)-timedelta(minutes=1)
            with pytest.raises(ValueError):store.ingest(chart([stamp],price=price),observed_at=now+timedelta(seconds=seconds),asset_class=asset)
        assert store.archive('SPY',now=now+timedelta(minutes=1))==before


@pytest.mark.parametrize('fault',['tail','head','key','body'])
def test_retained_store_corruption_prevents_reads_and_new_writes(fault):
    with sqlite3.connect(':memory:') as db:
        store,now,_=seeded(db)
        if fault=='tail':db.execute('DELETE FROM replay_bar_receipts WHERE sequence=(SELECT MAX(sequence) FROM replay_bar_receipts)')
        if fault=='head':db.execute('DELETE FROM replay_bar_receipt_heads')
        if fault=='key':db.execute("UPDATE replay_bar_receipts SET event_time='substitution' WHERE sequence=1")
        if fault=='body':db.execute("UPDATE replay_bar_receipts SET body='{}' WHERE sequence=1")
        db.commit()
        with pytest.raises((ValueError,KeyError)):store.archive('SPY',now=now)
        with pytest.raises((ValueError,KeyError)):corrected(store,now)


def test_normal_store_conflict_refusal_is_unchanged_and_tables_are_separate():
    with sqlite3.connect(':memory:') as db:
        legacy=ReplayStore(db);now,_=populate(legacy);before=legacy.history('SPY',now=now)
        store=vintage.BarVintageStore(db)
        assert corrected(store,now)==1
        with pytest.raises(ValueError):
            legacy.ingest(chart([now.replace(second=0)-timedelta(minutes=1)],price=120),observed_at=now+timedelta(seconds=20),asset_class='US_ETF')
        assert legacy.history('SPY',now=now)==before


def test_transaction_bounds_and_insert_failure_preserve_no_partial_receipts(monkeypatch):
    with sqlite3.connect(':memory:') as db:
        store,now,_=seeded(db);before=store.archive('SPY',now=now)
        db.execute("CREATE TRIGGER reject_receipt BEFORE INSERT ON replay_bar_receipts BEGIN SELECT RAISE(ABORT,'synthetic full disk'); END")
        with pytest.raises(sqlite3.IntegrityError):corrected(store,now)
        assert store.archive('SPY',now=now)==before
    with sqlite3.connect(':memory:') as db:
        store=vintage.BarVintageStore(db);monkeypatch.setattr(vintage,'MAX_RECORDS',1)
        with pytest.raises(ValueError):
            store.ingest(chart([now.replace(second=0)-timedelta(minutes=i) for i in (2,1)]),observed_at=now,asset_class='US_ETF')
        assert store.archive('SPY',now=now)['record_n']==0


def test_restart_persists_exact_receipts_and_concurrent_exact_retry_is_deduplicated(tmp_path):
    path=tmp_path/'synthetic.sqlite'
    with sqlite3.connect(path) as db:
        _,now,_=seeded(db)
    barrier=Barrier(2)
    def write():
        with sqlite3.connect(path,timeout=2) as db:
            store=vintage.BarVintageStore(db);barrier.wait(timeout=3)
            return corrected(store,now)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:write(),range(2)))
    assert sorted(results)==[0,1]
    with sqlite3.connect(path) as db:
        archive=vintage.BarVintageStore(db).archive('SPY',now=now+timedelta(minutes=1))
        assert archive['record_n']==19
        assert vintage.project_history(archive,now=now+timedelta(seconds=20))['correction_n']==1


def test_process_interruption_before_commit_preserves_previous_committed_head(tmp_path):
    path=tmp_path/'synthetic.sqlite'
    with sqlite3.connect(path) as db:
        store,now,_=seeded(db);before=store.archive('SPY',now=now+timedelta(minutes=1))
    script=tmp_path/'interrupted.py'
    script.write_text('import sqlite3,os,sys\nfrom scripts.observation_runtime.bar_vintages import BarVintageStore\n'
        'class Crash(sqlite3.Connection):\n def commit(self): os._exit(71)\n'
        'db=sqlite3.connect(sys.argv[1],factory=Crash)\nBarVintageStore(db)\n'
        'db.execute("BEGIN IMMEDIATE")\ndb.execute("DELETE FROM replay_bar_receipt_heads")\ndb.commit()\n')
    completed=subprocess.run([sys.executable,str(script),str(path)],capture_output=True,timeout=10,check=False)
    assert completed.returncode==71,completed.stderr.decode(errors='replace')
    with sqlite3.connect(path) as db:
        assert vintage.BarVintageStore(db).archive('SPY',now=now+timedelta(minutes=1))==before


def test_work_budget_refuses_before_per_decision_analysis(monkeypatch):
    with sqlite3.connect(':memory:') as db:
        store,now,ref=seeded(db);archive=store.archive('SPY',now=now)
    monkeypatch.setattr(vintage,'MAX_RECEIPT_DECISIONS',1)
    with pytest.raises(ValueError,match='work budget'):vintage.replay_vintages(archive,[ref],[now])


def test_projection_is_detached_and_future_cutoff_refuses():
    with sqlite3.connect(':memory:') as db:
        store,now,_=seeded(db);archive=store.archive('SPY',now=now)
    before=copy.deepcopy(archive);projection=vintage.project_history(archive,now=now)
    projection['history']['rows'][-1]['close']=999
    assert archive==before
    with pytest.raises(ValueError):vintage.project_history(archive,now=now+timedelta(seconds=1))


@pytest.mark.parametrize('after_commit',[False,True])
def test_commit_failure_never_acknowledges_success_and_retry_does_not_duplicate(after_commit):
    class Fault(sqlite3.Connection):
        fail=False
        def commit(self):
            if self.fail:
                self.fail=False
                if after_commit:super().commit()
                raise OSError('synthetic uncertain commit' if after_commit else 'synthetic commit failed')
            return super().commit()
    with sqlite3.connect(':memory:',factory=Fault) as db:
        store,now,_=seeded(db);db.fail=True
        with pytest.raises(OSError):corrected(store,now)
        assert corrected(store,now)==(0 if after_commit else 1)
        assert store.archive('SPY',now=now+timedelta(minutes=1))['record_n']==19


def test_unrelated_pending_transaction_is_not_committed_or_rolled_back():
    with sqlite3.connect(':memory:') as db:
        store,now,_=seeded(db);db.execute('CREATE TABLE unrelated (value INTEGER)')
        db.execute('INSERT INTO unrelated VALUES (1)')
        with pytest.raises(ValueError):corrected(store,now)
        with pytest.raises(ValueError):store.archive('SPY',now=now)
        assert db.in_transaction and db.execute('SELECT * FROM unrelated').fetchall()==[(1,)]
        db.rollback()


def test_actual_read_only_api_to_research_html_and_refusal_preserves_storage():
    async def scenario():
        with sqlite3.connect(':memory:') as db:
            store,now,ref=seeded(db);corrected(store,now)
            clock=now+timedelta(seconds=20);refs={'SPY':[ref]}
            app=vintage.create_vintage_app(store,symbols=['SPY','QQQ'],clock=lambda:clock,previous_closes=refs)
            refs['SPY'][0]['previous_close']=999
            before=db.execute('SELECT * FROM replay_bar_receipts').fetchall()
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as client:
                response=await client.get('/api/market-data/vintage-research?symbol=SPY')
                assert response.status_code==200 and response.headers['cache-control']=='no-store'
                report=response.json();assert report['cases'][0]['report']['analysis']['bar_close']==120
                fixture=Path(__file__).parent/'fixtures/market-replay-v1/bar-vintages-api.json'
                assert vintage.browser_vintages(report).encode()==fixture.read_bytes()
                assert report['cases'][0]['report']['analysis']['previous_close']==100
                assert report['startup_authorized'] is False and report['network_authorized'] is False
                html=await client.get('/vintage-research?symbol=SPY')
                assert html.status_code==200 and 'Receipt-vintage evidence' in html.text
                assert 'default-src' in html.headers['content-security-policy']
                source=await client.get('/api/market-data/receipt-history?symbol=SPY')
                assert source.json()['record_n']==19
                missing=await client.get('/api/market-data/vintage-research?symbol=QQQ')
                assert missing.json()['status_counts']['INSUFFICIENT_REFERENCE']==1
                assert (await client.get('/api/market-data/vintage-research?symbol=UNH')).status_code==404
                assert (await client.post('/api/market-data/vintage-research?symbol=SPY')).status_code==405
                assert before==db.execute('SELECT * FROM replay_bar_receipts').fetchall()
                db.execute('DELETE FROM replay_bar_receipts WHERE sequence=19');db.commit()
                refused=await client.get('/api/market-data/receipt-history?symbol=SPY')
                assert refused.status_code==503 and refused.json()['reason']=='DATA_UNAVAILABLE'
    asyncio.run(scenario())


@pytest.mark.parametrize('hour,session',[(12,'PRE_MARKET'),(14,'REGULAR'),(21,'AFTER_HOURS')])
def test_corrections_preserve_exchange_session_paths(hour,session):
    stamp=datetime(2026,10,20,hour,tzinfo=UTC);first=stamp+timedelta(seconds=70);second=first+timedelta(seconds=20)
    with sqlite3.connect(':memory:') as db:
        store=vintage.BarVintageStore(db)
        store.ingest(chart([stamp],price=100),observed_at=first,asset_class='US_ETF')
        store.ingest(chart([stamp],price=105),observed_at=second,asset_class='US_ETF')
        report=vintage.replay_vintages(store.archive('SPY',now=second),[reference(first)],[first,second])
        assert [case['report']['analysis']['bar_close'] for case in report['cases']]==[100,105]
        assert all(case['report']['analysis']['session']==session for case in report['cases'])


def test_historical_volume_correction_changes_only_subsequent_rvol_baseline():
    with sqlite3.connect(':memory:') as db:
        store,now,ref=seeded(db);old=store.archive('SPY',now=now)
        payload=chart([datetime(2026,10,19,13,30,tzinfo=UTC)])
        payload['chart']['result'][0]['indicators']['quote'][0]['volume']=[500]
        receipt=now+timedelta(seconds=20)
        store.ingest(payload,observed_at=receipt,asset_class='US_ETF')
        result=vintage.replay_vintages(store.archive('SPY',now=receipt),[ref],[now,receipt])
        assert result['cases'][0]['report']['analysis']['relative_volume']==2
        assert result['cases'][1]['report']['analysis']['relative_volume']!=2
        assert result['cases'][0]==vintage.replay_vintages(old,[ref],[now])['cases'][0]


def test_new_reference_vintage_is_not_used_before_its_availability():
    with sqlite3.connect(':memory:') as db:
        store,now,ref=seeded(db);archive=store.archive('SPY',now=now+timedelta(minutes=1))
    clocks=[now,now+timedelta(seconds=30)]
    future={**ref,'available_at':(now+timedelta(seconds=20)).isoformat(),'previous_close':102}
    old=vintage.replay_vintages(archive,[ref],clocks)
    revised=vintage.replay_vintages(archive,[ref,future],clocks)
    assert old['cases'][0]==revised['cases'][0]
    assert revised['cases'][1]['report']['analysis']['previous_close']==102
