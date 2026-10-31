"""Multi-bar failure must not partially commit under supported SQLite modes."""
import sqlite3
from builtins import BaseExceptionGroup
from datetime import UTC, datetime, timedelta

import pytest
from app.investment.offline_research import ResearchInputRefused
from test_market_replay_integration import fixture

from scripts.observation_runtime.market_replay import ReplayStore


def connect(mode):
    if mode == 'native_autocommit':
        return sqlite3.connect(':memory:', autocommit=True)
    return sqlite3.connect(':memory:', isolation_level=None if mode == 'legacy_autocommit' else '')


@pytest.mark.parametrize('mode', ['default','legacy_autocommit','native_autocommit'])
def test_conflicting_batch_is_atomic_in_each_connection_mode(mode):
    db = connect(mode)
    try:
        store = ReplayStore(db)
        ts = datetime(2026,10,20,14,tzinfo=UTC)
        now = ts+timedelta(minutes=3)
        store.ingest(fixture(ts+timedelta(minutes=1)),observed_at=now,asset_class='US_ETF')
        payload = fixture(ts)
        result = payload['chart']['result'][0]
        result['timestamp'].append(int((ts+timedelta(minutes=1)).timestamp()))
        for key, values in result['indicators']['quote'][0].items():
            values.append(100 if key == 'close' else values[0])
        with pytest.raises(ResearchInputRefused,match='Conflicting'):
            store.ingest(payload,observed_at=now,asset_class='US_ETF')
        assert db.execute('SELECT count(*) FROM replay_bars').fetchone()[0] == 1
        assert not db.in_transaction
    finally:
        db.close()


@pytest.mark.parametrize('mode', ['default','legacy_autocommit','native_autocommit'])
def test_success_commits_and_retry_is_duplicate_without_active_transaction(tmp_path, mode):
    path = tmp_path/'synthetic.db'
    options = {'autocommit': True} if mode == 'native_autocommit' else {'isolation_level': None if mode == 'legacy_autocommit' else ''}
    ts = datetime(2026,10,20,14,tzinfo=UTC)
    payload = fixture(ts)
    db = sqlite3.connect(path, **options)
    store = ReplayStore(db)
    assert store.ingest(payload,observed_at=ts+timedelta(minutes=2),asset_class='US_ETF') == 1
    assert not db.in_transaction
    db.close()
    db = sqlite3.connect(path, **options)
    try:
        store = ReplayStore(db)
        assert store.ingest(payload,observed_at=ts+timedelta(minutes=3),asset_class='US_ETF') == 0
        assert db.execute('SELECT count(*) FROM replay_bars').fetchone()[0] == 1
        assert not db.in_transaction
    finally:
        db.close()


@pytest.mark.parametrize('rollback_failure', [False, True])
def test_native_commit_failure_preserves_error_and_uncertain_cleanup_refuses_reuse(rollback_failure):
    commit_error = OSError('synthetic commit failure')
    rollback_error = OSError('synthetic rollback failure')
    class Connection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql == 'COMMIT': raise commit_error
            if sql == 'ROLLBACK' and rollback_failure: raise rollback_error
            return super().execute(sql, parameters)
    db = sqlite3.connect(':memory:',autocommit=True,factory=Connection)
    try:
        store = ReplayStore(db)
        ts = datetime(2026,10,20,14,tzinfo=UTC)
        expected = BaseExceptionGroup if rollback_failure else OSError
        with pytest.raises(expected) as captured:
            store.ingest(fixture(ts),observed_at=ts+timedelta(minutes=2),asset_class='US_ETF')
        if rollback_failure:
            assert captured.value.exceptions == (commit_error, rollback_error)
            with pytest.raises(ResearchInputRefused): store.history('SPY',now=ts+timedelta(minutes=3))
        else:
            assert captured.value is commit_error
            assert db.execute('SELECT count(*) FROM replay_bars').fetchone()[0] == 0
            assert not db.in_transaction
    finally:
        db.close()
