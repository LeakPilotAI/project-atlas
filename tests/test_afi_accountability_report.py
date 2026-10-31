import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime

import pytest
from app.backtest.forecast_artifacts import publish_forecast
from app.backtest.forecast_baselines import fingerprint, fit_baseline, predict_baseline
from app.backtest.forecast_dataset import review_dataset
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_report import (
    ForecastHistory,
    build_accountability_report,
    main,
    render_accountability_report,
    run_bundle,
)
from test_afi_baselines import ASOF, history
from test_afi_outcomes import CORRECTED, RESOLVED, append, changed_review, setup


def bundle_fixture(tmp_path):
    r,_s,f,out=setup(tmp_path)
    (tmp_path/'original-manifest.json').write_bytes(r.manifest_bytes);(tmp_path/'original-records.json').write_bytes(r.payload_bytes)
    spec={'artifact':f.relative_to(tmp_path).as_posix(),'dataset_manifest':'original-manifest.json','dataset_records':'original-records.json',
          'source_manifest':None,'source_root':None,'history':[],'expected_head':None,'append':None}
    b={'schema':'AFI_ACCOUNTABILITY_BUNDLE_V1','asof':ASOF.isoformat(),'forecasts':[spec]}
    return r,f,out,b


def save(tmp_path,bundle):
    (tmp_path/'bundle.json').write_text(json.dumps(bundle),encoding='utf-8')


def test_report_scores_latest_correction_once_not_every_history_event(tmp_path):
    r,_s,f,out=setup(tmp_path);p,a=append(out,f,r,outcome_asof=RESOLVED)
    newer=changed_review(r);q,b=append(out,f,r,newer,outcome_asof=CORRECTED,history=[(p,r)],expected_head=a['artifact_sha256'])
    e=ForecastHistory(f,r,((p,r),(q,newer)),b['artifact_sha256'])
    report=build_accountability_report([e],evidence_asof=ASOF)
    assert report['forecast_n']==1 and report['score']['scored_n']==1 and report['correction_n']==1
    assert report['rows'][0]['actual']==155 and report['rows'][0]['history_n']==2
    assert 'input_source_sha256' not in report['rows'][0]
    assert not report['calibration_established'] and not report['production_approved']
    before_render=deepcopy(report)
    html=render_accountability_report(report)
    assert 'Signed price error diagnostics' in html and 'Mean signed error' in html
    assert report == before_render
    assert 'Directional outcome diagnostics' in html
    assert '<script' not in html.lower() and 'scope="col"' in html and 'Production NO-GO' in html
    with pytest.raises(ForecastEvidenceRefused):build_accountability_report([e,e],evidence_asof=ASOF)



