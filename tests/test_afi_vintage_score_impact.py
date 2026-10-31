"""Immutable synthetic publisher -> original-score correction impact contracts."""
import hashlib
import json
import subprocess
from pathlib import Path

import pytest
import test_afi_log_loss as producer
from app.backtest.forecast_dataset import review_dataset
from app.backtest.forecast_report import interval_diagnostics
from test_afi_baselines import ASOF
from test_afi_dataset_integrity import encode


@pytest.mark.parametrize('case', ['up_to_down', 'down_to_up', 'both_wrong', 'unchanged_down', 'interval', 'no_probability'])
def test_producer_score_correction_contract(tmp_path, monkeypatch, case):
    original_history = producer.history
    original_publish = producer.publish_forecast
    original_fit = producer.fit
    if case in {'up_to_down', 'down_to_up', 'both_wrong', 'unchanged_down'}:
        def history():
            source = original_history()
            manifest, payload = json.loads(source.manifest_bytes), json.loads(source.payload_bytes)
            for index, row in enumerate(payload['records']):
                value = 200-index if case == 'unchanged_down' else 1+index if case == 'down_to_up' else 100+index
                if index == 38 and case in {'down_to_up', 'both_wrong'}:
                    value = .5 if case == 'down_to_up' else 80
                row.update(value=value, raw_price=value)
            raw = encode(payload)
            manifest['content_sha256'] = hashlib.sha256(raw).hexdigest()
            return review_dataset(encode(manifest), raw, asof=ASOF)
        monkeypatch.setattr(producer, 'history', history)
    if case == 'interval':
        from test_afi_uncertainty import interval
        fitted = interval()
        monkeypatch.setattr(producer, 'fit', lambda review, **kwargs: original_fit(review, method=fitted['selection']['selected_method'], **kwargs))
        monkeypatch.setattr(producer, 'publish_forecast', lambda *args, **kwargs: original_publish(*args, interval=fitted, **kwargs))
    if case == 'no_probability':
        def publish(*args, **kwargs):
            kwargs['probability_method'] = None
            return original_publish(*args, **kwargs)
        monkeypatch.setattr(producer, 'publish_forecast', publish)
    reports = producer.make_reports(tmp_path)
    raw = json.dumps(reports, sort_keys=True, separators=(',', ':')) + '\n'
    output = tmp_path / (case + '-reports.json')
    output.write_text(raw, encoding='utf8')
    root = Path(__file__).resolve().parents[1]
    fixture = root / 'tests/fixtures/afi-vintage-score-impact-v1/reports.json'
    if fixture.exists():
        assert json.loads(fixture.read_bytes())[case] == json.loads(raw)
    left, right = reports[1:]
    expected = {'case': case, 'left_brier': left['score']['cohorts'][0]['brier'], 'right_brier': right['score']['cohorts'][0]['brier']}
    if case != 'no_probability':
        x_loss = producer.loss.log_loss_diagnostics(left['rows'])['cohorts'][0]['cases'][0]
        y_loss = producer.loss.log_loss_diagnostics(right['rows'])['cohorts'][0]['cases'][0]
        expected.update(left_log_loss=x_loss['log_loss'], right_log_loss=y_loss['log_loss'])
    if case == 'interval':
        x = interval_diagnostics(left['rows'])['cohorts'][0]
        y = interval_diagnostics(right['rows'])['cohorts'][0]
        expected.update(left_covered=bool(x['covered_n']), right_covered=bool(y['covered_n']), left_score=x['mean_interval_score'], right_score=y['mean_interval_score'])
    expected_file = tmp_path / 'expected.json'
    expected_file.write_text(json.dumps(expected), encoding='utf8')
    code = """const fs=require('fs'),assert=require('assert/strict'),v=require(process.argv[1]);
const reports=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),e=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
const result=v.compareReportVintages(reports[1],reports[2]),impact=result.rows[0].score_impact,p=impact.probability;
const close=(a,b)=>assert.ok(Math.abs(a-b)<=1e-12*Math.max(1,Math.abs(b)));
assert.equal(result.union_forecast_n,1);assert.equal(result.history_ancestry_verified,false);
if(e.case==='no_probability'){assert.equal(p.state,'NO_PROBABILITY');assert.equal(p.left_log_loss_state,'NO_PROBABILITY');assert.equal(p.right_minus_left_brier,null);}
else {close(p.left_brier,e.left_brier);close(p.right_brier,e.right_brier);close(p.right_minus_left_brier,e.right_brier-e.left_brier);}
if(e.case!=='no_probability'){assert.equal(p.log_loss_difference_state,'FINITE');close(p.left_log_loss,e.left_log_loss);close(p.right_log_loss,e.right_log_loss);close(p.right_minus_left_log_loss,e.right_log_loss-e.left_log_loss);}
if(e.case==='interval'){const i=impact.interval;assert.equal(i.state,'FINITE');assert.equal(i.left_covered,e.left_covered);assert.equal(i.right_covered,e.right_covered);close(i.left_score,e.left_score);close(i.right_score,e.right_score);close(i.right_minus_left_score,e.right_score-e.left_score);}
process.stdout.write('PASS');"""
    result = subprocess.run(['C:/Program Files/nodejs/node.exe', '-e', code,
                             str(root / 'frontend/offline/forecast-accountability/view.cjs'), str(output), str(expected_file)],
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'PASS'

@pytest.mark.parametrize('case,probability,left_up,right_up,state', [
    ('positive', 1.0, True, False, 'POSITIVE_INFINITY'),
    ('negative', 1.0, False, True, 'NEGATIVE_INFINITY'),
    ('both', 1.0, False, False, 'UNDEFINED_BOTH_INFINITE'),
    ('positive_zero', 0.0, False, True, 'POSITIVE_INFINITY'),
    ('negative_zero', 0.0, True, False, 'NEGATIVE_INFINITY'),
    ('both_zero', 0.0, True, True, 'UNDEFINED_BOTH_INFINITE'),
    ('half', .5, False, True, 'FINITE'),
    ('near_half', .5000000000000001, False, True, 'UNAVAILABLE_NUMERIC_RANGE'),
    ('tiny', float.fromhex('0x0.0000000000001p-1022'), False, True, 'FINITE'),
])
def test_declared_extreme_probability_import_contract(tmp_path, case, probability, left_up, right_up, state):
    # Declared boundary packets test imports for future models. They are NOT
    # histories generated by the Laplace-smoothed production-model prototype.
    import copy
    from datetime import datetime

    from app.backtest.forecast_report import (
        _row_metrics,
        directional_diagnostics,
        paired_interval_diagnostics,
        paired_model_diagnostics,
        paired_probability_diagnostics,
    )

    reports = copy.deepcopy(producer.make_reports(tmp_path)[1:])
    code_hash = hashlib.sha256((Path(__file__).resolve().parents[1] / 'tests/fixtures/afi-vintage-score-impact-v1/declared-generator-source.txt').read_bytes()).hexdigest()
    for index, (report, up) in enumerate(zip(reports, [left_up, right_up], strict=True)):
        row = report['rows'][0]
        row.update(model='DECLARED_BOUNDARY_FIXTURE', model_version=code_hash,
                   forecast_code_sha256=code_hash, probability_up=probability,
                   actual=row['reference']+(1 if up else -1),
                   forecast_sha256=hashlib.sha256(encode({'case': case, 'fixture': 'forecast'})).hexdigest(),
                   forecast_artifact_sha256=hashlib.sha256(encode({'case': case, 'fixture': 'artifact'})).hexdigest(),
                   model_configuration_sha256=hashlib.sha256(encode({'case': case, 'fixture': 'configuration'})).hexdigest(),
                   expected_head=hashlib.sha256(encode({'case': case, 'declared_head': index})).hexdigest())
        row['score_cohort'].update(model_id=row['model'], model_version=code_hash, code_sha256=code_hash,
                                   model_configuration_sha256=row['model_configuration_sha256'])
        report['score']['cohorts'] = [{'cohort': row['score_cohort'], **_row_metrics(report['rows'])}]
        report['directional_diagnostics'] = directional_diagnostics(report['rows'])
        report['interval_diagnostics'] = interval_diagnostics(report['rows'])
        for name, function in [('model', paired_model_diagnostics), ('interval', paired_interval_diagnostics), ('probability', paired_probability_diagnostics)]:
            report['paired_'+name+'_diagnostics'] = function(report['rows'], asof=datetime.fromisoformat(report['asof']))
        report.pop('report_sha256', None)
        report['report_sha256'] = hashlib.sha256(encode(report)).hexdigest()
    packet = {'scope': 'DECLARED_SYNTHETIC_BOUNDARIES_NOT_PUBLISHER_HISTORIES', 'reports': reports}
    fixture = Path(__file__).resolve().parents[1] / 'tests/fixtures/afi-vintage-score-impact-v1/declared-boundaries.json'
    if fixture.exists():
        assert json.loads(fixture.read_bytes())[case] == json.loads(json.dumps(packet))
    output = tmp_path / (case+'-declared.json')
    output.write_text(json.dumps(packet, sort_keys=True, separators=(',', ':'))+'\n', encoding='utf8')
    code = """const fs=require('fs'),assert=require('assert/strict'),v=require(process.argv[1]);
const packet=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),p=v.compareReportVintages(...packet.reports).rows[0].score_impact.probability;
assert.equal(p.log_loss_difference_state,process.argv[3]);
if(process.argv[3]!=='FINITE')assert.equal(p.right_minus_left_log_loss,null);
if(process.argv[4]==='tiny'){assert.equal(p.state,'UNAVAILABLE_NUMERIC_RANGE');assert.equal(p.left_brier,null);assert.ok(p.right_minus_left_log_loss>700);}
if(process.argv[4]==='half')assert.equal(p.right_minus_left_log_loss,0);
process.stdout.write('PASS');"""
    result = subprocess.run(['C:/Program Files/nodejs/node.exe', '-e', code,
                             str(Path(__file__).resolve().parents[1] / 'frontend/offline/forecast-accountability/view.cjs'), str(output), state, case],
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'PASS'
