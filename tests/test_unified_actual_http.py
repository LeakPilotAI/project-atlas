"""Real loopback + shipped Windows Stop action; actual two native financial lanes.

All market, session and custody authority is explicitly synthetic. No enrollment.
"""
import asyncio
import hashlib
import importlib.util
import json
import os
import socket
import subprocess
import threading
import uuid
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
import test_unified_actual_native_lanes as native_fixtures
from app.services.unified_paper_runtime import (
    UnifiedControlStopBridge,
    UnifiedMarketReadCapability,
)
from test_quality_dips_operational_read_service import request
from test_unified_actual_native_lanes import cycle

system = native_fixtures.system

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('actual_two_read_host', REPO / 'scripts/observation_runtime/quality_dips_read_service.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def capture(s):
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for root in (s.root, s.qd_root) for p in root.rglob('*') if p.is_file()}


def host(s):
    reader = s.s.runtime.runtime.readonly()
    bridge = UnifiedControlStopBridge(s.r)
    process = m.observe_self()
    account = s.s.runtime.runtime.reader.enrollment['account_id']
    epoch = s.q.writer.manifest['epoch']
    c = SimpleNamespace(account=account, epoch=epoch, clock=s.clock, identity=process, observer=m.observe_self,
        host_id=uuid.uuid4().hex, host_claim_lock=threading.Lock(), host_claimed=False,
        read_committed=reader.read_committed, verify=reader.verify)
    def admitted(action):
        if m.observe_self() != process or not s.a.valid: raise ValueError('SYNTHETIC_ACCEPTANCE_REVOKED')
        return action()
    c.admitted = admitted
    c.preflight = lambda: admitted(lambda: reader.read_committed(account, epoch))
    c.verify_control_bridge = lambda candidate: admitted(lambda: candidate is bridge and bridge.verify_session())
    token = uuid.uuid4().hex
    h = m.OwnedReadHost(c, market_reader=s.q.f, unified_reader=UnifiedMarketReadCapability(s.r),
        control_bridge=bridge, control_token=token)
    return h, token


def test_two_real_native_accounts_http_and_shipped_control_center(system):
    s = system
    asyncio.run(cycle(s))
    h, token = host(s)
    ready = h.start()
    port = urlsplit(ready['url']).port
    try:
        before = capture(s)
        code, raw, _ = request(ready, m.SELECTED)
        assert code == 200
        view = json.loads(raw)
        assert view['status'] == 'ACKNOWLEDGED', view
        accounts = view['multi_market']['accounts']
        assert accounts['state'] == 'ACKNOWLEDGED', accounts
        assert accounts['accounts']['QUALITY_DIPS']['currency'] == 'USD'
        assert accounts['accounts']['HYPERLIQUID']['currency'] == 'USDC'
        assert accounts['accounts']['QUALITY_DIPS']['cash'] == '899.96'
        assert accounts['accounts']['HYPERLIQUID']['cash'] == '1000'
        assert accounts['accounts']['HYPERLIQUID']['resting_orders']
        assert accounts['accounts']['HYPERLIQUID']['available_cash'] is None
        assert accounts['total_cash'] is None and accounts['total_equity'] is None
        assert request(ready, '/api/investments/quality-dips')[0] == 404
        assert request(ready, m.SELECTED + '/commands', 'POST')[0] == 403
        assert request(ready, m.SELECTED, headers={'Host': 'foreign.invalid'})[0] == 403
        assert request(ready, '/quality_dips.html?mode=selected-paper')[0] == 200
        assert capture(s) == before  # Genuine HTTP GETs do not create latches, pins, reports or fills.
        script = """Import-Module './scripts/windows/Atlas-Control-Center.psm1' -Force
$bridge = [pscustomobject]@{url=$env:QD_TEST_URL;token=$env:QD_TEST_TOKEN}
$bridge | Add-Member ScriptMethod verify_session {return $true}
$bridge | Add-Member ScriptMethod request_stop {
 param($mode)
 Invoke-RestMethod -Uri ($this.url+'/_atlas/control/stop') -Method Post -ContentType 'application/json' -Headers @{Origin=$this.url;'X-Atlas-Control'=$this.token} -Body (@{mode=$mode}|ConvertTo-Json -Compress)
}
Invoke-AtlasPaperStop $bridge | ConvertTo-Json -Depth 20 -Compress
"""
        result = subprocess.run([str(Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'),
            '-NoProfile', '-Command', script], env={**os.environ, 'QD_TEST_URL': f'http://127.0.0.1:{port}',
            'QD_TEST_TOKEN': token}, capture_output=True, text=True, timeout=35, check=False)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)['outcome']['status'] == 'FLATTENED', result.stdout
        assert s.r.state == 'STOPPED'
        assert s.p.writer.verify_order_drain()
        after = capture(s)
        assert request(ready, m.SELECTED)[0] == 200
        assert capture(s) == after
        with pytest.raises(ValueError): h.close({**ready, 'host_id': 'foreign'})
        assert h.verify_read_only_session(ready)
    finally:
        h.close(ready)
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', port)) != 0


def test_control_acceptance_is_separate_and_missing_read_authority_is_unknown(system):
    s = system
    asyncio.run(cycle(s))
    s.a.verify_read_cuts = lambda *args: False
    assert s.custody.read_accounts(s.r.grant)['state'] == 'UNKNOWN'
    h, _ = host(s)
    h.composition.verify_control_bridge = lambda bridge: False
    with pytest.raises(ValueError, match='SEPARATE_CONTROL'):
        h.start()
    assert h.listener is None
