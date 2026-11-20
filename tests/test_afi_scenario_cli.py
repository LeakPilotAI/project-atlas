"""Scenario CLI uses existing engine/publication without runtime or price authority."""
import hashlib
import json
import os
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest
from app.backtest import forecast_cli as cli


def plan(tmp_path, **changes):
    value = {'schema':'AFI_ASSUMPTION_SCENARIO_REQUEST_V1','base_year':2026,'milestones':[2030,2040,2050],
             'annual_assumptions':{'bear':-.02,'base':.02,'bull':.05}}
    value.update(changes)
    path = tmp_path/'plan.json'
    path.write_text(json.dumps(value),encoding='utf-8')
    output = tmp_path/'output'
    output.mkdir()
    return path, output


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
    def handle_starttag(self, tag, attrs): self.tags.append(tag)


def test_existing_cli_publishes_repeatable_scriptless_conditional_artifacts(tmp_path,capsys):
    source,output = plan(tmp_path)
    arguments = ['scenarios','--plan',str(source),'--output-root',str(output)]
    assert cli.main(arguments) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['request_sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
    report = json.loads((output/result['report']).read_text(encoding='utf-8'))
    html = (output/result['dashboard']).read_text(encoding='utf-8')
    assert report['probabilities'] is None and report['coverage_guarantee'] is False
    assert 'not forecasts' in html and 'not an asset price' in html
    assert all(str(year) in html for year in [2030,2040,2050])
    tags = Tags(); tags.feed(html)
    assert not {'script','iframe','form','input','img','link'} & set(tags.tags)
    before = {p.name:p.read_bytes() for p in output.iterdir()}
    assert cli.main(arguments) == 0
    assert json.loads(capsys.readouterr().out) == result
    assert before == {p.name:p.read_bytes() for p in output.iterdir()}


@pytest.mark.parametrize('changes', [{'extra':True}, {'annual_assumptions':{'bear':-.9999999999999999,'base':0,'bull':.05}}])
def test_invalid_or_underflow_plan_refuses_before_any_publication(tmp_path,capsys,changes):
    source,output = plan(tmp_path,**changes)
    assert cli.main(['scenarios','--plan',str(source),'--output-root',str(output)]) == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'REFUSED'
    assert list(output.iterdir()) == []


def test_partial_publication_is_not_success_and_safe_retry_preserves_json(tmp_path,capsys,monkeypatch):
    source,output = plan(tmp_path)
    original = cli.publish_research_text
    def fail_html(*args, **kwargs):
        if kwargs['extension'] == '.html': raise OSError('synthetic private publication failure')
        return original(*args, **kwargs)
    monkeypatch.setattr(cli,'publish_research_text',fail_html)
    arguments = ['scenarios','--plan',str(source),'--output-root',str(output)]
    assert cli.main(arguments) == 2
    response = capsys.readouterr().out
    assert json.loads(response)['status'] == 'REFUSED' and 'private' not in response
    files = list(output.iterdir())
    assert len(files) == 1 and files[0].suffix == '.json'
    retained = files[0].read_bytes()
    monkeypatch.setattr(cli,'publish_research_text',original)
    assert cli.main(arguments) == 0
    assert files[0].read_bytes() == retained and len(list(output.iterdir())) == 2


@pytest.mark.parametrize('underflow', [False,True])
def test_module_command_dispatch_in_fresh_process(tmp_path,underflow):
    changes = {'annual_assumptions':{'bear':-.9999999999999999,'base':0,'bull':.05}} if underflow else {}
    source,output = plan(tmp_path,**changes)
    environment = dict(os.environ, PYTHONPATH=str(Path(cli.__file__).resolve().parents[2]))
    result = subprocess.run([sys.executable,'-m','app.backtest.forecast_cli','scenarios','--plan',str(source),
                             '--output-root',str(output)],cwd=tmp_path,env=environment,
                            capture_output=True,text=True,timeout=15,check=False)
    assert result.returncode == (2 if underflow else 0), result.stderr
    assert json.loads(result.stdout)['status'] == ('REFUSED' if underflow else 'OFFLINE_CONDITIONAL_SCENARIOS_COMPLETE')


def test_actual_scenario_artifact_is_refused_by_accountability_viewer(tmp_path):
    source,output = plan(tmp_path)
    result = cli.run_scenarios(plan_path=source,output_root=output)
    raw = (output/result['report']).read_text(encoding='utf-8')
    viewer = Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    script = "const api=require(process.argv[1]);let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>api.verifyEnvelope(s).then(()=>{process.exitCode=9}).catch(e=>process.stdout.write(JSON.stringify({status:'REFUSED',message:e.message}))));"
    checked = subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(viewer)],input=raw,
                             text=True,capture_output=True,timeout=15,check=False)
    assert checked.returncode == 0, checked.stderr
    refusal = json.loads(checked.stdout)
    assert refusal['status'] == 'REFUSED'
    assert 'separately generated scenario HTML' in refusal['message']
    assert 'not established' in refusal['message']