def test_accountability_html_table_column_alignment(tmp_path):
    from html.parser import HTMLParser

    class Tables(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tables = []
            self.current = None
            self.section = None
            self.cells = None
            self.text_parts = None

        def handle_starttag(self, tag, attrs):
            if tag == "table":
                self.current = {"headers": [], "rows": []}
                self.tables.append(self.current)
            elif self.current is not None:
                if tag == "thead":
                    self.section = "head"
                elif tag == "tbody":
                    self.section = "body"
                elif tag == "tr":
                    self.cells = []
                elif tag in ("th", "td"):
                    self.text_parts = []

        def handle_data(self, data):
            if self.text_parts is not None:
                self.text_parts.append(data)

        def handle_endtag(self, tag):
            if tag in ("th", "td") and self.text_parts is not None:
                self.cells.append("".join(self.text_parts).strip())
                self.text_parts = None
            elif tag == "tr" and self.cells is not None:
                if self.section == "head":
                    self.current["headers"] = self.cells
                elif self.section == "body":
                    self.current["rows"].append(self.cells)
                self.cells = None
            elif tag in ("thead", "tbody"):
                self.section = None
            elif tag == "table":
                self.current = None

    review, _, forecast_path, _ = setup(tmp_path)
    report = build_accountability_report(
        [ForecastHistory(forecast_path, review)],
        evidence_asof=ASOF,
    )
    parser = Tables()
    parser.feed(render_accountability_report(report))

    assert parser.tables, "Expected rendered accountability tables"

    for table in parser.tables:
        assert table["headers"], "Table missing column headings"
        for row in table["rows"]:
            assert len(row) == len(table["headers"]), (
                f"Column mismatch: {len(table['headers'])} headings, "
                f"{len(row)} values"
            )

    latest = parser.tables[0]
    assert len(latest["headers"]) == 16
    assert latest["headers"][9] == "Input source hash"
    assert latest["rows"], "Expected forecast evidence row"
    assert len(latest["rows"][0]) == 16
    assert latest["rows"][0][9] == "Unavailable"

def test_unobserved_forecast_is_pending_and_report_substitution_refuses(tmp_path):
    r,_s,f,_out=setup(tmp_path)
    report=build_accountability_report([ForecastHistory(f,r)],evidence_asof=ASOF)
    assert report['rows'][0]['status']=='FORECAST_ONLY' and report['score']['pending_n']==1
    assert 'input_source_sha256' not in report['rows'][0]
    bad=deepcopy(report);bad['score']['scored_n']=999
    with pytest.raises(ForecastEvidenceRefused):render_accountability_report(bad)


def test_source_bound_input_provenance_flows_to_report_without_rewriting_forecasts(tmp_path):
    review=history()
    manifest=json.loads(review.manifest_bytes);payload=json.loads(review.payload_bytes)
    for record in payload['records']:
        record['source_sha256']='a'*64
        identity={'asset_id':record['asset_id'],'observed_at':record['observed_at'],
                  'received_at':record['available_at'],'value':record['value'],
                  'source_sha256':record['source_sha256']}
        revision=hashlib.sha256((json.dumps(identity,sort_keys=True,separators=(',',':'))+'\n').encode()).hexdigest()
        record['record_id']=record['revision']=revision
    payload_bytes=json.dumps(payload,sort_keys=True,separators=(',',':')).encode()
    manifest['content_sha256']=hashlib.sha256(payload_bytes).hexdigest()
    review=review_dataset(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode(),
                          payload_bytes,asof=ASOF)
    model=fit_baseline(review,asset_id='CRYPTO:BTC-USD',
                       issued_at=datetime(2026,10,1,0,1,tzinfo=UTC),evidence_asof=ASOF,lookback=5)
    forecast=predict_baseline(model,review,evidence_asof=ASOF)
    publish_forecast(tmp_path,review,model,evidence_asof=ASOF)
    forecast_path=next(tmp_path.glob('*.json'))
    report=build_accountability_report([ForecastHistory(forecast_path,review)],evidence_asof=ASOF)
    row=report['rows'][0]
    assert row['input_observed_at']==forecast.input_observed_at.isoformat()
    assert row['input_available_at']==forecast.input_available_at.isoformat()
    assert row['input_source_id']=='fixture' and row['input_source_sha256']=='a'*64
    html=render_accountability_report(report)
    assert 'Input source hash' in html and 'a'*64 in html
    bad=deepcopy(report);bad['rows'][0]['input_available_at']='2026-09-30T00:00:00+00:00'
    bad['report_sha256']=fingerprint({key:value for key,value in bad.items() if key!='report_sha256'})
    with pytest.raises(ForecastEvidenceRefused,match='issue time'):
        render_accountability_report(bad)


def test_explicit_bundle_publishes_report_dashboard_and_idempotent_outcome(tmp_path):
    _r,_f,out,b=bundle_fixture(tmp_path)
    b['forecasts'][0]['append']={'dataset_manifest':'original-manifest.json','dataset_records':'original-records.json',
                                'source_manifest':None,'source_root':None,'outcome_asof':RESOLVED.isoformat()}
    save(tmp_path,b)
    a=run_bundle(bundle_root=tmp_path,bundle_name='bundle.json',output_root=out)
    before={p.name:p.read_bytes() for p in out.iterdir()}
    c=run_bundle(bundle_root=tmp_path,bundle_name='bundle.json',output_root=out)
    assert a==c and {p.name:p.read_bytes() for p in out.iterdir()}==before
    report=json.loads((out/a['report']).read_bytes())
    assert report['score']['scored_n']==1 and a['status']=='OFFLINE_ACCOUNTABILITY_COMPLETE'
    assert '<script' not in (out/a['dashboard']).read_text(encoding='utf-8')


def test_bundle_correction_chain_returns_new_head_and_keeps_prior_bytes(tmp_path):
    r,_f,out,b=bundle_fixture(tmp_path)
    spec=b['forecasts'][0];spec['append']={'dataset_manifest':'original-manifest.json','dataset_records':'original-records.json',
                                        'source_manifest':None,'source_root':None,'outcome_asof':RESOLVED.isoformat()}
    save(tmp_path,b);first=run_bundle(bundle_root=tmp_path,bundle_name='bundle.json',output_root=out)
    head=first['updated_heads'][0];path=out/(head+'.json');raw=path.read_bytes()
    newer=changed_review(r);(tmp_path/'new-manifest.json').write_bytes(newer.manifest_bytes);(tmp_path/'new-records.json').write_bytes(newer.payload_bytes)
    spec['history']=[{'artifact':path.relative_to(tmp_path).as_posix(),'dataset_manifest':'original-manifest.json','dataset_records':'original-records.json',
                      'source_manifest':None,'source_root':None}];spec['expected_head']=head
    spec['append'].update(dataset_manifest='new-manifest.json',dataset_records='new-records.json',outcome_asof=CORRECTED.isoformat())
    save(tmp_path,b);second=run_bundle(bundle_root=tmp_path,bundle_name='bundle.json',output_root=out)
    report=json.loads((out/second['report']).read_bytes())
    assert report['correction_n']==1 and second['updated_heads'][0]!=head and path.read_bytes()==raw


@pytest.mark.parametrize('bad',['traversal','absolute','backslash','missing-history-head','duplicate','historical','unknown-field'])
def test_malformed_or_unauthorized_bundles_fail_before_publication(tmp_path,bad):
    r,_f,out,b=bundle_fixture(tmp_path);spec=b['forecasts'][0]
    if bad=='traversal':spec['dataset_records']='../outside.json'
    if bad=='absolute':spec['artifact']='C:/secret.json'
    if bad=='backslash':spec['artifact']='forecasts\\other.json'
    if bad=='missing-history-head':spec['expected_head']='a'*64
    if bad=='duplicate':b['forecasts'].append(deepcopy(spec))
    if bad=='historical':
        m=json.loads(r.manifest_bytes);m['evidence_class']='HISTORICAL';m['source']['permission_status']='DECLARED'
        (tmp_path/'original-manifest.json').write_text(json.dumps(m),encoding='utf-8')
    if bad=='unknown-field':spec['production_override']=True
    save(tmp_path,b)
    with pytest.raises(ForecastEvidenceRefused):run_bundle(bundle_root=tmp_path,bundle_name='bundle.json',output_root=out)
    assert not list(out.iterdir())


def test_bundle_cli_refusal_is_nonzero_and_does_not_expose_payload(tmp_path,capsys):
    _r,_f,out,b=bundle_fixture(tmp_path);b['forecasts'][0]['dataset_records']='missing-secret-name.json';save(tmp_path,b)
    assert main(['--bundle-root',str(tmp_path),'--bundle','bundle.json','--output-root',str(out)])==2
    data=json.loads(capsys.readouterr().out)
    assert data['status']=='REFUSED' and 'missing-secret-name' not in str(data)

def test_browser_export_hashes_exact_python_json_bytes_and_preserves_refusal_flags(tmp_path):
    import hashlib

    from app.backtest.forecast_report import browser_export
    r,_s,f,_out=setup(tmp_path)
    report=build_accountability_report([ForecastHistory(f,r)],evidence_asof=ASOF)
    envelope=json.loads(browser_export(report))
    assert envelope['schema']=='AFI_BROWSER_REPORT_V1'
    assert hashlib.sha256(envelope['report_json'].encode()).hexdigest()==envelope['payload_sha256']
    assert json.loads(envelope['report_json'])==report
    report['production_approved']=True
    with pytest.raises(ForecastEvidenceRefused):browser_export(report)


def test_v2_portable_source_archive_can_replace_extracted_source_pairs(tmp_path):
    from app.backtest.forecast_source import source_archive_bytes
    from test_afi_source_binding import source
    r,f,out,b=bundle_fixture(tmp_path)
    from app.backtest.forecast_artifacts import publish_forecast
    from test_afi_source_binding import model
    f=publish_forecast(f.parent,r,model(r,source()),evidence_asof=ASOF,source_review=source())
    b['schema']='AFI_ACCOUNTABILITY_BUNDLE_V2'
    spec=b['forecasts'][0];spec['artifact']=f.relative_to(tmp_path).as_posix();spec.pop('source_manifest');spec.pop('source_root')
    archive=tmp_path/'source.json';archive.write_bytes(source_archive_bytes(source()))
    spec['source_archive']='source.json';save(tmp_path,b)
    result=run_bundle(bundle_root=tmp_path,bundle_name='bundle.json',output_root=out)
    assert result['forecast_n']==1 and not result['production_approved']


@pytest.mark.parametrize('mode',['mixed','traversal','changed'])
def test_v2_source_refuses_conflicting_escaping_or_changed_archive(tmp_path,mode):
    from app.backtest.forecast_source import source_archive_bytes
    from test_afi_source_binding import source
    _,_,out,b=bundle_fixture(tmp_path)
    b['schema']='AFI_ACCOUNTABILITY_BUNDLE_V2';spec=b['forecasts'][0]
    spec.pop('source_manifest');spec.pop('source_root');spec['source_archive']='source.json'
    raw=source_archive_bytes(source());(tmp_path/'source.json').write_bytes(raw)
    if mode=='mixed':spec['source_root']='source'
    if mode=='traversal':spec['source_archive']='../source.json'
    if mode=='changed':(tmp_path/'source.json').write_bytes(raw.replace(b'fixture-v1',b'changed-v1'))
    save(tmp_path,b)
    with pytest.raises(ForecastEvidenceRefused):run_bundle(bundle_root=tmp_path,bundle_name='bundle.json',output_root=out)
    assert not list(out.iterdir())


@pytest.mark.parametrize('mutation',['authority','diagnostics'])
def test_derived_report_refuses_rehashed_authority_or_contradictory_diagnostics(tmp_path,mutation):
    from app.backtest.forecast_baselines import fingerprint
    r,_,f,_=setup(tmp_path)
    report=build_accountability_report([ForecastHistory(f,r)],evidence_asof=ASOF)
    if mutation=='authority':report['trading_authority']=True
    else:report['directional_diagnostics']['cohorts'][0]['pending_n']=0
    report['report_sha256']=fingerprint({k:v for k,v in report.items() if k!='report_sha256'})
    with pytest.raises(ForecastEvidenceRefused):render_accountability_report(report)
