"""Actual isolated ASGI response bytes replace stale research in existing viewer."""
import asyncio
import json
import subprocess
from pathlib import Path

import httpx
import pytest
from test_market_refusals import seeded
from test_retained_research import reference

from scripts.observation_runtime import retained_research as module
from scripts.observation_runtime.market_replay import create_replay_app


@pytest.mark.parametrize('error_type', [ValueError,TypeError])
def test_actual_research_refusal_clears_view_and_explicit_recovery_loads(monkeypatch,error_type):
    async def scenario():
        db,store,now = seeded()
        original = module.retained_research
        def fail(*args, **kwargs): raise error_type('SYNTHETIC_PRIVATE')
        try:
            app = create_replay_app(store,symbols=['SPY'],clock=lambda:now,previous_closes={'SPY':reference(now)})
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app,raise_app_exceptions=False),base_url='http://fixture') as client:
                valid = await client.get('/api/market-data/research?symbol=SPY')
                monkeypatch.setattr(module,'retained_research',fail)
                refused = await client.get('/api/market-data/research?symbol=SPY')
                monkeypatch.setattr(module,'retained_research',original)
                recovered = await client.get('/api/market-data/research?symbol=SPY')
            assert (valid.status_code,refused.status_code,recovered.status_code) == (200,503,200)
            assert valid.content == recovered.content
            return {'valid':valid.text,'refused':refused.text,'recovered':recovered.text}
        finally:
            monkeypatch.setattr(module,'retained_research',original)
            db.close()
    payload = asyncio.run(scenario())
    root = Path(__file__).resolve().parents[1]
    q = subprocess.run(['C:/Program Files/nodejs/node.exe',str(root/'tests/research_viewer_handoff.cjs'),str(root)],
                       input=json.dumps(payload),text=True,capture_output=True,timeout=15,check=False)
    assert q.returncode == 0, q.stderr
    assert json.loads(q.stdout)['transitions'] == 4
