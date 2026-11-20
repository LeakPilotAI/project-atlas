"""Actual immutable histories feed the built viewer's conservative prior-case context."""
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from app.backtest.forecast_artifacts import publish_forecast
from app.backtest.forecast_report import (
    ForecastHistory,
    browser_export,
    build_accountability_report,
)
from test_afi_baselines import ASOF, fit, history
from test_afi_outcomes import CORRECTED, RESOLVED, append, changed_review


def test_actual_prior_history_and_late_correction_in_embedded_workspace(tmp_path):
    review = history()
    forecasts = tmp_path / 'forecasts'
    outcomes = tmp_path / 'outcomes'
    forecasts.mkdir()
    outcomes.mkdir()
    paths = [publish_forecast(forecasts, review,
             fit(review, method='NO_CHANGE', issued_at=datetime(2026, 10, day, 0, 1, tzinfo=UTC)),
             evidence_asof=ASOF) for day in (17, 19)]
    resolved, first = append(outcomes, paths[0], review, outcome_asof=RESOLVED)
    newer = changed_review(review)
    corrected, second = append(outcomes, paths[0], review, newer, outcome_asof=CORRECTED,
                               history=[(resolved, review)], expected_head=first['artifact_sha256'])
    before = {p: p.read_bytes() for p in [*paths, resolved, corrected]}
    reports = []
    for records, head in [(((resolved, review),), first['artifact_sha256']),
                          (((resolved, review), (corrected, newer)), second['artifact_sha256'])]:
        report = build_accountability_report([
            ForecastHistory(paths[0], review, records, head), ForecastHistory(paths[1], review),
        ], evidence_asof=ASOF)
        reports.append(browser_export(report))
    fixture = tmp_path / 'reports.json'
    fixture.write_text(json.dumps(reports), encoding='utf-8')
    repo = Path(__file__).resolve().parents[1]
    node = 'C:/Program Files/nodejs/node.exe'
    workspace = tmp_path / 'workspace'
    subprocess.run([node, str(repo / 'frontend/offline/workspace/build-v2.mjs'), str(workspace)],
                   capture_output=True, text=True, check=True, timeout=20)
    script = r"""
const fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[1],'utf8'),code=html.match(/<script>([\s\S]*?)<\/script>/)[1],box={exports:{}};
assert.ok(html.includes('id="memory-query"'));assert.ok(html.includes('id="memory-rows"'));
vm.runInNewContext(code,{module:box,crypto:crypto.webcrypto,TextEncoder,TextDecoder},{timeout:2000});
(async()=>{
 const reports=await Promise.all(JSON.parse(fs.readFileSync(process.argv[2],'utf8')).map(raw=>box.exports.verifyEnvelope(raw)));
 const query=reports[0].rows.find(r=>r.issued_at.startsWith('2026-10-19'));
 const original=box.exports.priorCaseContext(reports[0].rows,query.forecast_sha256);
 assert.equal(original.prior_n,1);assert.equal(original.known_outcome_n,1);assert.notEqual(original.cases[0].actual,null);
 const later=box.exports.priorCaseContext(reports[1].rows,query.forecast_sha256);
 assert.equal(later.prior_n,1);assert.equal(later.unavailable_outcome_n,1);assert.equal(later.cases[0].actual,null);
 assert.equal(later.cases[0].outcome_dataset_sha256,null);assert.equal(later.similarity_ranking_established,false);
 assert.equal(later.historical_availability_authenticated,false);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    result = subprocess.run([node, '-e', script, str(workspace / 'forecast.html'), str(fixture)],
                            capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert all(p.read_bytes() == raw for p, raw in before.items())
