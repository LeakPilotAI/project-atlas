"""Descriptive target support parity, never independent sample evidence."""
import json
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest
from app.backtest.forecast_report import interval_target_support
from test_afi_interval_accountability import interval_row


def rows(case):
    first = interval_row(target_at='2026-10-02T00:00:00Z')
    second = deepcopy(first)
    if case == 'distinct': second['target_at'] = '2026-10-03T00:00:00Z'
    if case == 'offset': second['target_at'] = '2026-10-01T19:00:00-05:00'
    if case == 'missing': second.pop('target_at')
    if case == 'naive': second['target_at'] = '2026-10-02T00:00:00'
    if case == 'pending': second.update(status='FORECAST_ONLY',actual=None)
    if case == 'level': second['interval']['level'] = .9
    if case == 'precision': second['target_at'] = '2026-10-02T00:00:00.000001Z'
    invalid = {'calendar': '2026-02-30T00:00:00Z', 'precision7': '2026-10-02T00:00:00.0000001Z',
               'year': '2201-01-01T00:00:00Z', 'bad_offset': '2026-10-02T00:00:00+00:99', 'boolean': True}
    if case in invalid: second['target_at'] = invalid[case]
    if case == 'reverse_level':
        first['interval']['level'] = .9
    return [first, second]


@pytest.mark.parametrize('case', ['distinct','repeated','offset','missing','naive','pending','level','precision','calendar','precision7','year','bad_offset','boolean','reverse_level'])
def test_python_browser_target_support_parity(case):
    data = rows(case)
    original = deepcopy(data)
    result = interval_target_support(data)
    root = Path(__file__).resolve().parents[1]
    script = "const api=require(process.argv[1]);let text='';process.stdin.on('data',x=>text+=x);process.stdin.on('end',()=>process.stdout.write(JSON.stringify(api.intervalTargetSupport(JSON.parse(text)))));"
    q = subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,
                        str(root/'frontend/offline/forecast-accountability/view.cjs')],
                       input=json.dumps(data),capture_output=True,text=True,timeout=10,check=False)
    assert q.returncode == 0, q.stderr
    assert result == json.loads(q.stdout)
    assert data == original
    assert result['independent_samples_established'] is False
    assert result['calibration_established'] is False
    if case in ('repeated','offset'):
        assert result['cohorts'][0]['repeated_target_n'] == 1
    if case in ('missing','naive'):
        assert result['cohorts'][0]['missing_target_n'] == 1
