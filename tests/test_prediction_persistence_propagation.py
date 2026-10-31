"""Only temporary journals and fake providers/owned synthetic asyncio tasks."""
import asyncio
import builtins
from datetime import datetime, timezone
from types import SimpleNamespace

import app.prediction.paper_engine as engine
import app.prediction.prediction_paper_automation as automation
import pytest
from app.core.shutdown import ShutdownReport
from app.prediction.paper_engine import PredictionPaperPersistenceError
from test_prediction_paper_automation import _book, _journal, _market, _open

NOW=datetime(2026,10,2,12,tzinfo=timezone.utc)


def setup(tmp_path,monkeypatch):
    j=_journal(tmp_path);service=automation.PredictionPaperAutomation()
    monkeypatch.setattr(automation,'prediction_paper_journal',j)
    monkeypatch.setattr(automation,'get_subscriber_ids',list)
    monkeypatch.setattr(automation,'is_discord_ready',lambda:False)
    return j,service


def fail_write(j,path,monkeypatch):
    original=engine.write_flushed;error=OSError('synthetic required write failure')
    def write(handle,value):
        if str(handle.name)==str(path):raise error
        original(handle,value)
    with monkeypatch.context() as m:
        m.setattr(engine,'write_flushed',write)
        with pytest.raises(OSError):j._append(path,{'event':'synthetic'})
    return error


def test_unknown_ledger_intent_blocks_before_any_provider_request(tmp_path,monkeypatch):
    j,service=setup(tmp_path,monkeypatch);j.journal_path.with_name(j.journal_path.name+'.append-intent').write_bytes(b'uncertain')
    async def provider(*args,**kwargs):raise AssertionError('provider must not be called')
    monkeypatch.setattr(automation.kalshi_public,'get_orderbook',provider)
    with pytest.raises(PredictionPaperPersistenceError):asyncio.run(service.run_auto_flat_once(now=NOW))
    status=service.status();assert status['persistence']['lanes']['auto_flat']=='BLOCKED'
    assert status['auto_flat']['blocked'] and status['unattended_paper_open_enabled'] is False


def test_candidate_failure_does_not_disable_healthy_ledger_management(tmp_path,monkeypatch):
    j,service=setup(tmp_path,monkeypatch);_open(j,NOW);error=fail_write(j,j.candidate_path,monkeypatch)
    with pytest.raises(OSError) as actual:asyncio.run(service.run_scan_once(now=NOW))
    assert actual.value is error
    async def book(*args,**kwargs):return {'orderbook':_book()}
    monkeypatch.setattr(automation.kalshi_public,'get_orderbook',book)
    state=asyncio.run(service.run_auto_flat_once(now=NOW))
    assert state['last_action']=='AUTO_FLAT_EXECUTED' and j.snapshot()['summary']['closed_trades']==1
    assert service.status()['persistence']['lanes']=={'scanner':'BLOCKED','auto_flat':'NO_KNOWN_FAILURE'}
    assert service.config.flat_interval_seconds==5 and service.config.scan_interval_seconds==60


def test_scanner_write_failure_is_not_last_success_and_does_not_retry_provider(tmp_path,monkeypatch):
    j,service=setup(tmp_path,monkeypatch);calls=[];original=engine.write_flushed;error=OSError('synthetic candidate fsync')
    async def markets(**kwargs):calls.append('metadata');return {'markets':[_market(NOW,volume='1',oi='1')]}
    def write(handle,value):
        if str(handle.name)==str(j.candidate_path):raise error
        original(handle,value)
    monkeypatch.setattr(automation.kalshi_public,'get_markets',markets)
    with monkeypatch.context() as m:
        m.setattr(engine,'write_flushed',write)
        with pytest.raises(OSError) as actual:asyncio.run(service.run_scan_once(now=NOW))
    assert actual.value is error
    status=service.status();assert status['last_successful_scan'] is None
    assert status['scanner']['last_error']=='OSError' and status['scanner']['persistence_state']=='BLOCKED'
    with pytest.raises(OSError):asyncio.run(service.run_scan_once(now=NOW))
    assert calls==['metadata']


@pytest.mark.parametrize('error',[TimeoutError('synthetic provider timeout'),ConnectionError('synthetic provider disconnect')])
def test_provider_failure_is_not_misclassified_as_storage_failure(tmp_path,monkeypatch,error):
    j,service=setup(tmp_path,monkeypatch);_open(j,NOW)
    async def provider(*args,**kwargs):raise error
    monkeypatch.setattr(automation.kalshi_public,'get_orderbook',provider)
    state=asyncio.run(service.run_auto_flat_once(now=NOW));assert state['blocked']
    assert service.status()['persistence']['lanes']=={'scanner':'NO_KNOWN_FAILURE','auto_flat':'NO_KNOWN_FAILURE'}
    asyncio.run(service.stop())


def test_persistence_failure_reaches_bounded_shutdown_and_repeated_stop(tmp_path,monkeypatch):
    j,service=setup(tmp_path,monkeypatch);error=fail_write(j,j.journal_path,monkeypatch)
    async def scenario():
        report=ShutdownReport(timeout=1)
        async def independent():return None
        await report.run('independent',independent)
        with pytest.raises(builtins.ExceptionGroup) as group:await report.run('prediction',service.stop)
        assert error in group.value.exceptions
        with pytest.raises(builtins.ExceptionGroup):report.finish(SimpleNamespace(info=lambda *a,**k:None,error=lambda *a,**k:None))
        assert report.outcome=='INCOMPLETE'
        with pytest.raises(builtins.ExceptionGroup) as repeated:await service.stop()
        assert error in repeated.value.exceptions
    asyncio.run(scenario())


def test_owned_worker_does_not_swallow_persistent_ledger_failure(tmp_path,monkeypatch):
    j,service=setup(tmp_path,monkeypatch);error=fail_write(j,j.journal_path,monkeypatch)
    async def scenario():
        service.running=True;service._flat_task=asyncio.create_task(service._flat_loop())
        with pytest.raises(OSError) as observed:await service._flat_task
        assert observed.value is error
        with pytest.raises(builtins.ExceptionGroup) as stopped:await service.stop()
        assert error in stopped.value.exceptions
    asyncio.run(scenario())


def test_known_failure_is_not_hidden_by_later_invalid_record(tmp_path,monkeypatch):
    j,_=setup(tmp_path,monkeypatch);error=fail_write(j,j.journal_path,monkeypatch)
    with pytest.raises(OSError) as actual:j.log_event({'event':'synthetic','bad':float('nan')})
    assert actual.value is error
