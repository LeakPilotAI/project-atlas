import pytest
from app.services.paper_stop_receipt_ledger import PaperStopReceiptLedger, StopReceiptConflict

def test_stop_intent_survives_reopen_and_cannot_change_mode(tmp_path):
    path = tmp_path / "stop.sqlite"
    ledger = PaperStopReceiptLedger(path)
    assert ledger.reserve("session-1", "SHUTDOWN_FLATTEN")["state"] == "PENDING"
    reopened = PaperStopReceiptLedger(path)
    assert reopened.reserve("session-1", "SHUTDOWN_FLATTEN")["state"] == "PENDING"
    with pytest.raises(StopReceiptConflict):
        reopened.reserve("session-1", "EMERGENCY")

def test_stop_receipt_survives_reopen_and_refuses_duplicate_finish(tmp_path):
    path = tmp_path / "stop.sqlite"
    ledger = PaperStopReceiptLedger(path)
    ledger.reserve("session-1", "SHUTDOWN_FLATTEN")
    receipt = {"phase":"FINISHED","outcome":{"mode":"SHUTDOWN_FLATTEN","status":"SHUTDOWN_INCOMPLETE"}}
    ledger.finish("session-1", "SHUTDOWN_FLATTEN", receipt)
    assert PaperStopReceiptLedger(path).reserve("session-1", "SHUTDOWN_FLATTEN")["receipt"] == receipt
    with pytest.raises(StopReceiptConflict):
        ledger.finish("session-1", "SHUTDOWN_FLATTEN", receipt)

def test_stop_receipt_requires_reserved_intent_and_matching_mode(tmp_path):
    ledger = PaperStopReceiptLedger(tmp_path / "stop.sqlite")
    receipt = {"phase":"FINISHED","outcome":{"mode":"SHUTDOWN_FLATTEN","status":"SHUTDOWN_INCOMPLETE"}}
    with pytest.raises(StopReceiptConflict):
        ledger.finish("missing", "SHUTDOWN_FLATTEN", receipt)
    ledger.reserve("s", "EMERGENCY")
    with pytest.raises(ValueError):
        ledger.finish("s", "EMERGENCY", receipt)
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import pytest
from app.services.paper_stop_receipt_ledger import PaperStopReceiptLedger, StopReceiptConflict

def test_simultaneous_reservations_one_intent(tmp_path):
    path = tmp_path / "stop.sqlite"
    def reserve(_):
        return PaperStopReceiptLedger(path).reserve("same", "SHUTDOWN_FLATTEN")
    PaperStopReceiptLedger(path)
    with ThreadPoolExecutor(max_workers=12) as pool:
        rows = list(pool.map(reserve, range(24)))
    assert all(row == {"state":"PENDING","mode":"SHUTDOWN_FLATTEN","receipt":None} for row in rows)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM stop_receipts").fetchone()[0] == 1

def test_interrupted_stop_remains_pending_not_flat(tmp_path):
    path = tmp_path / "stop.sqlite"
    PaperStopReceiptLedger(path).reserve("interrupted", "SHUTDOWN_FLATTEN")
    recovered = PaperStopReceiptLedger(path).reserve("interrupted", "SHUTDOWN_FLATTEN")
    assert recovered["state"] == "PENDING"
    assert recovered["receipt"] is None

def test_concurrent_finishes_only_one_wins(tmp_path):
    path = tmp_path / "stop.sqlite"
    PaperStopReceiptLedger(path).reserve("same", "SHUTDOWN_FLATTEN")
    receipt = {"phase":"FINISHED","outcome":{"mode":"SHUTDOWN_FLATTEN","status":"SHUTDOWN_INCOMPLETE"}}
    def finish(_):
        try:
            PaperStopReceiptLedger(path).finish("same", "SHUTDOWN_FLATTEN", receipt)
            return "FINISHED"
        except StopReceiptConflict:
            return "CONFLICT"
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(finish, range(12)))
    assert results.count("FINISHED") == 1
    assert results.count("CONFLICT") == 11

