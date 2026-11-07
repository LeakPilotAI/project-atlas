"""Real FS2/FS3 Stop orchestration; all ownership/market authority is synthetic."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
import test_unified_native_writer as native_fixtures
from app.services.paper_financial_replay import digest
from app.services.unified_native_writer import (
    CanonicalWriterLane,
    PerpShutdownCoordinator,
)
from test_perp_financial_v2 import entry, exit_command, manifest
from test_perp_margin_tiers import tier_policy
from test_quality_dips_financial_records_native import TestPins
from test_unified_native_writer import m, submit

native_bundle = native_fixtures.bundle


@pytest.fixture
def installed(native_bundle, tmp_path):
    r, store, pins, now, writer, custody = native_bundle
    pins.now = now[0]
    old = r.lanes['HYPERLIQUID']
    scope = {'schema': 'FS3_PERP_REPORT_SCOPE_V3', 'account_id': 'synthetic', 'epoch': manifest()['epoch'],
                 'policy_digest': digest(manifest()), 'timezone': 'UTC', 'funding_reporting_policy': 'POSTED_CASH_AND_SETTLEMENT_ACCRUAL_V1',
                 'session_reporting_policy': 'ACKNOWLEDGED_EVENT_TIME_INCLUSIVE_CUT_V1'}
    path = str(tmp_path / 'session-report')
    report_pin = TestPins(m.ReportArchive.provision_disposable(path, scope, manifest()))
    archive = m.ReportArchive(path, report_pin)
    reports = m.ReportService(store, archive)
    flags = {'quotes': True, 'stale': False, 'drain': True, 'quote_reads': 0}
    class Books:
        def shutdown_evidence(self, position, cut, at):
            flags['quote_reads'] += 1
            if not flags['quotes']: raise ValueError('SYNTHETIC_DISCONNECTED_BOOK')
            e = entry()['evidence']
            e.update(bid='104', ask='105', sequence='shutdown-book', observed_at=at - 100 if flags['stale'] else at)
            return e
    books = Books()
    shutdown = PerpShutdownCoordinator(writer=writer, books=books, reports=reports, clock=r.clock, session_id='synthetic-session', started_at=3601)
    lane = CanonicalWriterLane(writer=writer, observer=old.observer, planner=old.planner, shutdown=shutdown, reports=reports)
    r.lanes['HYPERLIQUID'] = lane
    writer.authority.verify_shutdown_components = lambda binding, c: c['books'] is books and c['runtime'] is r and c['session_id'] == 'synthetic-session'
    shutdown.bind(r)
    custody.verify_shutdown_exit = lambda request: request['mode'] == 'SHUTDOWN_REDUCING_EXIT_V1' and r.entry_closed.is_set()
    original_drain = writer.authority.verify_drain
    writer.authority.verify_drain = lambda *args: flags['drain'] and original_drain(*args)
    try: yield r, store, pins, now, writer, custody, shutdown, books, reports, flags
    finally: archive.close()


def open_position(installed, side='LONG', partial=False):
    r, store, pins, now, writer, custody, *_ = installed
    c = entry(side=side)
    c['schema'] = 'PAPER_PERP_MARGIN_ENTRY_V1'
    c['evidence']['margin_policy'] = tier_policy()
    writer.authority.verify_margin_policy = lambda *args: True
    submit((r, store, pins, now, writer, custody), c)
    if partial:
        class View:
            manifest = globals()['manifest']()
            def snapshot(self): return store.verified_cut()['state']
        submit((r, store, pins, now, writer, custody), exit_command(View(), '0.2'))
    prior = writer.authority.verify_proposal
    writer.authority.verify_proposal = lambda binding, proposal, observation, cut: (
        proposal['strategy_ref'] == 'SHUTDOWN_FLATTEN:synthetic-session'
        and proposal['command']['kind'] == 'EXIT' and proposal['source_head'] == cut['head']) or prior(binding, proposal, observation, cut)


@pytest.mark.parametrize('side,partial', [('LONG', False), ('SHORT', False), ('LONG', True)])
def test_actual_native_stop_flattens_remaining_and_reconciles_session(side, partial, installed):
    open_position(installed, side, partial)
    r, store, pins, now, _, _, _, _, reports, _ = installed
    pins.now = now[0] = 3604
    before = store.verified_cut()['state']['revision']
    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(lambda _: r.stop(), range(2)))
    assert outcomes[0] == outcomes[1] and outcomes[0]['state'] == 'STOPPED'
    cut = store.verified_cut()
    assert cut['state']['revision'] == before + 1 and cut['state']['reserved_margin'] == '0'
    assert all(Decimal(p['remaining']) == 0 for p in cut['state']['positions'].values())
    history = reports.history()
    assert len(history) == 1 and history[0]['report']['schema'] == 'FS3_PERP_SESSION_REPORT_V1'
    assert history[0]['report']['cash']['closing'] == cut['state']['cash']
    with pytest.raises(ValueError): r.start({'test_only': True})


@pytest.mark.parametrize('failure', ['disconnected', 'stale', 'ack', 'report', 'drain', 'emergency'])
def test_actual_stop_failure_never_falsely_clean(failure, installed, monkeypatch):
    open_position(installed)
    r, store, pins, now, _, custody, _, _, reports, flags = installed
    pins.now = now[0] = 3604
    if failure == 'disconnected': flags['quotes'] = False
    elif failure == 'stale': flags['stale'] = True
    elif failure == 'ack': custody.fail_ack = True
    elif failure == 'drain': flags['drain'] = False
    elif failure == 'report':
        def failed(*args, **kwargs): raise OSError('SYNTHETIC_REPORT_DISK_FAILURE')
        monkeypatch.setattr(reports.archive.output, 'write_bound', failed)
    result = r.stop(emergency=failure == 'emergency')
    assert result['state'] == 'STOP_INCOMPLETE'
    state = store.verified_cut()['state']
    if failure in ('disconnected', 'stale', 'emergency'):
        assert state['revision'] == 1 and next(iter(state['positions'].values()))['remaining'] == '0.5'
    else:
        assert state['revision'] == 2 and all(Decimal(p['remaining']) == 0 for p in state['positions'].values())
    if failure == 'emergency': assert flags['quote_reads'] == 0
    assert r.stop() == result


def test_flat_stop_does_not_invent_prices_or_financial_events(installed):
    r, store, _, _, _, _, _, _, reports, flags = installed
    flags['quotes'] = False
    assert r.stop()['state'] == 'STOPPED'
    assert store.verified_cut()['state']['revision'] == 0 and flags['quote_reads'] == 0
    assert reports.history()[0]['report']['realized']['net'] == '0'
