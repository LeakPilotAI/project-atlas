"""Signed price errors are descriptive within provenance cohorts, never pooled skill."""
import json
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest
from app.backtest.forecast_report import signed_error_diagnostics
from test_afi_baselines import ASOF
from test_afi_directional_diagnostics import row


@pytest.mark.parametrize('case', ['balanced','over','under','pending','cancellation','overflow','underflow','partition'])
def test_signed_error_python_browser_parity_and_immutability(case):
    data = [row(110,100),row(90,100),row(100,100),row(110,None)]
    if case == 'over': data = [row(110,100),row(120,100)]
    if case == 'under': data = [row(90,100),row(80,100)]
    if case == 'pending': data = [row(110,None)]
    if case == 'cancellation': data = [row(1e16,1),row(2,1),row(1,1e16)]
    if case == 'overflow': data = [row(1e308,1),row(1e308,1)]
    if case == 'underflow': data = [row(1e-323,5e-324),row(5e-324,5e-324)]
    if case == 'partition': data += [dict(row(110,100),model='other'),dict(row(110,100),forecast_dataset_sha256='a'*64)]
    original = deepcopy(data)
    result = signed_error_diagnostics(data)
    root = Path(__file__).resolve().parents[1]
    script = "const api=require(process.argv[1]);let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>process.stdout.write(JSON.stringify(api.signedErrorDiagnostics(JSON.parse(s)))));"
    checked = subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(root/'frontend/offline/forecast-accountability/view.cjs')],
                             input=json.dumps(data),text=True,capture_output=True,timeout=10,check=False)
    assert checked.returncode == 0, checked.stderr
    other = json.loads(checked.stdout)
    def canonical(value): return sorted(value['cohorts'],key=lambda c:json.dumps(c['cohort'],sort_keys=True))
    assert canonical(result) == canonical(other)
    assert result['predictive_skill_established'] is result['independent_samples_established'] is False
    assert data == original
    c = result['cohorts'][0]
    if case == 'balanced':
        assert (c['over_n'],c['under_n'],c['equal_n'],c['pending_n']) == (1,1,1,1)
        assert c['mean_signed_error'] == 0
    if case == 'over': assert c['mean_signed_error'] == 15
    if case == 'under': assert c['mean_signed_error'] == -15
    if case == 'pending': assert c['mean_signed_error'] is None and c['status'] == 'NO_RESOLVED_OUTCOMES'
    if case == 'cancellation': assert c['mean_signed_error'] == pytest.approx(1/3)
    if case in ('overflow','underflow'): assert c['mean_signed_error'] is None and c['status'] == 'UNAVAILABLE_NUMERIC_RANGE'
    if case == 'partition': assert len(result['cohorts']) == 3


def test_published_label_history_scores_original_forecast_once_in_actual_viewer(tmp_path):
    from app.backtest.forecast_report import (
        ForecastHistory,
        browser_export,
        build_accountability_report,
        render_accountability_report,
    )
    from test_afi_outcomes import (
        CORRECTED,
        PENDING,
        RESOLVED,
        append,
        changed_review,
        setup,
    )

    reviewed,_,forecast,output = setup(tmp_path)
    pending,a = append(output,forecast,reviewed,outcome_asof=PENDING)
    resolved,b = append(output,forecast,reviewed,outcome_asof=RESOLVED,
                        history=[(pending,reviewed)],expected_head=a['artifact_sha256'])
    revised = changed_review(reviewed)
    corrected,c = append(output,forecast,reviewed,revised,outcome_asof=CORRECTED,
                         history=[(pending,reviewed),(resolved,reviewed)],expected_head=b['artifact_sha256'])
    immutable = {p:p.read_bytes() for p in tmp_path.rglob('*.json')}
    root = Path(__file__).resolve().parents[1]
    script = "const api=require(process.argv[1]),crypto=require('node:crypto');let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>api.verifyEnvelope(s,x=>crypto.createHash('sha256').update(x).digest('hex')).then(r=>process.stdout.write(JSON.stringify({forecast_n:r.forecast_n,correction_n:r.correction_n,diagnostics:api.signedErrorDiagnostics(r.rows)}))).catch(e=>{console.error(e);process.exitCode=1}));"
    cases = [([(pending,reviewed)],a), ([(pending,reviewed),(resolved,reviewed)],b),
             ([(pending,reviewed),(resolved,reviewed),(corrected,revised)],c)]
    means = []
    for index,(history_rows,head) in enumerate(cases):
        report = build_accountability_report([ForecastHistory(forecast,reviewed,tuple(history_rows),head['artifact_sha256'])],evidence_asof=ASOF)
        before = deepcopy(report)
        checked = subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(root/'frontend/offline/forecast-accountability/view.cjs')],
                                 input=browser_export(report),text=True,capture_output=True,timeout=10,check=False)
        assert checked.returncode == 0, checked.stderr
        viewer = json.loads(checked.stdout)
        diagnostics = signed_error_diagnostics(report['rows'])
        assert viewer['diagnostics'] == diagnostics
        assert viewer['forecast_n'] == 1 and viewer['correction_n'] == (1 if index == 2 else 0)
        cohort = diagnostics['cohorts'][0]
        assert cohort['resolved_n'] == (0 if index == 0 else 1)
        assert cohort['pending_n'] == (1 if index == 0 else 0)
        if index == 0:
            assert cohort['mean_signed_error'] is None
        else:
            expected = report['rows'][0]['forecast_point']-report['rows'][0]['actual']
            assert cohort['mean_signed_error'] == expected
            assert cohort['over_n']+cohort['under_n']+cohort['equal_n'] == 1
            means.append(expected)
        assert 'Signed price error diagnostics' in render_accountability_report(report)
        assert report == before
    assert means[0] != means[1]
    assert all(p.read_bytes() == raw for p,raw in immutable.items())