def test_corrupted_receipt_never_treated_as_complete(tmp_path):
    path = tmp_path / "stop.sqlite"
    ledger = PaperStopReceiptLedger(path)
    ledger.reserve("same", "SHUTDOWN_FLATTEN")
    with sqlite3.connect(path) as db:
        db.execute("UPDATE stop_receipts SET state='FINISHED',receipt='invalid-json' WHERE session='same'")
    with pytest.raises(ValueError):
        ledger.reserve("same", "SHUTDOWN_FLATTEN")
def test_read_only_recovery_does_not_create_missing_intent(tmp_path):
    ledger = PaperStopReceiptLedger(tmp_path / "stop.sqlite")
    with pytest.raises(StopReceiptConflict):
        ledger.recover("missing", "SHUTDOWN_FLATTEN")
    ledger.reserve("s", "SHUTDOWN_FLATTEN")
    assert ledger.recover("s", "SHUTDOWN_FLATTEN") == {
        "state":"SHUTDOWN_UNVERIFIED","mode":"SHUTDOWN_FLATTEN","receipt":None}
    receipt = {"phase":"FINISHED","outcome":{"mode":"SHUTDOWN_FLATTEN","status":"SHUTDOWN_INCOMPLETE"}}
    ledger.finish("s", "SHUTDOWN_FLATTEN", receipt)
    assert PaperStopReceiptLedger(ledger.path).recover("s", "SHUTDOWN_FLATTEN") == {
        "state":"RECEIPT_RECORDED","mode":"SHUTDOWN_FLATTEN","receipt":receipt}
def test_stop_ledger_refuses_symlink_database(tmp_path):
    real = tmp_path / "real.sqlite"
    PaperStopReceiptLedger(real)
    link = tmp_path / "alias.sqlite"
    try:
        link.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this Windows account")
    with pytest.raises(ValueError, match="SYMLINK"):
        PaperStopReceiptLedger(link)
def test_reserve_rejects_semantically_forged_finished_receipt(tmp_path):
    path = tmp_path / "stop.sqlite"
    ledger = PaperStopReceiptLedger(path)
    ledger.reserve("s", "SHUTDOWN_FLATTEN")
    with sqlite3.connect(path) as db:
        db.execute("UPDATE stop_receipts SET state='FINISHED', receipt=? WHERE session='s'",
                   ('{"phase":"FINISHED","outcome":{"mode":"EMERGENCY","status":"FLATTENED"}}',))
    with pytest.raises(StopReceiptConflict, match="CORRUPT"):
        ledger.reserve("s", "SHUTDOWN_FLATTEN")
def test_fresh_stop_intent_is_single_use_across_restarts(tmp_path):
    path = tmp_path / "stop.sqlite"
    ledger = PaperStopReceiptLedger(path)
    assert ledger.reserve_fresh("session", "SHUTDOWN_FLATTEN")["state"] == "PENDING"
    with pytest.raises(StopReceiptConflict, match="ALREADY_EXISTS"):
        PaperStopReceiptLedger(path).reserve_fresh("session", "SHUTDOWN_FLATTEN")
    with pytest.raises(StopReceiptConflict, match="ALREADY_EXISTS"):
        PaperStopReceiptLedger(path).reserve_fresh("session", "EMERGENCY")
    assert ledger.recover("session", "SHUTDOWN_FLATTEN")["state"] == "SHUTDOWN_UNVERIFIED"

def test_fresh_intent_concurrent_claim_has_single_winner(tmp_path):
    path = tmp_path / "stop.sqlite"
    PaperStopReceiptLedger(path)
    def claim(_):
        try:
            PaperStopReceiptLedger(path).reserve_fresh("same", "SHUTDOWN_FLATTEN")
            return "CLAIMED"
        except StopReceiptConflict:
            return "BLOCKED"
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(claim, range(16)))
    assert outcomes.count("CLAIMED") == 1
    assert outcomes.count("BLOCKED") == 15
