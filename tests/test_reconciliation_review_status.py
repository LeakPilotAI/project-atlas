"""Fake reconciliation scans only; never sends or starts a service loop."""
import asyncio

import app.services.paper_reconciliation_alert as reconciliation
import app.services.perp_alert_delivery as delivery
import pytest


def test_not_run_cannot_report_reconciliation_ok():
    service = delivery.PerpAlertDeliveryService()
    status = service.reconciliation_status()
    assert status['last_result'] == {}


def test_failed_scan_does_not_retain_previous_ok(monkeypatch):
    service = delivery.PerpAlertDeliveryService()
    service.last_reconciliation_result = {'reconciliation_ok':True,'attempted':0}
    async def failed():raise OSError('synthetic private reconciliation path')
    monkeypatch.setattr(reconciliation,'alert_reconciliation_if_needed',failed)
    asyncio.run(service._run_reconciliation())
    status = service.reconciliation_status()
    assert status['last_result'] == {}
    assert status['reconciliation_review']['state'] == 'FAILED'
    assert status['reconciliation_review']['error_class'] == 'OSError'
    assert 'private' not in str(status)


@pytest.mark.parametrize('value',[None,False,[],{}, {'reconciliation_ok':1}, {'reconciliation_ok':'true'}])
def test_invalid_reconciliation_acknowledgement_is_failed(monkeypatch,value):
    service = delivery.PerpAlertDeliveryService()
    async def invalid():return value
    monkeypatch.setattr(reconciliation,'alert_reconciliation_if_needed',invalid)
    asyncio.run(service._run_reconciliation())
    status = service.reconciliation_status()
    assert status['last_result'] == {}
    assert status['reconciliation_review']['state'] == 'FAILED'
    assert status['reconciliation_review']['error_class'] == 'TypeError'


def test_success_then_interruption_preserves_only_explicit_history(monkeypatch):
    service = delivery.PerpAlertDeliveryService()
    result = {'reconciliation_ok':False,'attempted':1}
    async def success():
        assert service.reconciliation_status()['reconciliation_review']['state'] == 'IN_PROGRESS'
        assert service.reconciliation_status()['last_result'] == {}
        return result
    monkeypatch.setattr(reconciliation,'alert_reconciliation_if_needed',success)
    asyncio.run(service._run_reconciliation())
    status = service.reconciliation_status()
    assert status['reconciliation_review']['state'] == 'COMPLETE'
    assert status['last_result']['reconciliation_ok'] is False
    status['last_result']['reconciliation_ok'] = True
    assert service.last_reconciliation_result['reconciliation_ok'] is False
    original = asyncio.CancelledError('synthetic private cancellation')
    async def interrupted():raise original
    monkeypatch.setattr(reconciliation,'alert_reconciliation_if_needed',interrupted)
    with pytest.raises(asyncio.CancelledError) as caught:asyncio.run(service._run_reconciliation())
    assert caught.value is original
    status = service.reconciliation_status()
    assert status['last_result'] == {}
    assert status['reconciliation_review']['state'] == 'INTERRUPTED'
    assert status['reconciliation_review']['last_successful_result'] == result
    assert status['reconciliation_review']['last_successful_at']
    assert status['reconciliation_review']['finished_at']
    assert 'private' not in str(status)
