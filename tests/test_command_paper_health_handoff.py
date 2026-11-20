"""Actual diagnostic API output to actual health renderer, fully synthetic inputs."""
import asyncio
import json
import subprocess
from pathlib import Path

import app.api.diagnostics as api
import app.services.paper_reconciliation_alert as reconciliation
import app.services.perp_alert_delivery as delivery
import app.services.perp_manual_service as manual
import app.services.perp_paper_observability as observability
import app.services.perp_setup_paper_mirror as mirror
import pytest


@pytest.mark.parametrize('reconciled',[True,False])
def test_diagnostic_api_handoff_keeps_direct_and_background_outcomes_distinct(monkeypatch,reconciled):
    service = delivery.PerpAlertDeliveryService()
    monkeypatch.setattr(delivery,'perp_alert_delivery_service',service)
    monkeypatch.setattr(manual.perp_manual_service,'snapshot',lambda:{'setups':[],'markets':[]})
    async def failed(*_args,**_kwargs):raise OSError('synthetic private evidence')
    monkeypatch.setattr(mirror.perp_setup_paper_mirror,'sync',failed)
    monkeypatch.setattr(reconciliation,'alert_reconciliation_if_needed',failed)
    monkeypatch.setattr(observability,'reconciliation_summary',lambda:{'reconciliation_ok':reconciled})
    async def response():
        with pytest.raises(OSError):await service.paper_once()
        await service._run_reconciliation()
        return await api.diagnostics_paper_reconciliation()
    payload = asyncio.run(response())
    assert payload['read_only'] is True and payload['live_capital_allowed'] is False
    assert payload['runtime']['paper_review']['state'] == 'FAILED'
    assert payload['runtime']['reconciliation_review']['state'] == 'FAILED'
    root = Path(__file__).resolve().parents[1]
    script = """const {page,payloads}=await import(process.argv[1]);let data='';
for await(const part of process.stdin)data+=part;
const inputs=payloads();inputs['/diagnostics/paper-reconciliation']=JSON.parse(data);
const p=page();p.set(inputs);await p.load();
process.stdout.write(JSON.stringify({reconciliation:p.node('hRecon').textContent,findings:p.node('findings').innerHTML}));"""
    result = subprocess.run(['C:/Program Files/nodejs/node.exe','--input-type=module','-e',script,
                             (root/'tests/command_center_health_fixture.mjs').as_uri()],
                            input=json.dumps(payload),text=True,encoding='utf-8',capture_output=True,timeout=10,check=False)
    assert result.returncode == 0, result.stderr
    shown = json.loads(result.stdout)
    assert shown['reconciliation'] == ('OK' if reconciled else 'REVIEW')
    assert 'LAST PAPER REVIEW FAILED' in shown['findings']
    assert 'LAST BACKGROUND RECONCILIATION FAILED' in shown['findings']
    assert 'NO CURRENT HEALTH FINDINGS' not in shown['findings']
    assert 'private' not in shown['findings']
