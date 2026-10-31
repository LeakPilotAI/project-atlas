"""Synthetic review status only; no service loop, provider or Discord sender."""
import asyncio
import json
import subprocess
from pathlib import Path

import app
import app.services.perp_alert_delivery as delivery
import app.services.perp_manual_service as manual
import app.services.perp_setup_paper_mirror as mirror
import pytest


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(manual.perp_manual_service, "snapshot", lambda:{"setups":[], "markets":[]})
    return delivery.PerpAlertDeliveryService()


def test_failed_review_never_reuses_last_successful_counts(service, monkeypatch):
    counts = {"opened":1,"closed":0,"marked":1,"skipped":0}
    async def success(*_args, **_kwargs):return counts
    monkeypatch.setattr(mirror.perp_setup_paper_mirror,"sync",success)
    assert asyncio.run(service.paper_once()) == counts
    original = OSError("synthetic private storage failure")
    async def failed(*_args, **_kwargs):raise original
    monkeypatch.setattr(mirror.perp_setup_paper_mirror,"sync",failed)
    with pytest.raises(OSError) as caught:asyncio.run(service.paper_once())
    assert caught.value is original
    assert service.last_paper_result == {}
    status = service.paper_review_status()
    assert status['state'] == 'FAILED' and status['counts'] is None
    assert status['last_successful_counts'] == counts
    assert status['error_class'] == 'OSError'
    assert 'private' not in str(status)


@pytest.mark.parametrize('failure',[asyncio.CancelledError('synthetic'),ValueError('synthetic')])
def test_interrupted_or_failed_review_is_not_complete(service,monkeypatch,failure):
    async def failed(*_args, **_kwargs):raise failure
    monkeypatch.setattr(mirror.perp_setup_paper_mirror,'sync',failed)
    with pytest.raises(type(failure)):asyncio.run(service.paper_once())
    status = service.paper_review_status()
    assert status['state'] == ('INTERRUPTED' if isinstance(failure,asyncio.CancelledError) else 'FAILED')
    assert status['counts'] is None


def test_not_run_and_success_are_explicit_and_status_copies_counts(service,monkeypatch):
    assert service.paper_review_status()['state'] == 'NOT_RUN'
    assert service.paper_review_status()['counts'] is None
    async def success(*_args, **_kwargs):
        assert service.paper_review_status()['state'] == 'IN_PROGRESS'
        assert service.paper_review_status()['counts'] is None
        assert service.paper_review_status()['finished_at'] is None
        return {'marked':2}
    monkeypatch.setattr(mirror.perp_setup_paper_mirror,'sync',success)
    asyncio.run(service.paper_once())
    status = service.paper_review_status()
    assert status['state'] == 'COMPLETE' and status['counts'] == {'marked':2}
    assert status['finished_at'] and status['last_successful_at']
    status['counts']['marked'] = 100
    assert service.paper_review_status()['counts'] == {'marked':2}


def test_snapshot_failure_and_invalid_result_never_acknowledge(service,monkeypatch):
    def failed():raise ValueError('synthetic snapshot')
    monkeypatch.setattr(manual.perp_manual_service,'snapshot',failed)
    with pytest.raises(ValueError):asyncio.run(service.paper_once())
    assert service.paper_review_status()['state'] == 'FAILED'
    monkeypatch.setattr(manual.perp_manual_service,'snapshot',dict)
    async def invalid(*_args, **_kwargs):return None
    monkeypatch.setattr(mirror.perp_setup_paper_mirror,'sync',invalid)
    with pytest.raises(TypeError):asyncio.run(service.paper_once())
    assert service.paper_review_status()['counts'] is None


def test_discord_result_cannot_clear_paper_failure(service,monkeypatch):
    async def failed(*_args, **_kwargs):raise OSError('synthetic')
    async def no_delivery(*_args, **_kwargs):return {'attempted':0,'delivered':0,'acknowledged':0,'failed':0}
    monkeypatch.setattr(mirror.perp_setup_paper_mirror,'sync',failed)
    monkeypatch.setattr(delivery,'deliver_alert_candidates',no_delivery)
    with pytest.raises(OSError):asyncio.run(service.paper_once())
    asyncio.run(service.deliver_once())
    assert service.last_error is None
    assert service.paper_review_status()['state'] == 'FAILED'
    assert service.reconciliation_status()['paper_review']['state'] == 'FAILED'


def test_actual_api_to_dashboard_hint_reports_failure_without_stale_success(service,monkeypatch):
    import app.api.perp_manual as api
    async def failed(*_args, **_kwargs):raise OSError('synthetic private path')
    monkeypatch.setattr(mirror.perp_setup_paper_mirror,'sync',failed)
    with pytest.raises(OSError):asyncio.run(service.paper_once())
    monkeypatch.setattr(api,'perp_alert_delivery_service',service)
    monkeypatch.setattr(api.perp_setup_paper_mirror,'status',lambda:{'opened_total':5,'closed_total':2})
    monkeypatch.setattr(api,'build_paper_observability',lambda *_:{})
    response = asyncio.run(api.manual_perps())['auto_paper']
    assert response['last_pass'] == {}
    assert response['review']['state'] == 'FAILED'
    html = Path(app.__file__).resolve().parent/'static/dashboard_shell.html'
    script = """const fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync(process.argv[1],'utf8'),start=html.indexOf('function paperReviewHint(ap){'),end=html.indexOf('async function loadPerps()',start);
if(start<0||end<start)throw Error('Missing actual dashboard hint');
const hint=vm.runInNewContext(html.slice(start,end)+';paperReviewHint',{});
let data='';process.stdin.on('data',x=>data+=x);process.stdin.on('end',()=>process.stdout.write(JSON.stringify([hint(JSON.parse(data)),hint({}),hint({review:{state:'COMPLETE'},opened_total:5,closed_total:2})])));"""
    result = subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(html)],
                            input=json.dumps(response),capture_output=True,text=True,encoding="utf-8",timeout=10,check=False)
    assert result.returncode == 0, result.stderr
    failed,unknown,complete = json.loads(result.stdout)
    assert 'failed' in failed and 'results unavailable' in failed
    assert 'opened 5' not in failed and 'private' not in failed
    assert 'unknown' in unknown and 'last review complete' in complete


def test_dependency_import_failure_also_invalidates_current_result(service,monkeypatch):
    import builtins
    original = builtins.__import__
    def unavailable(name,*args,**kwargs):
        if name == 'app.services.perp_setup_paper_mirror':
            raise ImportError('synthetic private dependency path')
        return original(name,*args,**kwargs)
    service.last_paper_result = {'marked':10}
    monkeypatch.setattr(builtins,'__import__',unavailable)
    with pytest.raises(ImportError):asyncio.run(service.paper_once())
    assert service.last_paper_result == {}
    assert service.paper_review_status()['state'] == 'FAILED'
    assert service.paper_review_status()['error_class'] == 'ImportError'
