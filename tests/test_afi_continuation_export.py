import json

import pytest
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_report import main, run_bundle
from test_afi_batch_accountability import prepare, setup
from test_afi_dataset_integrity import encode


def test_reusable_bundle_preserves_pending_resolved_history(tmp_path):
    _,plan,_,_,request,prepared,reports=setup(tmp_path)
    for instruction,spec in zip(request['outcomes'],plan['forecasts'],strict=True):
        instruction['append']={**{k:spec[k] for k in ('dataset_manifest','dataset_records','source_archive')},
                               'outcome_asof':'2026-10-16T20:02:00+00:00'}
    bridge=prepare(tmp_path,prepared,request)
    first=run_bundle(bundle_root=tmp_path,bundle_name='prepared/'+bridge['bundle'],output_root=reports,
                     continuation_output_prefix='reports')
    original={p:p.read_bytes() for p in reports.iterdir()}
    retained=json.loads((reports/first['continuation_bundle']).read_bytes())
    assert all(s['append'] is None and len(s['history'])==1 for s in retained['forecasts'])
    replay=run_bundle(bundle_root=tmp_path,bundle_name='reports/'+first['continuation_bundle'],output_root=reports,
                      continuation_output_prefix='reports')
    assert replay['continuation_bundle']==first['continuation_bundle']
    assert replay['updated_heads']==first['updated_heads']
    for spec in retained['forecasts']:
        spec['append']={**{k:spec[k] for k in ('dataset_manifest','dataset_records','source_archive')},
                        'outcome_asof':'2026-10-19T20:30:00+00:00'}
    (tmp_path/'next.json').write_bytes(encode(retained))
    resolved=run_bundle(bundle_root=tmp_path,bundle_name='next.json',output_root=reports,
                        continuation_output_prefix='reports')
    assert resolved['scored_n']==3
    final=json.loads((reports/resolved['continuation_bundle']).read_bytes())
    assert all(s['append'] is None and len(s['history'])==2 for s in final['forecasts'])
    assert all(p.read_bytes()==raw for p,raw in original.items())
    assert main(['--bundle-root',str(tmp_path),'--output-root',str(reports),'--bundle',
                 'reports/'+resolved['continuation_bundle'],'--continuation-output-prefix','reports'])==0


@pytest.mark.parametrize('prefix',['../reports','reports/../reports','prepared','missing'])
def test_invalid_mapping_refused_before_append(tmp_path,prefix):
    _,plan,_,_,request,prepared,reports=setup(tmp_path)
    for instruction,spec in zip(request['outcomes'],plan['forecasts'],strict=True):
        instruction['append']={**{k:spec[k] for k in ('dataset_manifest','dataset_records','source_archive')},
                               'outcome_asof':'2026-10-19T20:30:00+00:00'}
    bridge=prepare(tmp_path,prepared,request)
    with pytest.raises(ForecastEvidenceRefused):
        run_bundle(bundle_root=tmp_path,bundle_name='prepared/'+bridge['bundle'],output_root=reports,
                   continuation_output_prefix=prefix)
    assert not list(reports.iterdir())


def test_export_failure_never_returns_complete(tmp_path,monkeypatch):
    from app.backtest import forecast_report
    _,_,_,_,request,prepared,reports=setup(tmp_path)
    bridge=prepare(tmp_path,prepared,request)
    real=forecast_report.publish_research_text
    def fail_export(root,text,**kwargs):
        if 'AFI_ACCOUNTABILITY_BUNDLE_V2' in text:
            raise OSError('synthetic continuation publication failure')
        return real(root,text,**kwargs)
    monkeypatch.setattr(forecast_report,'publish_research_text',fail_export)
    with pytest.raises(OSError,match='publication failure'):
        run_bundle(bundle_root=tmp_path,bundle_name='prepared/'+bridge['bundle'],output_root=reports,
                   continuation_output_prefix='reports')
    assert list(reports.iterdir())  # Prior immutable outputs retained, never rolled back.
