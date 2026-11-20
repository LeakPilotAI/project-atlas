import hashlib
import json
import uuid
from pathlib import Path

import pytest
from test_r7e47s_observation_bootstrap import make_fixture
from test_session_quality_timeline import inputs

from scripts.observation_runtime import quality_report


def setup(tmp_path):
    history,now=inputs()
    raw=json.dumps(history,sort_keys=True).encode()
    (tmp_path/'history.json').write_bytes(raw)
    output=tmp_path/'output';output.mkdir()
    request={'schema':'ATLAS_SESSION_QUALITY_REQUEST_V1','now':now.isoformat(),'history':'history.json',
             'expected_history_sha256':hashlib.sha256(raw).hexdigest(),'lifecycle':None,'lifecycle_expected_head':None}
    (tmp_path/'request.json').write_text(json.dumps(request))
    return request,output


def run(root,output):
    return quality_report.export_quality(bundle_root=root,request_name='request.json',output_root=output)


def test_actual_history_export_is_immutable_and_cli_reusable(tmp_path,capsys):
    _,output=setup(tmp_path)
    result=run(tmp_path,output)
    report=json.loads((output/result['report']).read_bytes())
    assert report['observed_bar_n']==2 and report['windows'][0]['missing_minutes_between_observed_bars']==1
    before={p:p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert quality_report.main(['--bundle-root',str(tmp_path),'--request','request.json','--output-root',str(output)])==0
    assert json.loads(capsys.readouterr().out)['report']==result['report']
    assert all(p.read_bytes()==raw for p,raw in before.items())
    provenance=json.loads((output/result['provenance']).read_bytes())
    assert provenance['report_sha256']==hashlib.sha256((output/result['report']).read_bytes()).hexdigest()
    assert provenance['source_authenticated'] is False


@pytest.mark.parametrize('fault',['pin','escape','authority','head_without_records'])
def test_invalid_request_refuses_before_publication(tmp_path,fault):
    request,output=setup(tmp_path)
    if fault=='pin':request['expected_history_sha256']='a'*64
    elif fault=='escape':request['history']='../history.json'
    elif fault=='authority':request['startup_authorized']=True
    else:request['lifecycle_expected_head']='a'*64
    (tmp_path/'request.json').write_text(json.dumps(request))
    with pytest.raises(ValueError):run(tmp_path,output)
    assert list(output.iterdir())==[]


@pytest.mark.parametrize('stage',[2,3])
def test_publication_failure_preserves_partial_evidence_never_complete(tmp_path,monkeypatch,stage):
    _,output=setup(tmp_path);real=quality_report.publish_research_text;calls=0
    def fail(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==stage:raise OSError('synthetic publication failure')
        return real(*args,**kwargs)
    monkeypatch.setattr(quality_report,'publish_research_text',fail)
    with pytest.raises(OSError):run(tmp_path,output)
    assert len(list(output.iterdir()))==stage-1


def test_actual_interrupted_lifecycle_export_never_clears_state(tmp_path):
    request,output=setup(tmp_path)
    _m,_p,_c,journal,world,bootstrap=make_fixture(tmp_path/'fixture')
    bootstrap.start()
    journal.append('INTERRUPTED',{'reason':'UNKNOWN_EXIT'},str(uuid.uuid4()),observed_at=world.now)
    before=journal.path.read_bytes()
    (tmp_path/'session.jsonl').write_bytes(before)
    request.update(lifecycle='session.jsonl',lifecycle_expected_head=journal.verify()[-1]['digest'])
    (tmp_path/'request.json').write_text(json.dumps(request))
    result=run(tmp_path,output)
    report=json.loads((output/result['report']).read_bytes())
    assert report['lifecycle']['status']=='RECOVERY_REQUIRED'
    assert report['recovery_authorized'] is False
    assert journal.path.read_bytes()==before


def test_readback_failure_never_claims_export_complete(tmp_path,monkeypatch):
    _,output=setup(tmp_path);real=Path.read_text
    def wrong(path,*args,**kwargs):
        return 'synthetic mismatched HTML' if path.parent==output and path.suffix=='.html' else real(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',wrong)
    with pytest.raises(ValueError,match='readback'):run(tmp_path,output)
    assert len(list(output.iterdir()))==3


def test_cli_refusal_is_sanitized_and_denies_authority(tmp_path,capsys):
    request,output=setup(tmp_path)
    request['expected_history_sha256']='a'*64
    (tmp_path/'request.json').write_text(json.dumps(request))
    assert quality_report.main(['--bundle-root',str(tmp_path),'--request','request.json','--output-root',str(output)])==2
    result=json.loads(capsys.readouterr().out)
    assert result['status']=='REFUSED' and result['startup_authorized'] is False
    assert str(tmp_path) not in json.dumps(result)
    assert list(output.iterdir())==[]
