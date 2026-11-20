"""Actual source-reproduced exports retain microsecond plans in browser verification."""
import json
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest
from test_research_replay import inputs
from test_research_replay_export import run, setup, verify

from scripts.observation_runtime.research_comparison import (
    browser_comparison,
    compare_exports,
)
from scripts.observation_runtime.research_replay import encoded


@pytest.mark.parametrize('scenario',['descriptive','refused','ttl','millisecond-boundary'])
def test_actual_fractional_replay_and_source_verified_comparison(tmp_path,scenario):
    request,output=setup(tmp_path)
    _,_,original=inputs()
    if scenario=='refused':
        first=original[0]+timedelta(microseconds=1)
        clocks=[first,first+timedelta(microseconds=1)]
        expected=['REFUSED','REFUSED']
    elif scenario=='ttl':
        first=original[1].replace(minute=35,second=0)
        clocks=[first,first+timedelta(microseconds=1)]
        expected=['DESCRIPTIVE_RESEARCH_ONLY','REFUSED']
    elif scenario=='millisecond-boundary':
        clocks=[original[1]+timedelta(microseconds=n) for n in [999,1000]]
        expected=['DESCRIPTIVE_RESEARCH_ONLY']*2
    else:
        clocks=[original[1]+timedelta(microseconds=n) for n in [1,2]]
        expected=['DESCRIPTIVE_RESEARCH_ONLY']*2
    request['decisions']=[clock.isoformat() for clock in clocks]
    (tmp_path/'request.json').write_bytes(encoded(request))
    result=run(tmp_path,output)
    assert result['planned_decision_n']==2
    assert verify(output,result)['status']=='OFFLINE_REPLAY_VERIFIED'
    manifest=json.loads((output/result['manifest']).read_bytes())
    report=json.loads((output/manifest['report']).read_bytes())
    assert [row['status'] for row in report['cases']]==expected
    assert [row['decision_at'] for row in report['cases']]==request['decisions']
    before={p.name:p.read_bytes() for p in output.iterdir()}
    compared=compare_exports(left_root=output,left_manifest=result['manifest'],left_pin=result['manifest'][:-5],
        right_root=output,right_manifest=result['manifest'],right_pin=result['manifest'][:-5])
    assert compared['planned_pair_n']==2 and compared['same_evidence_n']==2
    assert compared['source_authenticated'] is False and compared['predictive_skill_established'] is False
    assert before=={p.name:p.read_bytes() for p in output.iterdir()}
    comparison=tmp_path/'comparison.json'
    comparison.write_text(browser_comparison(compared),encoding='utf-8')
    view=Path(__file__).resolve().parents[1]/'frontend/offline/market-replay/view.cjs'
    code="const fs=require('node:fs');const a=require(process.argv[1]);(async()=>{const r=await a.verifyResearchReplay(fs.readFileSync(process.argv[2],'utf8'));const c=await a.verifyResearchComparison(fs.readFileSync(process.argv[3],'utf8'));if(r.planned_decision_n!==2||c.planned_pair_n!==2||c.same_evidence_n!==2||r.source_authenticated!==false)throw Error('scope');})().catch(e=>{console.error(e);process.exitCode=1;});"
    execution=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',code,str(view),str(output/result['browser_export']),str(comparison)],capture_output=True,text=True,timeout=20,check=False)
    assert execution.returncode==0,execution.stdout+execution.stderr
