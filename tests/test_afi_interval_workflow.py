"""Complete actual offline CLI -> vintage correction -> local viewer acceptance."""
import json
import subprocess
from pathlib import Path

import app
from app.backtest.forecast_cli import run
from app.backtest.forecast_replay import freeze_selection
from app.backtest.forecast_report import run_bundle
from app.backtest.forecast_source import package_source, review_source_archive
from app.backtest.forecast_uncertainty import fit_interval
from test_afi_baselines import ASOF, ASSET, history
from test_afi_outcomes import CORRECTED, RESOLVED, changed_review
from test_afi_replay import issue
from test_afi_uncertainty import CALIBRATION, FREEZE


def test_source_bound_interval_cli_accountability_correction_and_viewer(tmp_path):
    packages=tmp_path/'source';packages.mkdir()
    package=package_source(Path(app.__file__).resolve().parent.parent,packages,release_id='interval-offline-20261019',include=['app/backtest/forecast_outcomes.py','app/backtest/forecast_report.py'])
    archive=packages/package['archive'];source=review_source_archive(archive.read_bytes());r=history()
    selection=freeze_selection(r,asset_id=ASSET,selection_issues=[issue(20),issue(21)],frozen_at=issue(24),evidence_asof=ASOF,lookback=5,source_review=source)
    interval=fit_interval(r,selection,calibration_issues=CALIBRATION,calibrated_at=FREEZE,evidence_asof=ASOF,source_review=source)
    (tmp_path/'interval.json').write_text(json.dumps(interval),encoding='utf-8')
    for name,review in [('original',r),('corrected',changed_review(r))]:
        (tmp_path/(name+'-manifest.json')).write_bytes(review.manifest_bytes);(tmp_path/(name+'-records.json')).write_bytes(review.payload_bytes)
    forecasts=tmp_path/'forecasts';forecasts.mkdir();reports=tmp_path/'reports';reports.mkdir()
    from datetime import UTC, datetime
    produced=run(manifest=tmp_path/'original-manifest.json',records=tmp_path/'original-records.json',output_root=forecasts,asset_id=ASSET,issued_at=datetime(2026,10,17,0,1,tzinfo=UTC),evidence_asof=ASOF,method=selection['selected_method'],lookback=5,source_archive=archive,interval_path=tmp_path/'interval.json')
    original=(forecasts/produced['forecast_artifact']).read_bytes()
    def dataset(name):return {'dataset_manifest':name+'-manifest.json','dataset_records':name+'-records.json','source_archive':'source/'+package['archive']}
    spec={'artifact':'forecasts/'+produced['forecast_artifact'],**dataset('original'),'history':[],'expected_head':None,'append':{**dataset('original'),'outcome_asof':RESOLVED.isoformat()}}
    bundle={'schema':'AFI_ACCOUNTABILITY_BUNDLE_V2','asof':ASOF.isoformat(),'forecasts':[spec]};path=tmp_path/'bundle.json';path.write_text(json.dumps(bundle),encoding='utf-8')
    initial=run_bundle(bundle_root=tmp_path,bundle_name='bundle.json',output_root=reports);head=initial['updated_heads'][0]
    first=(reports/(head+'.json')).read_bytes()
    spec.update(history=[{'artifact':'reports/'+head+'.json',**dataset('original')}],expected_head=head,append={**dataset('corrected'),'outcome_asof':CORRECTED.isoformat()})
    path.write_text(json.dumps(bundle),encoding='utf-8');result=run_bundle(bundle_root=tmp_path,bundle_name='bundle.json',output_root=reports)
    report=json.loads((reports/result['report']).read_bytes());c=report['interval_diagnostics']['cohorts'][0]
    assert c['resolved_n']==1 and c['status']=='INSUFFICIENT_EVIDENCE' and report['correction_n']==1
    assert c['cohort']['model_version']==report['rows'][0]['model_version'] and c['cohort']['lookback']==5
    assert (forecasts/produced['forecast_artifact']).read_bytes()==original and (reports/(head+'.json')).read_bytes()==first
    viewer=Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability'
    script="const v=require(process.argv[1]),fs=require('node:fs'),c=require('node:crypto');v.verifyEnvelope(fs.readFileSync(process.argv[2],'utf8'),t=>c.createHash('sha256').update(t).digest('hex')).then(r=>{if(r.interval_diagnostics.cohorts[0].resolved_n!==1||r.correction_n!==1)process.exit(2);const cohorts=v.forecastPlot(r.rows).cohorts;if(cohorts.length!==1)process.exit(4);const plot=v.forecastPlot(r.rows,cohorts[0].id);if(plot.points.length!==1||plot.points[0].row.actual!==r.rows[0].actual||JSON.stringify(plot.points[0].row.interval)!==JSON.stringify(r.rows[0].interval)||plot.points[0].row.correction_n!==1)process.exit(5);console.log('ACCEPTED_SYNTHETIC_ONLY');}).catch(()=>process.exit(3));"
    accepted=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(viewer/'view.cjs'),str(reports/result['browser_export'])],capture_output=True,text=True,check=True,timeout=10)
    subprocess.run(['C:/Program Files/nodejs/node.exe',str(viewer/'build.cjs'),str(tmp_path/'viewer.html')],capture_output=True,text=True,check=True,timeout=10)
    (tmp_path/'acceptance.json').write_text(json.dumps({'scope':'OFFLINE_SYNTHETIC_ONLY','source':package,'forecast':produced,'report':result,'viewer':accepted.stdout.strip(),'production_approved':False},indent=2),encoding='utf-8')

    workspace=tmp_path/'workspace-v2'
    subprocess.run(['C:/Program Files/nodejs/node.exe',str(viewer.parent/'workspace/build-v2.mjs'),str(workspace)],capture_output=True,text=True,check=True,timeout=15)
    embedded=r"""const fs=require('node:fs'),vm=require('node:vm'),c=require('node:crypto');
const html=fs.readFileSync(process.argv[1],'utf8'),script=html.match(/<script>([\s\S]*?)<\/script>/)[1],box={exports:{}};
vm.runInNewContext(script,{module:box,crypto:c.webcrypto,TextEncoder,TextDecoder},{timeout:2000});
box.exports.verifyEnvelope(fs.readFileSync(process.argv[2],'utf8')).then(r=>{const groups=box.exports.forecastPlot(r.rows).cohorts;if(r.correction_n!==1||groups.length!==1||box.exports.forecastPlot(r.rows,groups[0].id).points.length!==1)process.exitCode=2;}).catch(()=>process.exitCode=3);"""
    subprocess.run(['C:/Program Files/nodejs/node.exe','-e',embedded,str(workspace/'forecast.html'),str(reports/result['browser_export'])],capture_output=True,text=True,check=True,timeout=15)
    assert 'browser_export' in (workspace/'README.txt').read_text(encoding='utf-8')
    assert (forecasts/produced['forecast_artifact']).read_bytes()==original
    assert (reports/(head+'.json')).read_bytes()==first
