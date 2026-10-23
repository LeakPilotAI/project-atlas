import hashlib
import json
import shutil
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from test_research_replay import inputs
from test_retained_research import chart, reference

from scripts.observation_runtime import research_replay_export as export
from scripts.observation_runtime.market_replay import ReplayStore
from scripts.observation_runtime.research_replay import encoded


def setup(tmp_path,large=False):
    archive,refs,decisions=inputs()
    if large:
        now=datetime(2026,10,20,8,41,10,tzinfo=UTC)
        stamps=[datetime(2026,10,19,8,tzinfo=UTC)+timedelta(minutes=i) for i in range(960)]
        stamps += [datetime(2026,10,20,8,tzinfo=UTC)+timedelta(minutes=i) for i in range(41)]
        with sqlite3.connect(':memory:') as db:
            store=ReplayStore(db);store.ingest(chart(stamps),observed_at=now,asset_class='US_ETF')
            archive=store.history('SPY',now=now)
            archive.update(rows=[json.loads(row[0]) for row in db.execute('SELECT body FROM replay_bars ORDER BY event_time')],more_retained_rows=False)
        refs=[reference(now)];decisions=[now]
    request={'schema':'ATLAS_DESCRIPTIVE_REPLAY_REQUEST_V1','decisions':[clock.isoformat() for clock in decisions]}
    for key,value in [('archive',archive),('references',refs)]:
        raw=encoded(value);(tmp_path/(key+'.json')).write_bytes(raw)
        request[key]=key+'.json';request['expected_'+key+'_sha256']=hashlib.sha256(raw).hexdigest()
    (tmp_path/'request.json').write_bytes(encoded(request));output=tmp_path/'output';output.mkdir()
    return request,output


def run(root,output):return export.export_replay(bundle_root=root,request_name='request.json',output_root=output)


def verify(root,result):
    return export.verify_replay(bundle_root=root,manifest_name=result['manifest'],expected_manifest_sha256=result['manifest'][:-5])


def test_self_contained_export_reproduces_every_case_and_cli_is_read_only(tmp_path,capsys):
    _,output=setup(tmp_path);result=run(tmp_path,output)
    assert result['status_counts']['REFUSED']==2 and result['planned_decision_n']==3
    before={p:p.read_bytes() for p in output.iterdir()}
    assert verify(output,result)['status']=='OFFLINE_REPLAY_VERIFIED'
    assert export.main(['--bundle-root',str(output),'--verify',result['manifest'],'--expected-manifest-sha256',result['manifest'][:-5]])==0
    assert json.loads(capsys.readouterr().out)['trading_authorized'] is False
    assert before=={p:p.read_bytes() for p in output.iterdir()}
    assert run(tmp_path,output)==result
    fixture=Path(__file__).parent/'fixtures/market-replay-v1/research-replay.json'
    assert (output/result['browser_export']).read_bytes()==fixture.read_bytes()


def test_larger_retained_archive_is_chunked_without_silent_truncation(tmp_path):
    _,output=setup(tmp_path,large=True);result=run(tmp_path,output)
    manifest=json.loads((output/result['manifest']).read_bytes())
    assert [spec['record_n'] for spec in manifest['archive_chunks']]==[1000,1]
    assert result['status_counts']['DESCRIPTIVE_RESEARCH_ONLY']==1
    assert verify(output,result)['planned_decision_n']==1


@pytest.mark.parametrize('fault',['missing_chunk','report','case','dashboard','wrong_pin','case_omission','mapping_bool'])
def test_corrupt_or_rebased_outputs_never_verify(tmp_path,fault):
    _,output=setup(tmp_path);result=run(tmp_path,output)
    manifest=json.loads((output/result['manifest']).read_bytes());altered=tmp_path/'altered';altered.mkdir()
    missing=manifest['archive_chunks'][0]['artifact'] if fault=='missing_chunk' else None
    for path in output.iterdir():
        if path.name!=missing:shutil.copyfile(path,altered/path.name)
    expected=result['manifest'][:-5];name=result['manifest']
    if fault=='wrong_pin':expected='a'*64
    elif fault in {'report','case','dashboard','case_omission','mapping_bool'}:
        if fault=='report':
            report=json.loads((output/manifest['report']).read_bytes());report['planned_decision_n']=True
            path=export.publish_research_text(altered,encoded(report).decode(),extension='.json');manifest['report']=path.name
        elif fault=='case':
            case=json.loads((output/manifest['case_artifacts'][0]['artifact']).read_bytes())
            case['case']['report']['trading_authorized']=0
            path=export.publish_research_text(altered,encoded(case).decode(),extension='.json');manifest['case_artifacts'][0]['artifact']=path.name
        elif fault=='dashboard':
            path=export.publish_research_text(altered,'<h1>Unproven success</h1>',extension='.html');manifest['dashboard']=path.name
        elif fault=='case_omission':manifest['case_artifacts']=manifest['case_artifacts'][:-1]
        else:manifest['case_artifacts'][0]['index']=False
        path=export.publish_research_text(altered,encoded(manifest).decode(),extension='.json');name=path.name;expected=name[:-5]
    with pytest.raises((ValueError,OSError)):
        export.verify_replay(bundle_root=altered,manifest_name=name,expected_manifest_sha256=expected)
    assert verify(output,result)['planned_decision_n']==3


@pytest.mark.parametrize('fault',['pin','escape','clock_order'])
def test_request_refuses_before_any_publication(tmp_path,fault):
    request,output=setup(tmp_path)
    if fault=='pin':request['expected_archive_sha256']='a'*64
    elif fault=='escape':request['archive']='../archive.json'
    else:request['decisions'].reverse()
    (tmp_path/'request.json').write_bytes(encoded(request))
    with pytest.raises(ValueError):run(tmp_path,output)
    assert list(output.iterdir())==[]


def test_partial_publication_is_retained_without_success(tmp_path,monkeypatch):
    _,output=setup(tmp_path);real=export.publish_research_text;calls=0
    def fail(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==3:raise OSError('synthetic replay publication failure')
        return real(*args,**kwargs)
    monkeypatch.setattr(export,'publish_research_text',fail)
    with pytest.raises(OSError):run(tmp_path,output)
    assert len(list(output.iterdir()))==2


def test_failed_final_reproduction_is_not_reported_complete(tmp_path,monkeypatch):
    _,output=setup(tmp_path)
    def fail(**kwargs):raise ValueError('synthetic reproduction failure')
    monkeypatch.setattr(export,'verify_replay',fail)
    with pytest.raises(ValueError):run(tmp_path,output)
    assert len(list(output.iterdir()))>3


def test_actual_pre_browser_v1_export_remains_verifiable():
    root=Path(__file__).parent/'fixtures/descriptive-replay-v1-valid'
    provenance=json.loads((root/'provenance.json').read_bytes())
    checked=export.verify_replay(bundle_root=root,manifest_name=provenance['manifest'],
                                 expected_manifest_sha256=provenance['expected_manifest_sha256'])
    assert checked['status']=='OFFLINE_REPLAY_VERIFIED' and checked['trading_authorized'] is False


def test_preserved_incomplete_v1_fixture_is_still_refused():
    root=Path(__file__).parent/'fixtures/descriptive-replay-v1'
    provenance=json.loads((root/'provenance.json').read_bytes())
    with pytest.raises(ValueError):
        export.verify_replay(bundle_root=root,manifest_name=provenance['manifest'],
                             expected_manifest_sha256=provenance['expected_manifest_sha256'])
