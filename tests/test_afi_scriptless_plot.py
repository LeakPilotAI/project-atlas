"""Scriptless display of original synthetic cases, never forecast skill."""
import json
import math
import re
from copy import deepcopy
from pathlib import Path

import pytest
from app.backtest.forecast_report import (
    _render_case_plots,
    render_accountability_report,
)

FIXTURES=json.loads((Path(__file__).parent/'fixtures/afi-vintage-score-impact-v1/reports.json').read_text(encoding='utf-8'))

@pytest.mark.parametrize('index',[0,1,2])
def test_scriptless_actual_publisher_history(index):
    report=deepcopy(FIXTURES['interval'][index]);before=deepcopy(report)
    html=render_accountability_report(report)
    assert '<script' not in html and '<svg ' in html and '<details>' in html
    assert 'Exact plotted cases' in html and 'scope="col"' in html
    assert html.count('<circle ')==1 and html.count('<rect ')==int(index>0)
    assert html.count('<line ')==3
    assert report['rows'][0]['forecast_sha256'] in html
    assert report==before

@pytest.mark.parametrize('key,value',[
 ('asset_id','CRYPTO:ETH-USD'),('horizon','5D'),('model_version','other'),
 ('forecast_dataset_sha256','a'*64),('forecast_code_sha256','b'*64),
 ('model_configuration_sha256','c'*64),('input_source_id','other')])
def test_plot_cohorts_remain_separate(key,value):
    a=deepcopy(FIXTURES['interval'][1]['rows'][0]);b=dict(a,forecast_sha256='f'*64)
    b[key]=value
    html=_render_case_plots([a,b])
    assert html.count('<details>')==2 and html.count('<svg ')==2


def test_empty_legacy_duplicates_and_malformed_refuse_or_disclose():
    assert 'No visible cases' in _render_case_plots([])
    row=deepcopy(FIXTURES['interval'][1]['rows'][0])
    del row['model_version'];del row['lookback']
    assert '<svg ' not in _render_case_plots([row])
    assert '1 cases lack' in _render_case_plots([row])
    with pytest.raises(ValueError):_render_case_plots([row,row])
    with pytest.raises(ValueError):_render_case_plots([dict(row,actual=float('nan'))])
    with pytest.raises(ValueError):_render_case_plots([dict(row,interval={'lower':120,'upper':100,'level':.8})])


def test_plot_escapes_receipt_text_and_keeps_finite_geometry():
    row=deepcopy(FIXTURES['interval'][1]['rows'][0]);row['input_source_id']='<script>bad</script>'
    row['interval']=None;row['forecast_point']=1.7e308;row['actual']=5e-324
    html=_render_case_plots([row]);assert '<script>' not in html and '&lt;script&gt;' in html
    assert all(math.isfinite(float(v)) for v in re.findall(r'(?:cx|cy|x1|x2|y1|y2)="([^"]+)"',html))
    assert re.search(r'<circle cx="880.0"',html)
    row['actual']=row['forecast_point'];assert '<circle cx="570.0"' in _render_case_plots([row])

def test_browser_and_scriptless_plots_partition_same_publisher_cases():
    import subprocess
    rows=[deepcopy(reports[1]['rows'][0]) for reports in FIXTURES.values()]
    # Several producer fixtures deliberately reuse identities; select unique originals.
    rows=list({row['forecast_sha256']:row for row in rows}.values())
    script="const v=require(process.argv[1]);let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>{const rows=JSON.parse(s),m=v.forecastPlot(rows);console.log(JSON.stringify({cohorts:m.cohorts.length,points:m.cohorts.reduce((n,c)=>n+v.forecastPlot(rows,c.id).points.length,0)}))});"
    result=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs')],input=json.dumps(rows),capture_output=True,text=True,check=True,timeout=10)
    model=json.loads(result.stdout);html=_render_case_plots(rows)
    assert html.count('<details>')==model['cohorts']
    assert html.count('<circle ')==model['points']==len(rows)
