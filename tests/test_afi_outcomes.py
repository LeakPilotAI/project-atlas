import hashlib
import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from app.backtest.forecast_artifacts import publish_forecast
from app.backtest.forecast_dataset import review_dataset
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_outcomes import append_outcome, verify_outcome_history
from app.backtest.forecast_source import create_source_review
from test_afi_baselines import ASOF, history
from test_afi_dataset_integrity import encode
from test_afi_source_binding import model, source

PENDING=datetime(2026,10,17,12,tzinfo=UTC)
RESOLVED=datetime(2026,10,18,12,tzinfo=UTC)
CORRECTED=datetime(2026,10,19,13,tzinfo=UTC)


def setup(tmp_path,bound=False):
    r=history();s=source() if bound else None
    forecasts=tmp_path/'forecasts';forecasts.mkdir();out=tmp_path/'outcomes';out.mkdir()
    f=publish_forecast(forecasts,r,model(r,s),evidence_asof=ASOF,source_review=s)
    return r,s,f,out


def changed_review(r,*,version='v2',remove=False,wrong_source=False):
    m=json.loads(r.manifest_bytes);p=json.loads(r.payload_bytes)
    target='2026-10-18T00:00:00+00:00';row=next(x for x in p['records'] if x['observed_at']==target)
    if remove:
        p['records']=[x for x in p['records'] if x['observed_at']!=target];m['quality']['max_missing_fraction']=.1
    else:p['records'].append({**row,'record_id':'corrected','revision':'v2','raw_price':155,'value':155,'available_at':'2026-10-19T12:00:00+00:00'})
    if wrong_source:
        m['source']['id']='another-source'
        for x in p['records']:x['source_id']='another-source'
    raw=encode(p);m.update(version=version,content_sha256=hashlib.sha256(raw).hexdigest(),record_count=len(p['records']),
                         acquired_at='2026-10-19T12:00:00+00:00',generated_at='2026-10-19T12:00:00+00:00')
    return review_dataset(encode(m),raw,asof=ASOF)


def append(out,f,r,outcome_review=None,**kwargs):
    return append_outcome(out,f,r,outcome_review or r,evidence_asof=ASOF,**kwargs)


def test_pending_resolution_and_correction_append_preserve_original_evidence(tmp_path):
    r,_s,f,out=setup(tmp_path)
    p,a=append(out,f,r,outcome_asof=PENDING);before=p.read_bytes()
    assert a['status']=='PENDING_TARGET' and a['evaluation']['pending_n']==1 and a['observation'] is None
    q,b=append(out,f,r,outcome_asof=RESOLVED,history=[(p,r)],expected_head=a['artifact_sha256'])
    assert b['event']=='RESOLUTION' and b['evaluation']['scored_n']==1
    newer=changed_review(r)
    v,c=append(out,f,r,newer,outcome_asof=CORRECTED,history=[(p,r),(q,r)],expected_head=b['artifact_sha256'])
    assert c['event']=='CORRECTION' and c['observation']['value']==155
    assert p.read_bytes()==before and c['previous_outcome_sha256']==b['artifact_sha256']
    result=verify_outcome_history(f,r,evidence_asof=ASOF,history=[(p,r),(q,r),(v,newer)],expected_head=c['artifact_sha256'])
    assert len(result['records'])==3 and not result['history_completeness_verified']
    assert not c['trading_authority'] and not c['recovery_authorized']


def test_idempotent_same_time_retry_never_appends_or_rewrites(tmp_path):
    r,_s,f,out=setup(tmp_path);p,a=append(out,f,r,outcome_asof=RESOLVED);raw=p.read_bytes()
    q,b=append(out,f,r,outcome_asof=RESOLVED,history=[(p,r)],expected_head=a['artifact_sha256'])
    assert q==p and b==a and p.read_bytes()==raw and len(list(out.iterdir()))==1


@pytest.mark.parametrize('case',['missing-head','wrong-head','backdated','version-reuse','source-change','disappeared','corrupt'])
def test_conflicting_or_missing_history_and_source_refuse(tmp_path,case):
    r,_s,f,out=setup(tmp_path);p,a=append(out,f,r,outcome_asof=RESOLVED)
    kwargs={'outcome_asof':CORRECTED,'history':[(p,r)],'expected_head':a['artifact_sha256']};newer=r
    if case=='missing-head':kwargs['expected_head']=None
    if case=='wrong-head':kwargs['expected_head']='a'*64
    if case=='backdated':kwargs['outcome_asof']=PENDING
    if case=='version-reuse':newer=changed_review(r,version='v1')
    if case=='source-change':newer=changed_review(r,wrong_source=True)
    if case=='disappeared':newer=changed_review(r,remove=True)
    if case=='corrupt':p.write_bytes(p.read_bytes().replace(b'"production_approved":false',b'"production_approved":true'))
    with pytest.raises(ForecastEvidenceRefused):append(out,f,r,newer,**kwargs)