def test_inspect_session_read_only_and_corrupt_mode_refused(tmp_path):
    import sqlite3
    ledger = PaperStopReceiptLedger(tmp_path / "stop.sqlite")
    assert ledger.inspect_session("absent") is None
    ledger.reserve_fresh("emergency", "EMERGENCY")
    assert ledger.inspect_session("emergency") == {"state":"PENDING","mode":"EMERGENCY","receipt":None}
    with sqlite3.connect(ledger.path) as db:
        db.execute("UPDATE stop_receipts SET mode='FORGED' WHERE session='emergency'")
    with pytest.raises(StopReceiptConflict, match="CORRUPT"):
        ledger.inspect_session("emergency")
def test_inspect_session_does_not_call_second_reader(tmp_path, monkeypatch):
    ledger = PaperStopReceiptLedger(tmp_path / "stop.sqlite")
    ledger.reserve_fresh("s", "EMERGENCY")
    def forbidden(*args):
        raise AssertionError("second query is forbidden")
    monkeypatch.setattr(ledger, "reserve_existing", forbidden)
    assert ledger.inspect_session("s") == {"state":"PENDING","mode":"EMERGENCY","receipt":None}

def test_inspect_session_rejects_forged_finished_receipt(tmp_path):
    import sqlite3
    ledger = PaperStopReceiptLedger(tmp_path / "stop.sqlite")
    ledger.reserve_fresh("s", "EMERGENCY")
    with sqlite3.connect(ledger.path) as db:
        db.execute("UPDATE stop_receipts SET state='FINISHED',receipt=? WHERE session='s'",
                   ('{"phase":"FINISHED","outcome":{"mode":"SHUTDOWN_FLATTEN","status":"FLATTENED"}}',))
    with pytest.raises(StopReceiptConflict, match="CORRUPT"):
        ledger.inspect_session("s")
def test_sqlite_connection_closed_after_normal_and_failed_ledger_operations(tmp_path, monkeypatch):
    import sqlite3
    from app.services import paper_stop_receipt_ledger as module
    real_connect = sqlite3.connect
    handles = []
    class TrackedConnection(sqlite3.Connection):
        def close(self):
            handles.append(self)
            super().close()
    def tracked_connect(*args, **kwargs):
        kwargs["factory"] = TrackedConnection
        return real_connect(*args, **kwargs)
    monkeypatch.setattr(module.sqlite3, "connect", tracked_connect)
    ledger = PaperStopReceiptLedger(tmp_path / "stop.sqlite")
    ledger.reserve_fresh("s", "SHUTDOWN_FLATTEN")
    assert ledger.inspect_session("s")["state"] == "PENDING"
    with pytest.raises(StopReceiptConflict):
        ledger.reserve_fresh("s", "SHUTDOWN_FLATTEN")
    assert len(handles) == 4
    for handle in handles:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            handle.execute("SELECT 1")



def test_recovery_inventory_tracks_pending_and_recorded_without_flat_claim(tmp_path):
    path = tmp_path / 'stop.sqlite'
    ledger = PaperStopReceiptLedger(path)
    ledger.reserve_fresh('a', 'SHUTDOWN_FLATTEN')
    ledger.reserve_fresh('b', 'EMERGENCY')
    ledger.finish('b', 'EMERGENCY', {'phase': 'FINISHED', 'outcome': {'mode': 'EMERGENCY', 'status': 'SHUTDOWN_INCOMPLETE'}})
    expected = {'schema': 'ATLAS_PAPER_STOP_RECOVERY_INVENTORY_V1',
                'pending_unverified': 1, 'receipts_recorded_not_flat_verified': 1,
                'receipts_without_flatten_claim': 1,
                'requires_independent_position_reconciliation': True,
                'financial_authorized': False, 'startup_authorized': False}
    assert ledger.summarize_recovery() == expected
    assert PaperStopReceiptLedger(path).summarize_recovery() == expected


