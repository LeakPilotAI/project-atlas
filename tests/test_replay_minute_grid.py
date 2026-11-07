"""Irregular minute observations cannot imply negative or fictitious gap counts."""
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from app.investment.offline_research import ResearchInputRefused
from test_market_replay_integration import fixture

from scripts.observation_runtime.market_replay import ReplayStore
from scripts.observation_runtime.session_quality import session_quality


def seeded(offsets):
    ts = datetime(2026,10,20,14,tzinfo=UTC)
    now = ts+timedelta(minutes=5)
    payload = fixture(ts)
    result = payload['chart']['result'][0]
    result['timestamp'] = [int((ts+timedelta(seconds=n)).timestamp()) for n in offsets]
    for values in result['indicators']['quote'][0].values(): values[:] = [values[0]]*len(offsets)
    db = sqlite3.connect(':memory:')
    store = ReplayStore(db)
    store.ingest(payload,observed_at=now,asset_class='US_ETF')
    return db,store,now


@pytest.mark.parametrize('offsets', [[0,30],[0,30,60],[0,90]])
def test_non_minute_provider_observations_refuse_before_storage(offsets):
    ts = datetime(2026,10,20,14,tzinfo=UTC)
    payload = fixture(ts)
    result = payload['chart']['result'][0]
    result['timestamp'] = [int((ts+timedelta(seconds=n)).timestamp()) for n in offsets]
    for values in result['indicators']['quote'][0].values(): values[:] = [values[0]]*len(offsets)
    db = sqlite3.connect(':memory:')
    try:
        store = ReplayStore(db)
        with pytest.raises(ResearchInputRefused) as captured:
            store.ingest(payload,observed_at=ts+timedelta(minutes=5),asset_class='US_ETF')
        assert 'non-minute' in str(captured.value.__cause__)
        assert db.execute('SELECT count(*) FROM replay_bars').fetchone()[0] == 0
        assert not db.in_transaction
    finally:
        db.close()


@pytest.mark.parametrize('phase', [0,60])
def test_aligned_grid_preserves_exact_interior_gap_count(phase):
    db,store,now = seeded([phase,phase+120])
    try:
        coverage = store.snapshot(['SPY'],now=now)['rows'][0]['coverage']
        quality = session_quality(store.history('SPY',now=now),now=now)
        assert coverage['missing_minutes'] == 1
        assert quality['windows'][0]['missing_minutes_between_observed_bars'] == 1
    finally:
        db.close()
