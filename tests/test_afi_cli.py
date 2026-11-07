import json
import os
import subprocess
import sys

import pytest
from app.backtest import forecast_cli
from test_afi_baselines import ASOF, ASSET, history


def inputs(tmp_path):
    r=history();manifest=tmp_path/'manifest.json';records=tmp_path/'records.json';out=tmp_path/'outputs';out.mkdir()
    manifest.write_bytes(r.manifest_bytes);records.write_bytes(r.payload_bytes)
    return manifest,records,out


def args(paths):
    m,r,o=paths
    return ['--manifest',str(m),'--records',str(r),'--output-root',str(o),'--asset',ASSET,
            '--issued-at','2026-10-01T00:01:00+00:00','--asof',ASOF.isoformat(),'--lookback','5']


def test_cli_native_process_publishes_reproducible_offline_outputs(tmp_path):
    paths=inputs(tmp_path);command=[sys.executable,'-m','app.backtest.forecast_cli',*args(paths)]
    a=subprocess.run(command,capture_output=True,text=True,timeout=15,env=os.environ.copy(),check=False)
    assert a.returncode==0,a.stderr
    report=json.loads(a.stdout);assert report['status']=='OFFLINE_SYNTHETIC_COMPLETE'
    outputs={p.name:p.read_bytes() for p in paths[2].iterdir()}
    b=subprocess.run(command,capture_output=True,text=True,timeout=15,env=os.environ.copy(),check=False)
    assert b.returncode==0 and json.loads(b.stdout)==report
    assert {p.name:p.read_bytes() for p in paths[2].iterdir()}==outputs
    html=(paths[2]/report['dashboard']).read_text(encoding='utf-8')
    assert 'synthetic fixtures only' in html and '<script' not in html


@pytest.mark.parametrize('failure',['missing','malformed','historical','naive','bad-root'])
def test_cli_refusal_never_reports_complete(tmp_path,capsys,failure):
    paths=inputs(tmp_path);argv=args(paths)
    if failure=='missing':paths[0].unlink()
    if failure=='malformed':paths[1].write_bytes(b'{bad')
    if failure=='historical':
        m=json.loads(paths[0].read_bytes());m['evidence_class']='HISTORICAL';m['source']['permission_status']='DECLARED'
        paths[0].write_text(json.dumps(m),encoding='utf-8')
    if failure=='naive':argv[argv.index('--issued-at')+1]='2026-10-01T00:01:00'
    if failure=='bad-root':argv[argv.index('--output-root')+1]=str(tmp_path/'unprovisioned')
    assert forecast_cli.main(argv)==2
    result=json.loads(capsys.readouterr().out)
    assert result['status']=='REFUSED' and not result['production_approved']


def test_partial_cli_failure_preserves_committed_forecast(tmp_path,monkeypatch,capsys):
    paths=inputs(tmp_path)
    def fail(*args,**kwargs):raise OSError('synthetic disk full')
    monkeypatch.setattr(forecast_cli,'publish_research_text',fail)
    assert forecast_cli.main(args(paths))==2
    assert json.loads(capsys.readouterr().out)['status']=='REFUSED'
    assert len(list(paths[2].glob('*.json')))==1 and not list(paths[2].glob('*.html'))