def test_recovery_inventory_fails_closed_on_corrupt_row(tmp_path):
    path = tmp_path / 'stop.sqlite'
    ledger = PaperStopReceiptLedger(path)
    ledger.reserve_fresh('a', 'SHUTDOWN_FLATTEN')
    with sqlite3.connect(path) as db:
        db.execute("UPDATE stop_receipts SET state='FINISHED',receipt='{}' WHERE session='a'")
    with pytest.raises(StopReceiptConflict, match='CORRUPT'):
        ledger.summarize_recovery()


def test_recovery_inventory_empty_never_authorizes(tmp_path):
    result = PaperStopReceiptLedger(tmp_path / 'stop.sqlite').summarize_recovery()
    assert result['pending_unverified'] == 0
    assert result['receipts_recorded_not_flat_verified'] == 0
    assert result['startup_authorized'] is False


def test_recovery_inventory_finished_flatten_claim_still_needs_independent_reconciliation(tmp_path):
    ledger = PaperStopReceiptLedger(tmp_path / 'stop.sqlite')
    ledger.reserve_fresh('s', 'SHUTDOWN_FLATTEN')
    ledger.finish('s', 'SHUTDOWN_FLATTEN', {'phase': 'FINISHED', 'outcome': {'mode': 'SHUTDOWN_FLATTEN', 'status': 'FLATTENED'}})
    result = PaperStopReceiptLedger(ledger.path).summarize_recovery()
    assert result['receipts_without_flatten_claim'] == 0
    assert result['requires_independent_position_reconciliation'] is True
    assert result['startup_authorized'] is False


def test_recovery_inventory_missing_receipt_status_fails_closed(tmp_path):
    ledger = PaperStopReceiptLedger(tmp_path / 'stop.sqlite')
    ledger.reserve_fresh('s', 'EMERGENCY')
    ledger.finish('s', 'EMERGENCY', {'phase': 'FINISHED', 'outcome': {'mode': 'EMERGENCY'}})
    with pytest.raises(StopReceiptConflict, match='CORRUPT'):
        PaperStopReceiptLedger(ledger.path).summarize_recovery()


def test_restart_observation_compares_both_lanes_without_authorizing(tmp_path):
    path = tmp_path / 'stop.sqlite'
    ledger = PaperStopReceiptLedger(path)
    ledger.reserve_fresh('session', 'SHUTDOWN_FLATTEN')
    cuts = {'QUALITY_DIPS': {'open_positions': 1, 'unsettled_orders': 0},
            'HYPERLIQUID': {'open_positions': 0, 'unsettled_orders': 0}}
    result = PaperStopReceiptLedger(path).reconcile_restart_observation('session', lane_positions=cuts)
    assert result['stop_record_state'] == 'PENDING'
    assert result['exposure_observed'] is True
    assert result['reconciliation_required'] is True
    assert result['startup_authorized'] is False
    assert 'session' not in str(result)
    cuts['QUALITY_DIPS']['open_positions'] = 0
    assert ledger.reconcile_restart_observation('session', lane_positions=cuts)['startup_authorized'] is False


def test_restart_observation_finished_receipt_not_proof_of_flat(tmp_path):
    ledger = PaperStopReceiptLedger(tmp_path / 'stop.sqlite')
    ledger.reserve_fresh('s', 'SHUTDOWN_FLATTEN')
    ledger.finish('s', 'SHUTDOWN_FLATTEN', {'phase': 'FINISHED', 'outcome': {'mode': 'SHUTDOWN_FLATTEN', 'status': 'FLATTENED'}})
    cuts = {k: {'open_positions': 0, 'unsettled_orders': 0} for k in ('QUALITY_DIPS', 'HYPERLIQUID')}
    result = ledger.reconcile_restart_observation('s', lane_positions=cuts)
    assert result['stop_record_state'] == 'FINISHED'
    assert result['reconciliation_required'] is True
    assert result['startup_authorized'] is False


