"""Actual immutable synthetic outcomes through the browser vintage comparator."""
import json
import subprocess
from pathlib import Path

from test_afi_log_loss import make_reports


def test_actual_pending_resolved_corrected_reports_compare_without_extra_samples(tmp_path):
    reports = make_reports(tmp_path)
    payload = json.dumps(reports, sort_keys=True, separators=(',', ':')) + '\n'
    file = tmp_path / 'producer-vintages.json'
    file.write_text(payload, encoding='utf8')
    root = Path(__file__).resolve().parents[1]
    fixture = root / 'tests/fixtures/afi-report-vintages-v1/reports.json'
    if fixture.exists():
        assert fixture.read_text(encoding='utf8') == payload
    code = """const fs=require('fs'),assert=require('assert/strict'),v=require(process.argv[1]);
const [pending,resolved,corrected]=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const a=v.compareReportVintages(pending,resolved),b=v.compareReportVintages(resolved,corrected);
assert.equal(a.union_forecast_n,1);assert.equal(a.status_counts.RESOLUTION_REPORTED,1);
assert.equal(b.union_forecast_n,1);assert.equal(b.status_counts.OUTCOME_VALUE_CHANGED,1);
assert.equal(b.rows[0].right_actual,90);assert.equal(b.rows[0].metric_state,'FINITE');
assert.equal(b.rows[0].right_minus_left_absolute_error,Math.abs(corrected.rows[0].forecast_point-90)-Math.abs(resolved.rows[0].forecast_point-resolved.rows[0].actual));
assert.equal(b.history_ancestry_verified,false);assert.equal(b.production_approved,false);
process.stdout.write('PASS');"""
    result = subprocess.run(['C:/Program Files/nodejs/node.exe', '-e', code,
                             str(root / 'frontend/offline/forecast-accountability/view.cjs'), str(file)],
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'PASS'
