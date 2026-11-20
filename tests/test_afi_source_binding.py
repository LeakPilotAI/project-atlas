import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from app.backtest.forecast_artifacts import (
    artifact_envelope,
    publish_forecast,
    read_forecast,
)
from app.backtest.forecast_baselines import (
    fit_baseline,
    model_fingerprint,
    predict_baseline,
)
from app.backtest.forecast_cli import run
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_replay import freeze_selection
from app.backtest.forecast_source import (
    REQUIRED_FILES,
    create_source_review,
    review_source,
    validate_source,
)
from app.backtest.forecast_uncertainty import fit_interval, predict_interval
from test_afi_baselines import ASOF, ASSET, history
from test_afi_cli import inputs
from test_afi_replay import issue
from test_afi_uncertainty import CALIBRATION, FREEZE


def source():return create_source_review({p:b'# explicit synthetic source fixture\n' for p in REQUIRED_FILES},release_id='fixture-v1')


def model(r,s=None):
    return fit_baseline(r,asset_id=ASSET,issued_at=datetime(2026,10,17,0,1,tzinfo=UTC),evidence_asof=ASOF,lookback=5,source_review=s)


def test_source_graph_is_deterministic_and_not_an_authentication_claim():
    s=source();assert s==source() and validate_source(s)==s.release_sha256
    assert not s.externally_authenticated and not s.running_memory_attested and not s.production_approved
    assert create_source_review(dict(reversed(s.source_files)),release_id='fixture-v1')==s


def test_altered_source_bytes_refuse_original_manifest_and_changed_release_changes_identity():
    s=source();files=dict(s.source_files);files['app/backtest/forecast_baselines.py']+=b'# changed\n'
    with pytest.raises(ForecastEvidenceRefused):review_source(s.manifest_bytes,files)
    changed=create_source_review(files,release_id='fixture-v1');r=history();a,b=model(r,s),model(r,changed)
    assert a.reference_price==b.reference_price and model_fingerprint(a)!=model_fingerprint(b)
    with pytest.raises(ForecastEvidenceRefused):predict_baseline(a,r,evidence_asof=ASOF,source_review=changed)
    with pytest.raises(ForecastEvidenceRefused):predict_baseline(a,r,evidence_asof=ASOF)


@pytest.mark.parametrize('bad',['missing','extra','traversal','flags','manifest','count'])
def test_missing_or_forged_source_evidence_refuses(bad):
    s=source();files=dict(s.source_files)
    if bad=='flags':
        with pytest.raises(ForecastEvidenceRefused):validate_source(replace(s,production_approved=True))
        return
    if bad=='manifest':
        with pytest.raises(ForecastEvidenceRefused):validate_source(replace(s,release_sha256='a'*64))
        return
    if bad=='missing':files.pop(next(iter(files)))
    if bad=='extra':files['app/core/config.py']=b'no'
    if bad=='traversal':files['../other.py']=b'no'
    if bad=='count':
        manifest=json.loads(s.manifest_bytes);manifest['files'][0]['bytes']=True
        raw=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()
        with pytest.raises(ForecastEvidenceRefused):review_source(raw,files)
        return
    with pytest.raises(ForecastEvidenceRefused):create_source_review(files,release_id='fixture-v1')


def test_bound_artifact_requires_same_source_and_legacy_remains_explicit(tmp_path):
    r=history();s=source();m=model(r,s);path=publish_forecast(tmp_path,r,m,evidence_asof=ASOF,source_review=s)
    data=read_forecast(path,r,evidence_asof=ASOF,source_review=s)
    assert data['schema'].endswith('V2') and data['release_source_sha256']==s.release_sha256
    with pytest.raises(ForecastEvidenceRefused):read_forecast(path,r,evidence_asof=ASOF)
    legacy=artifact_envelope(r,model(r),evidence_asof=ASOF)
    assert legacy['schema'].endswith('V1') and 'release_source_sha256' not in legacy
    assert 'release_source_sha256' not in legacy['model']