def test_restart_observation_refuses_missing_or_malformed_lane_cuts(tmp_path):
    ledger = PaperStopReceiptLedger(tmp_path / 'stop.sqlite')
    ledger.reserve_fresh('s', 'EMERGENCY')
    good = {k: {'open_positions': 0, 'unsettled_orders': 0} for k in ('QUALITY_DIPS', 'HYPERLIQUID')}
    for bad in ({}, {'QUALITY_DIPS': good['QUALITY_DIPS']},
                {**good, 'HYPERLIQUID': {'open_positions': True, 'unsettled_orders': 0}},
                {**good, 'HYPERLIQUID': {'open_positions': -1, 'unsettled_orders': 0}}):
        with pytest.raises(ValueError, match='LANE'):
            ledger.reconcile_restart_observation('s', lane_positions=bad)
    with pytest.raises(StopReceiptConflict, match='MISSING'):
        ledger.reconcile_restart_observation('missing', lane_positions=good)


def test_native_restart_observation_requires_verified_custody_and_bound_session(tmp_path, monkeypatch):
    from app.services.unified_portfolio_custody import UnifiedPortfolioCustody
    ledger = PaperStopReceiptLedger(tmp_path / 'stop.sqlite')
    ledger.reserve_fresh('s', 'SHUTDOWN_FLATTEN')
    custody = object.__new__(UnifiedPortfolioCustody)
    snapshot = {'state': 'ACKNOWLEDGED', 'accounts': {
        k: {'positions': {}, 'resting_orders': {}, 'source_head': 'test-head', 'source_revision': 1, 'observed_at': 123, 'epoch': 'test-epoch', 'strategy': 'test-strategy'}
        for k in ('QUALITY_DIPS', 'HYPERLIQUID')}}
    monkeypatch.setattr(UnifiedPortfolioCustody, 'read_accounts', lambda self, grant: snapshot)
    result = ledger.observe_native_account_restart('s', custody=custody, grant={'session_id': 's'})
    assert result['exposure_observed'] is False
    assert result['reconciliation_required'] is True
    assert result['startup_authorized'] is False
    with pytest.raises(ValueError, match='SESSION_BINDING'):
        ledger.observe_native_account_restart('s', custody=custody, grant={'session_id': 'other'})
    with pytest.raises(ValueError, match='NATIVE_CUSTODY'):
        ledger.observe_native_account_restart('s', custody=object(), grant={'session_id': 's'})


def test_native_restart_observation_refuses_missing_orders_or_unknown_cuts(tmp_path, monkeypatch):
    from app.services.unified_portfolio_custody import UnifiedPortfolioCustody
    ledger = PaperStopReceiptLedger(tmp_path / 'stop.sqlite')
    ledger.reserve_fresh('s', 'EMERGENCY')
    custody = object.__new__(UnifiedPortfolioCustody)
    snapshots = [
        {'state': 'UNKNOWN', 'accounts': None},
        {'state': 'ACKNOWLEDGED', 'accounts': {
            k: {'positions': {}, 'source_head': 'test-head', 'source_revision': 1, 'observed_at': 123, 'epoch': 'test-epoch', 'strategy': 'test-strategy'}
            for k in ('QUALITY_DIPS', 'HYPERLIQUID')}}]
    monkeypatch.setattr(UnifiedPortfolioCustody, 'read_accounts', lambda self, grant: snapshots.pop(0))
    for _ in range(2):
        with pytest.raises(StopReceiptConflict, match='NATIVE_CUT_UNVERIFIED'):
            ledger.observe_native_account_restart('s', custody=custody, grant={'session_id': 's'})


