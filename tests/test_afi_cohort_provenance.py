from copy import deepcopy

import pytest
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_report import directional_diagnostics, interval_diagnostics
from test_afi_interval_accountability import interval_row


def bound(**updates):
    row=interval_row();row.update(forecast_dataset_sha256='a'*64,release_source_sha256='b'*64);row.update(updates);return row


@pytest.mark.parametrize('fn',[directional_diagnostics,interval_diagnostics])
@pytest.mark.parametrize('change',[{'forecast_dataset_sha256':'c'*64},{'release_source_sha256':'d'*64},{'release_source_sha256':None}])
def test_distinct_dataset_or_release_commitments_are_not_pooled(fn,change):
    a=bound();b=deepcopy(a);b.update(change);d=fn([a,b])
    assert len(d['cohorts'])==2
    assert sum(c['resolved_n'] for c in d['cohorts'])==2


@pytest.mark.parametrize('change',[{'forecast_dataset_sha256':True},{'forecast_dataset_sha256':'bad'},{'release_source_sha256':False},{'release_source_sha256':'z'*64}])
def test_malformed_binding_never_becomes_legacy_unbound(change):
    with pytest.raises(ForecastEvidenceRefused):interval_diagnostics([bound(**change)])


def test_partial_source_identity_without_dataset_refuses():
    row=interval_row();row['release_source_sha256']='a'*64
    with pytest.raises(ForecastEvidenceRefused):interval_diagnostics([row])


def test_explicit_legacy_diagnostics_remain_reconstructible_without_source_partition():
    a=bound();b=bound(forecast_dataset_sha256='c'*64)
    assert len(interval_diagnostics([a,b],bind_provenance=False)['cohorts'])==1
    assert len(directional_diagnostics([a,b],bind_provenance=False)['cohorts'])==1



def test_frozen_original_interval_report_stays_readable_without_rewriting():
    import hashlib
    import json
    from pathlib import Path

    from app.backtest.forecast_report import (
        browser_export,
        render_accountability_report,
    )
    path=Path(__file__).parent/'fixtures/afi-legacy-v1/accountability-interval-unpartitioned.json';raw=path.read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='0fa3fdab1837b3dea8ea8efaab44c22007f658d9aa2635e2886ce54db1f80672'
    report=json.loads(raw);assert 'diagnostic_partition' not in report
    html=render_accountability_report(report)
    assert report['rows'][0]['forecast_dataset_sha256'] in html
    assert 'Forecast dataset commitment' in html
    assert json.loads(json.loads(browser_export(report))['report_json'])==report and path.read_bytes()==raw


@pytest.mark.parametrize('value',[None,'UNKNOWN_PARTITION'])
def test_unknown_partition_contract_refuses_before_export(value):
    import json
    from pathlib import Path

    from app.backtest.forecast_baselines import fingerprint
    from app.backtest.forecast_report import browser_export
    report=json.loads((Path(__file__).parent/'fixtures/afi-legacy-v1/accountability-interval-unpartitioned.json').read_bytes())
    report['diagnostic_partition']=value;report['report_sha256']=fingerprint({k:v for k,v in report.items() if k!='report_sha256'})
    with pytest.raises(ForecastEvidenceRefused):browser_export(report)



def test_actual_source_bound_forecast_retains_diagnostic_provenance(tmp_path):
    from app.backtest.forecast_report import (
        ForecastHistory,
        build_accountability_report,
    )
    from test_afi_baselines import ASOF
    from test_afi_outcomes import setup
    r,source,f,_=setup(tmp_path,bound=True)
    report=build_accountability_report([ForecastHistory(f,r,source_review=source)],evidence_asof=ASOF)
    assert report['diagnostic_partition']=='DATASET_RELEASE_V1'
    cohort=report['directional_diagnostics']['cohorts'][0]['cohort'];row=report['rows'][0]
    assert cohort['forecast_dataset_sha256']==row['forecast_dataset_sha256']==r.content_sha256
    assert cohort['release_source_sha256']==row['release_source_sha256'] and cohort['release_source_sha256'] is not None
    assert report['score']['pending_n']==1 and not report['production_approved']



@pytest.mark.parametrize('fn',[directional_diagnostics,interval_diagnostics])
@pytest.mark.parametrize('field',['forecast_dataset_manifest_sha256','forecast_code_sha256'])
def test_manifest_and_model_code_do_not_pool_identical_payloads(fn,field):
    a=bound(forecast_dataset_manifest_sha256='e'*64,forecast_dataset_id='fixture',forecast_dataset_version='v1',forecast_code_sha256='f'*64)
    b=deepcopy(a);b[field]='d'*64
    assert len(fn([a,b])['cohorts'])==2



@pytest.mark.parametrize('change',[{'forecast_dataset_manifest_sha256':'e'*64},{'forecast_dataset_id':'fixture'},{'forecast_dataset_manifest_sha256':'e'*64,'forecast_dataset_id':'fixture','forecast_dataset_version':True}])
def test_partial_or_invalid_manifest_version_binding_refuses(change):
    with pytest.raises(ForecastEvidenceRefused):interval_diagnostics([bound(**change)])