def test_release_binding_propagates_selection_calibration_and_forecast():
    r=history();s=source()
    frozen=freeze_selection(r,asset_id=ASSET,selection_issues=[issue(20),issue(21)],frozen_at=issue(24),
                            evidence_asof=ASOF,lookback=5,source_review=s)
    interval=fit_interval(r,frozen,calibration_issues=CALIBRATION,calibrated_at=FREEZE,evidence_asof=ASOF,source_review=s)
    f=predict_interval(r,interval,issued_at=datetime(2026,10,17,0,1,tzinfo=UTC),evidence_asof=ASOF,source_review=s)
    assert frozen['release_source_sha256']==s.release_sha256 and f.code_sha256!=model_fingerprint(model(r))
    with pytest.raises(ForecastEvidenceRefused):predict_interval(r,interval,issued_at=f.issued_at,evidence_asof=ASOF)


def test_cli_reads_explicit_source_archive_and_rejects_changed_file(tmp_path):
    manifest,records,out=inputs(tmp_path);s=source();root=tmp_path/'source';root.mkdir()
    for p,raw in s.source_files:
        f=root/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(raw)
    source_manifest=tmp_path/'source-manifest.json';source_manifest.write_bytes(s.manifest_bytes)
    kwargs={'manifest':manifest,'records':records,'output_root':out,'asset_id':ASSET,'issued_at':datetime(2026,10,1,0,1,tzinfo=UTC),
            'evidence_asof':ASOF,'lookback':5,'source_manifest':source_manifest,'source_root':root}
    result=run(**kwargs);assert result['source_binding']=='SUPPLIED_ARCHIVE_BYTES_VERIFIED'
    (root/'app/backtest/forecast_baselines.py').write_bytes(b'# changed')
    with pytest.raises(ForecastEvidenceRefused):run(**kwargs)

def test_source_archive_roundtrip_and_altered_content_refusal():
    from app.backtest.forecast_source import review_source_archive, source_archive_bytes
    s=source();raw=source_archive_bytes(s)
    assert review_source_archive(raw)==s
    payload=json.loads(raw);payload['files'][0]['source_utf8']+='changed'
    with pytest.raises(ForecastEvidenceRefused):review_source_archive(json.dumps(payload,sort_keys=True,separators=(',',':')).encode())


def test_package_capture_is_explicit_immutable_and_cli_usable(tmp_path):
    from app.backtest.forecast_source import package_source, review_source_archive
    manifest,records,out=inputs(tmp_path);s=source();root=tmp_path/'source';root.mkdir();packages=tmp_path/'packages';packages.mkdir()
    for name,raw in s.source_files:
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    result=package_source(root,packages,release_id='fixture-v1')
    archive=packages/result['archive'];before=archive.read_bytes()
    assert review_source_archive(before)==s
    assert package_source(root,packages,release_id='fixture-v1')==result and archive.read_bytes()==before
    output=run(manifest=manifest,records=records,output_root=out,asset_id=ASSET,issued_at=datetime(2026,10,1,0,1,tzinfo=UTC),
               evidence_asof=ASOF,lookback=5,source_archive=archive)
    assert output['release_source_sha256']==s.release_sha256
    with pytest.raises(ForecastEvidenceRefused):package_source(root,packages,release_id='fixture-v1',include=['../secret'])


def test_source_archive_refuses_missing_and_duplicate_entries():
    from app.backtest.forecast_source import review_source_archive, source_archive_bytes
    raw=source_archive_bytes(source())
    for mode in ('missing','duplicate'):
        data=json.loads(raw)
        if mode=='missing':data['files'].pop()
        else:data['files'].append(data['files'][0])
        with pytest.raises(ForecastEvidenceRefused):review_source_archive(json.dumps(data,sort_keys=True,separators=(',',':')).encode())