def test_native_restart_observation_detects_positions_and_resting_orders(tmp_path, monkeypatch):
    from app.services.unified_portfolio_custody import UnifiedPortfolioCustody
    ledger = PaperStopReceiptLedger(tmp_path / 'stop.sqlite')
    ledger.reserve_fresh('s', 'SHUTDOWN_FLATTEN')
    custody = object.__new__(UnifiedPortfolioCustody)
    monkeypatch.setattr(UnifiedPortfolioCustody, 'read_accounts', lambda self, grant: {
        'state': 'ACKNOWLEDGED', 'accounts': {
            'QUALITY_DIPS': {'positions': {'a': {}}, 'resting_orders': {}, 'source_head': 'head1', 'source_revision': 1, 'observed_at': 123, 'epoch': 'test-epoch', 'strategy': 'test-strategy'},
            'HYPERLIQUID': {'positions': {}, 'resting_orders': {'b': {}}, 'source_head': 'head2', 'source_revision': 1, 'observed_at': 123, 'epoch': 'test-epoch', 'strategy': 'test-strategy'}}})
    result = ledger.observe_native_account_restart('s', custody=custody, grant={'session_id': 's'})
    assert result['exposure_observed'] is True
    assert result['startup_authorized'] is False


def test_native_restart_observation_rejects_stop_record_changed_during_custody_read(tmp_path, monkeypatch):
    from app.services.unified_portfolio_custody import UnifiedPortfolioCustody
    ledger = PaperStopReceiptLedger(tmp_path / 'stop.sqlite')
    ledger.reserve_fresh('s', 'SHUTDOWN_FLATTEN')
    custody = object.__new__(UnifiedPortfolioCustody)
    def read_with_concurrent_stop_finish(self, grant):
        PaperStopReceiptLedger(ledger.path).finish('s', 'SHUTDOWN_FLATTEN', {
            'phase': 'FINISHED', 'outcome': {'mode': 'SHUTDOWN_FLATTEN', 'status': 'SHUTDOWN_INCOMPLETE'}})
        return {'state': 'ACKNOWLEDGED', 'accounts': {
            k: {'positions': {}, 'resting_orders': {}, 'source_head': 'head', 'source_revision': 1, 'observed_at': 123, 'epoch': 'test-epoch', 'strategy': 'test-strategy'}
            for k in ('QUALITY_DIPS', 'HYPERLIQUID')}}
    monkeypatch.setattr(UnifiedPortfolioCustody, 'read_accounts', read_with_concurrent_stop_finish)
    with pytest.raises(StopReceiptConflict, match='RECORD_CHANGED'):
        ledger.observe_native_account_restart('s', custody=custody, grant={'session_id': 's'})
    assert ledger.inspect_session('s')['state'] == 'FINISHED'


def test_native_restart_observation_rejects_unattributed_custody_cut(tmp_path, monkeypatch):
    from app.services.unified_portfolio_custody import UnifiedPortfolioCustody
    ledger = PaperStopReceiptLedger(tmp_path / 'stop.sqlite')
    ledger.reserve_fresh('s', 'SHUTDOWN_FLATTEN')
    custody = object.__new__(UnifiedPortfolioCustody)
    account = {'positions': {}, 'resting_orders': {}, 'source_head': 'head',
               'source_revision': 1, 'observed_at': 123,
               'epoch': 'test-epoch', 'strategy': 'test-strategy'}
    snapshot = {'state': 'ACKNOWLEDGED', 'accounts': {
        k: dict(account) for k in ('QUALITY_DIPS', 'HYPERLIQUID')}}
    monkeypatch.setattr(UnifiedPortfolioCustody, 'read_accounts', lambda self, grant: snapshot)
    for field, invalid in (('source_revision', True), ('source_revision', -1),
                           ('observed_at', None), ('epoch', ''),
                           ('strategy', None), ('source_head', '')):
        previous = snapshot['accounts']['HYPERLIQUID'][field]
        snapshot['accounts']['HYPERLIQUID'][field] = invalid
        with pytest.raises(StopReceiptConflict, match='NATIVE_CUT_UNVERIFIED'):
            ledger.observe_native_account_restart('s', custody=custody, grant={'session_id': 's'})
        snapshot['accounts']['HYPERLIQUID'][field] = previous
