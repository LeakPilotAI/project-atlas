"""Receipt-by-receipt daily sources support explicit pre-forecast intervals."""
import copy
import hashlib
import json
import subprocess
from datetime import timedelta
from pathlib import Path

from app.backtest.forecast_artifacts import publish_research_text
from app.backtest.forecast_dataset import review_dataset
from app.backtest.forecast_replay import freeze_selection
from app.backtest.forecast_report import prepare_batch_accountability, run_bundle
from app.backtest.forecast_uncertainty import fit_interval
from test_daily_afi_bridge import POLICY, chart, days, encode, end, universe

from scripts.observation_runtime.daily_afi_export import export_daily_dataset
from scripts.observation_runtime.daily_forecast_batch import run_daily_forecast_batch


def test_daily_receipt_history_interval_freeze_then_corrected_accountability(tmp_path):
    calendar = days(41)
    snapshots = []

    def retain(payload, stamp):
        raw = encode(payload)
        path = publish_research_text(tmp_path, raw.decode(), extension='.json')
        return {'file': path.name, 'sha256': hashlib.sha256(raw).hexdigest(), 'received_at': stamp.isoformat()}

    # A single late download could not support these historical issue times.
    # Retain each synthetic receipt, rather than invent earlier availability.
    for index in range(1, 40):
        snapshots.append(retain(chart(calendar[:index+1]), end(calendar[index])+timedelta(minutes=1)))
    issue = end(calendar[39])+timedelta(minutes=2)
    source_request = {'schema': 'ATLAS_SYNTHETIC_DAILY_EXPORT_REQUEST_V1', 'snapshots': snapshots,
                      'symbol': 'SPY', 'asset_class': 'US_ETF', 'universe': universe(),
                      'dataset_id': 'interval-daily', 'version': 'v1', 'asof': issue.isoformat(), **POLICY}

    def export(request):
        (tmp_path/'source-request.json').write_bytes(encode(request))
        result = export_daily_dataset(bundle_root=tmp_path, request_name='source-request.json', output_root=tmp_path)
        return result['binding'], json.loads((tmp_path/result['binding']).read_bytes())['artifacts']

    binding, original = export(source_request)
    review = review_dataset((tmp_path/original['manifest']).read_bytes(), (tmp_path/original['records']).read_bytes(), asof=issue)
    selection = freeze_selection(review, asset_id='ETF:SPY', selection_issues=[end(calendar[i])+timedelta(minutes=2) for i in [10, 11]],
                                 frozen_at=end(calendar[15])+timedelta(minutes=2), evidence_asof=issue, lookback=5)
    specs = []
    interval_names = []
    for level in [.8, .9]:
        interval = fit_interval(review, selection, calibration_issues=[end(calendar[i])+timedelta(minutes=2) for i in range(16, 36)],
                                calibrated_at=end(calendar[37])+timedelta(minutes=2), evidence_asof=issue, level=level)
        assert interval['n'] == 20 and interval['calibration_established'] is False
        path = publish_research_text(tmp_path, encode(interval).decode(), extension='.json')
        interval_names.append(path.name)
        specs.append({'daily_export': binding, 'expected_daily_export_sha256': binding[:-5], 'asset_id': 'ETF:SPY',
                      'issued_at': issue.isoformat(), 'method': selection['selected_method'], 'lookback': 5, 'horizon': '1D',
                      'interval': path.name, 'probability_method': None})
    request = {'schema': 'ATLAS_SYNTHETIC_DAILY_FORECAST_REQUEST_V1', 'asof': issue.isoformat(), 'forecasts': specs}
    (tmp_path/'forecast-request.json').write_bytes(encode(request))
    batch = run_daily_forecast_batch(bundle_root=tmp_path, request_name='forecast-request.json', output_root=tmp_path)
    before = {name: (tmp_path/name).read_bytes() for name in interval_names}
    index = json.loads((tmp_path/batch['index']).read_bytes())
    (tmp_path/'prepared').mkdir()
    (tmp_path/'reports').mkdir()
    final_receipt = end(calendar[40])+timedelta(minutes=1)
    source_request['snapshots'].append(retain(chart(calendar), final_receipt))
    source_request.update(version='v2', asof=final_receipt.isoformat())
    _, labels = export(source_request)
    accounting = {'schema': 'AFI_BATCH_ACCOUNTABILITY_REQUEST_V1', 'asof': final_receipt.isoformat(),
                  'batch_plan': batch['daily_batch_plan'], 'batch_index': batch['index'], 'expected_index_sha256': batch['index'][:-5],
                  'outcomes': [{'forecast_sha256': item['forecast_sha256'], 'history': [], 'expected_head': None,
                                'append': {'dataset_manifest': labels['manifest'], 'dataset_records': labels['records'],
                                           'source_archive': None, 'outcome_asof': final_receipt.isoformat()}} for item in index['items']]}

    def execute():
        (tmp_path/'accounting-request.json').write_bytes(encode(accounting))
        prepared = prepare_batch_accountability(bundle_root=tmp_path, request_name='accounting-request.json', output_root=tmp_path/'prepared')
        return run_bundle(bundle_root=tmp_path, bundle_name='prepared/'+prepared['bundle'], output_root=tmp_path/'reports')

    resolved = execute()
    first_report = json.loads((tmp_path/'reports'/resolved['report']).read_bytes())
    assert first_report['score']['scored_n'] == 2
    assert {row['interval']['level'] for row in first_report['rows']} == {.8, .9}
    for item, head in zip(accounting['outcomes'], resolved['updated_heads'], strict=True):
        item.update(history=[{'artifact': 'reports/'+head+'.json', 'dataset_manifest': labels['manifest'],
                              'dataset_records': labels['records'], 'source_archive': None}], expected_head=head)
    correction = copy.deepcopy(chart(calendar))
    quote = correction['chart']['result'][0]['indicators']['quote'][0]
    quote['close'][-1] -= 10
    quote['low'][-1] = quote['close'][-1]-1
    cutoff = final_receipt+timedelta(hours=1)
    source_request['snapshots'].append(retain(correction, cutoff))
    source_request.update(version='v3', asof=cutoff.isoformat())
    _, corrected_labels = export(source_request)
    accounting['asof'] = cutoff.isoformat()
    for item in accounting['outcomes']:
        item['append'].update(dataset_manifest=corrected_labels['manifest'], dataset_records=corrected_labels['records'], outcome_asof=cutoff.isoformat())
    final = execute()
    report = json.loads((tmp_path/'reports'/final['report']).read_bytes())
    assert report['correction_n'] == 2 and report['calibration_established'] is False
    assert all((tmp_path/name).read_bytes() == raw for name, raw in before.items())
    viewer = Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    script = """const v=require(process.argv[1]),fs=require('fs');
Promise.all(process.argv.slice(2).map(p=>v.verifyEnvelope(fs.readFileSync(p,'utf8')))).then(([a,b])=>{
const c=v.compareReportVintages(a,b);if(c.union_forecast_n!==2)throw Error('interval count');
for(const r of c.rows){const x=r.score_impact.interval;
if(x.state!=='FINITE'||x.left_covered!==true||x.right_covered!==false||!(x.right_minus_left_score>0))throw Error('interval correction');}
process.stdout.write('VERIFIED_INTERVAL_CORRECTION');}).catch(e=>{console.error(e);process.exitCode=1});"""
    checked = subprocess.run(['C:/Program Files/nodejs/node.exe', '-e', script, str(viewer),
                              str(tmp_path/'reports'/resolved['browser_export']), str(tmp_path/'reports'/final['browser_export'])],
                             capture_output=True, text=True, timeout=15, check=False)
    assert checked.returncode == 0, checked.stderr
    assert checked.stdout == 'VERIFIED_INTERVAL_CORRECTION'
