"""Calculation failures remain observable, sanitized non-success, never research success."""
import asyncio

import httpx
import pytest
from test_market_refusals import seeded
from test_retained_research import reference

from scripts.observation_runtime import retained_research as module
from scripts.observation_runtime.market_replay import create_replay_app


@pytest.mark.parametrize('path', ['/api/market-data/research?symbol=SPY','/research?symbol=SPY'])
@pytest.mark.parametrize('error_type', [ValueError,TypeError,KeyError,OverflowError])
def test_calculation_failure_uses_observable_non_success(path,error_type,monkeypatch):
    error = error_type('SYNTHETIC_PRIVATE_FAILURE')
    def fail(*args, **kwargs): raise error
    monkeypatch.setattr(module,'retained_research',fail)
    async def scenario():
        db,store,now = seeded()
        errors = []
        try:
            app = create_replay_app(store,symbols=['SPY'],clock=lambda:now,
                                    previous_closes={'SPY':reference(now)},failure_observer=errors.append)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app,raise_app_exceptions=False),base_url='http://fixture') as client:
                response = await client.get(path)
            assert response.status_code == 503
            assert response.headers['cache-control'] == 'no-store'
            assert errors == [error]
            assert 'SYNTHETIC_PRIVATE_FAILURE' not in response.text
            assert not db.in_transaction
            if path.startswith('/api/'):
                assert response.json()['rows'] == []
                assert response.json()['reason'] == 'DATA_UNAVAILABLE'
            else:
                assert 'Data unavailable' in response.text
                assert 'No current prices or partial research' in response.text
        finally:
            db.close()
    asyncio.run(scenario())
