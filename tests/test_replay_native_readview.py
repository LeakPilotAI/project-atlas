"""Read-view cleanup must roll back explicit native-autocommit transactions."""
import sqlite3
from builtins import BaseExceptionGroup
from datetime import UTC, datetime, timedelta

import pytest
from app.investment.offline_research import ResearchInputRefused
from test_market_replay_integration import fixture

from scripts.observation_runtime.market_replay import ReplayStore


def connection(mode):
    return sqlite3.connect(':memory:', **({'autocommit': True} if mode == 'native' else {'isolation_level': None if mode == 'legacy' else ''}))


@pytest.mark.parametrize('mode', ['default','legacy','native'])
@pytest.mark.parametrize('fail_operation', [False, True])
def test_owned_view_rolls_back_without_changing_operation_result(mode, fail_operation):
    db = connection(mode)
    try:
        store = ReplayStore(db)
        ts = datetime(2026,10,20,14,tzinfo=UTC)
        store.ingest(fixture(ts),observed_at=ts+timedelta(minutes=2),asset_class='US_ETF')
        error = ValueError('synthetic read interruption')
        def operation():
            with store.read_view():
                db.execute('CREATE TABLE accidental_fixture(value)')
                db.execute('INSERT INTO accidental_fixture VALUES (1)')
                if fail_operation: raise error
        if fail_operation:
            with pytest.raises(ValueError) as captured: operation()
            assert captured.value is error
        else:
            operation()
        assert not db.in_transaction and store._read_view_fault is None
        assert db.execute("SELECT name FROM sqlite_master WHERE name='accidental_fixture'").fetchall() == []
        with store.read_view(): assert len(store.history('SPY',now=ts+timedelta(minutes=3))['rows']) == 1
    finally:
        db.close()


@pytest.mark.parametrize('timing', ['before','after'])
def test_native_rollback_failure_preserves_both_errors_and_refuses_reuse(timing):
    cleanup = OSError('synthetic rollback error')
    operation = ValueError('synthetic read error')
    class Connection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql == 'ROLLBACK':
                if timing == 'after': super().execute(sql, parameters)
                raise cleanup
            return super().execute(sql, parameters)
    db = sqlite3.connect(':memory:',autocommit=True,factory=Connection)
    try:
        store = ReplayStore(db)
        with pytest.raises(BaseExceptionGroup) as captured, store.read_view(): raise operation
        assert captured.value.exceptions == (operation, cleanup)
        assert store._read_view_fault is captured.value
        with pytest.raises(ResearchInputRefused), store.read_view(): pass
    finally:
        db.close()


@pytest.mark.parametrize('mode', ['default','legacy','native'])
def test_owned_snapshot_stays_consistent_across_independent_fixture_writer(tmp_path, mode):
    options = {'autocommit': True} if mode == 'native' else {'isolation_level': None if mode == 'legacy' else ''}
    path = tmp_path/'synthetic-wal.db'
    db = sqlite3.connect(path, **options)
    writer = None
    try:
        assert db.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal'
        store = ReplayStore(db)
        ts = datetime(2026,10,20,14,tzinfo=UTC)
        now = ts+timedelta(minutes=4)
        store.ingest(fixture(ts),observed_at=now,asset_class='US_ETF')
        writer = sqlite3.connect(path,autocommit=True)
        other = ReplayStore(writer)
        with store.read_view():
            first = store.history('SPY',now=now)
            other.ingest(fixture(ts+timedelta(minutes=1)),observed_at=now,asset_class='US_ETF')
            assert store.history('SPY',now=now) == first
            assert len(first['rows']) == 1
        assert not db.in_transaction
        assert len(store.history('SPY',now=now)['rows']) == 2
    finally:
        if writer is not None: writer.close()
        db.close()