def test_missing_expected_tail_cannot_be_silently_accepted(tmp_path):
    r,_s,f,out=setup(tmp_path);p,a=append(out,f,r,outcome_asof=PENDING)
    q,b=append(out,f,r,outcome_asof=RESOLVED,history=[(p,r)],expected_head=a['artifact_sha256'])
    with pytest.raises(ForecastEvidenceRefused):verify_outcome_history(f,r,evidence_asof=ASOF,history=[(p,r)],expected_head=b['artifact_sha256'])
    q.unlink()
    with pytest.raises(FileNotFoundError):verify_outcome_history(f,r,evidence_asof=ASOF,history=[(p,r),(q,r)],expected_head=b['artifact_sha256'])


def test_partial_outcome_publication_failure_is_preserved_and_not_acknowledged(tmp_path):
    r,_s,f,out=setup(tmp_path)
    def broken(handle,text):handle.write(text[:12]);handle.flush();raise OSError('disk full')
    with patch('app.backtest.forecast_artifacts.write_flushed',broken),pytest.raises(OSError):append(out,f,r,outcome_asof=RESOLVED)
    files=list(out.iterdir());assert len(files)==1;raw=files[0].read_bytes()
    with pytest.raises(ForecastEvidenceRefused):append(out,f,r,outcome_asof=RESOLVED)
    assert files[0].read_bytes()==raw


def test_outcome_source_binding_includes_outcome_implementation_and_forecast_source(tmp_path):
    r,s,f,out=setup(tmp_path,bound=True)
    files=dict(s.source_files);files['app/backtest/forecast_outcomes.py']=b'# outcome fixture implementation\n'
    outcome_source=create_source_review(files,release_id='outcome-v1')
    with pytest.raises(ForecastEvidenceRefused):append(out,f,r,outcome_asof=RESOLVED,source_review=s,outcome_source=s)
    p,a=append(out,f,r,outcome_asof=RESOLVED,source_review=s,outcome_source=outcome_source)
    assert a['outcome_source_sha256']==outcome_source.release_sha256
    verified=verify_outcome_history(f,r,evidence_asof=ASOF,history=[(p,r,outcome_source)],expected_head=a['artifact_sha256'],source_review=s)
    assert len(verified['records'])==1
    with pytest.raises(ForecastEvidenceRefused):verify_outcome_history(f,r,evidence_asof=ASOF,history=[(p,r)],expected_head=a['artifact_sha256'],source_review=s)

def test_as_published_records_cannot_be_rewritten_under_a_new_archive_version(tmp_path):
    r,_s,f,out=setup(tmp_path);m=json.loads(r.manifest_bytes);p=json.loads(r.payload_bytes)
    p['records'][38].update(value=999,raw_price=999)
    raw=encode(p);m.update(version='v2',content_sha256=hashlib.sha256(raw).hexdigest())
    rewritten=review_dataset(encode(m),raw,asof=ASOF)
    with pytest.raises(ForecastEvidenceRefused,match='rewritten'):
        append(out,f,r,rewritten,outcome_asof=RESOLVED)


@pytest.mark.parametrize('kind',['late','missing'])
def test_new_outcome_dataset_distinguishes_unpublished_and_missing_labels(tmp_path,kind):
    r=history();m=json.loads(r.manifest_bytes);p=json.loads(r.payload_bytes)
    p['records']=p['records'][:38]
    raw=encode(p);m.update(version='v0',content_sha256=hashlib.sha256(raw).hexdigest(),record_count=38,
                         period_end=p['records'][-1]['observed_at'],acquired_at=p['records'][-1]['available_at'],generated_at=p['records'][-1]['available_at'])
    original=review_dataset(encode(m),raw,asof=ASOF)
    forecasts=tmp_path/'forecasts';forecasts.mkdir();out=tmp_path/'outcomes';out.mkdir()
    f=publish_forecast(forecasts,original,model(original),evidence_asof=ASOF)
    m=json.loads(r.manifest_bytes);p=json.loads(r.payload_bytes)
    if kind=='late':p['records'][38]['available_at']='2026-10-19T00:00:00+00:00'
    else:p['records'].pop(38);m['quality']['max_missing_fraction']=.1
    raw=encode(p);m.update(content_sha256=hashlib.sha256(raw).hexdigest(),record_count=len(p['records']))
    newer=review_dataset(encode(m),raw,asof=ASOF)
    _,record=append(out,f,original,newer,outcome_asof=RESOLVED)
    assert record['status']==('PENDING_PUBLICATION' if kind=='late' else 'MISSING_OUTCOME')
    assert record['evaluation']['pending_n']==1 and record['evaluation']['scored_n']==0
