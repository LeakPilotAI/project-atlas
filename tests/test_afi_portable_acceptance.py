"""Actual supplied source -> forecast correction -> local viewer contract, synthetic data only."""
import hashlib
import json
import subprocess
from pathlib import Path

import app
from app.backtest.forecast_artifacts import publish_forecast
from app.backtest.forecast_outcomes import append_outcome
from app.backtest.forecast_report import (
    ForecastHistory,
    browser_export,
    build_accountability_report,
    run_bundle,
)
from app.backtest.forecast_source import package_source, review_source_archive
from test_afi_baselines import ASOF, history
from test_afi_outcomes import CORRECTED, RESOLVED, changed_review
from test_afi_source_binding import model


def test_current_source_bound_correction_imports_in_actual_local_viewer(tmp_path):
    source_root=Path(app.__file__).resolve().parent.parent
    packages=tmp_path/"packages";packages.mkdir()
    package=package_source(source_root,packages,release_id="offline-20261019",include=["app/backtest/forecast_outcomes.py","app/backtest/forecast_report.py"])
    source=review_source_archive((packages/package["archive"]).read_bytes())
    r=history();forecasts=tmp_path/"forecasts";forecasts.mkdir();outcomes=tmp_path/"outcomes";outcomes.mkdir()
    f=publish_forecast(forecasts,r,model(r,source),evidence_asof=ASOF,source_review=source)
    p,a=append_outcome(outcomes,f,r,r,outcome_asof=RESOLVED,evidence_asof=ASOF,source_review=source,outcome_source=source)
    revised=changed_review(r)
    q,b=append_outcome(outcomes,f,r,revised,outcome_asof=CORRECTED,evidence_asof=ASOF,source_review=source,outcome_source=source,history=[(p,r,source)],expected_head=a["artifact_sha256"])
    report=build_accountability_report([ForecastHistory(f,r,((p,r,source),(q,revised,source)),b["artifact_sha256"],source)],evidence_asof=ASOF)
    for name,review in [('original',r),('corrected',revised)]:
        (tmp_path/(name+'-manifest.json')).write_bytes(review.manifest_bytes)
        (tmp_path/(name+'-records.json')).write_bytes(review.payload_bytes)
    source_path='packages/'+package['archive']
    def dataset(name):return {'dataset_manifest':name+'-manifest.json','dataset_records':name+'-records.json','source_archive':source_path}
    bundle={'schema':'AFI_ACCOUNTABILITY_BUNDLE_V2','asof':ASOF.isoformat(),'forecasts':[{'artifact':f.relative_to(tmp_path).as_posix(),**dataset('original'),'history':[{'artifact':p.relative_to(tmp_path).as_posix(),**dataset('original')},{'artifact':q.relative_to(tmp_path).as_posix(),**dataset('corrected')}],'expected_head':b['artifact_sha256'],'append':None}]}
    (tmp_path/'bundle.json').write_text(json.dumps(bundle),encoding='utf-8')
    reports=tmp_path/'reports';reports.mkdir()
    emitted=run_bundle(bundle_root=tmp_path,bundle_name='bundle.json',output_root=reports)
    browser=reports/emitted['browser_export']
    assert browser.read_text(encoding='utf-8')==browser_export(report)
    assert json.loads((reports/emitted['report']).read_bytes())==report
    frontend=Path(__file__).resolve().parents[1]/"frontend/offline/forecast-accountability"
    script="const fs=require('node:fs'),c=require('node:crypto'),v=require(process.argv[1]);v.verifyEnvelope(fs.readFileSync(process.argv[2],'utf8'),t=>c.createHash('sha256').update(t).digest('hex')).then(r=>{if(r.forecast_n!==1||r.correction_n!==1||r.score.scored_n!==1||r.production_approved)process.exit(2);console.log(JSON.stringify({forecast_n:r.forecast_n,correction_n:r.correction_n,scored_n:r.score.scored_n,production_approved:r.production_approved}));}).catch(()=>process.exit(3));"
    result=subprocess.run(["C:/Program Files/nodejs/node.exe","-e",script,str(frontend/"view.cjs"),str(browser)],capture_output=True,text=True,timeout=10,check=True)
    assert json.loads(result.stdout)["correction_n"]==1
    subprocess.run(["C:/Program Files/nodejs/node.exe",str(frontend/"build.cjs"),str(tmp_path/"viewer.html")],capture_output=True,text=True,timeout=10,check=True)
    (tmp_path/"acceptance.json").write_text(json.dumps({"source":package,"bundle_result":emitted,"browser_sha256":hashlib.sha256(browser.read_bytes()).hexdigest(),"viewer_acceptance":json.loads(result.stdout),"scope":"OFFLINE_SYNTHETIC_ONLY"},indent=2),encoding="utf-8")
