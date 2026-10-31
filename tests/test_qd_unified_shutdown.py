"""Actual QD shutdown financial effects under unified reservation, synthetic custody."""
import copy
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest, number
from app.services.paper_writer_fixture import provision_fixture_writers
from app.services.quality_dips_unified_writer import QualityDipsUnifiedShutdown
from app.services.unified_native_writer import CanonicalWriterLane
from app.services.unified_paper_runtime import UnifiedPaperRuntime
from qd_autonomous_binding_fixture import build
from test_qd_unified_writer_native import proposed, writer
from test_qd_v5_pre_effect_native import capture
from test_quality_dips_shutdown_flatten import quotes as quote_source
from test_unified_native_writer import FixtureCustody
from test_unified_paper_runtime import Installation, Lane, accounts


@pytest.fixture
def system(tmp_path):
    root = Path(os.environ['ATLAS_AUTO_RUNTIME_ROOT'])
    assert root.parent == Path(__file__).resolve().parents[1] / 'logs/diagnostics'
    assert root.name.startswith('qd-auto-runtime-') and tmp_path.is_relative_to(root)
    s = build(tmp_path, root, session_reports=True)
    try:
        yield s
    finally:
        if s.runtime.grant is not None:
            s.runtime.stop()
        s.x.x.close()


def composed(s, *, partial=False, empty=False):
    w, a = writer(s)
    p, observation = proposed(s, w)
    a.reserved = {'state': 'RESERVED', 'binding': digest(p)}
    if not empty:
        w.dispatch(p, a.reserved)
        if partial:
            s.x.n.now[0] += 1
            f = s.x.frame(2, 'partial')
            s.runtime.accept(f)
    # Shutdown observes a new quote sequence; never reuse a prior sequence with
    # a changed price (the actual engine correctly refuses that conflict).
    s.x.n.now[0] += 1
    quotes = quote_source(s)
    stop = QualityDipsUnifiedShutdown(writer=w, quotes=quotes, reports=s.runtime.runtime.reports, session_id='synthetic-unified-stop')
    a.verify_lane = lambda binding, actual: actual['writer'] is w and actual['shutdown'] is stop and actual['reports'] is stop.reports
    lane = CanonicalWriterLane(writer=w, observer=Lane('QUALITY_DIPS'), planner=object(), shutdown=stop, reports=stop.reports)
    path = str(s.x.x.root / 'global-stop-fixture.sqlite')
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE control(stopped INTEGER)')
        db.execute('INSERT INTO control VALUES(0)')
    provision_fixture_writers(path, {'qd': 'fixture-incarnation', 'perp': 'fixture-incarnation'})

    class Custody(FixtureCustody):
        def verify(self, request):
            if self.db.execute('SELECT stopped FROM control').fetchall() != [(1,)]: return False
            if self.db.execute('SELECT 1 FROM writer_operations WHERE acked=0').fetchone(): return False
            self.preview = w.preview(request['proposal'], r.observations['QUALITY_DIPS'])
            self.before, self.projected = accounts(), accounts()
            for row in self.before + self.projected: row['at'] = self.clock()
            position = self.preview['before']['positions'][request['proposal']['command']['position_id']]
            notional = number(position['remaining']) * number(position['entry'])
            self.before[0].update(epoch=w.manifest['epoch'], revision=self.preview['before']['revision'],
                head=self.preview['source_head'], committed_usd=str(notional), positions=[{
                'id': request['proposal']['command']['position_id'], 'instrument_id': 'synthetic-stock', 'side': 'LONG',
                'quantity': position['remaining'], 'gross_usd': str(notional), 'loss_usd': str(notional),
                'reserved_usd': str(notional), 'derivatives': None}])
            self.projected[0].update(epoch=w.manifest['epoch'], revision=self.preview['after']['revision'], head=digest(self.preview['after']))
            return True
        def verify_shutdown_exit(self, request):
            return request.get('mode') == 'SHUTDOWN_REDUCING_EXIT_V1' and r.state == 'STOPPING' and r.entry_closed.is_set()

    custody = Custody(path, w, a, s.x.x.clock)
    custody.policy['max_loss_usd'] = '200'
    r = UnifiedPaperRuntime(lanes={'QUALITY_DIPS': lane, 'HYPERLIQUID': Lane('HYPERLIQUID')},
                            installation=Installation(), portfolio=custody, clock=s.x.x.clock)
    a.verify_shutdown_components = lambda binding, actual: actual['runtime'] is r and actual['writer'] is w and actual['quotes'] is quotes
    a.verify_shutdown_request = lambda binding, frame, obs, cut: r.state == 'STOPPING' and r.entry_closed.is_set()
    a.verify_drain = lambda binding, cut, result: all(number(p['remaining']) == 0 for p in cut['state']['positions'].values())
    stop.bind(r)
    r.start({'test_only': True})
    r.observations['QUALITY_DIPS'] = {'connection': 'CONNECTED', 'session': 'OPEN', 'at': s.x.x.clock(), **observation}
    return SimpleNamespace(**locals())


@pytest.mark.parametrize('partial', [False, True])
def test_actual_qd_global_stop_reserves_then_closes_and_drains(system, partial):
    c = composed(system, partial=partial)
    result = c.r.stop()
    assert result['state'] == 'STOPPED', result
    assert c.w._cut()['state']['revision'] == (3 if partial else 2)
    assert all(number(p['remaining']) == 0 for p in c.w._cut()['state']['positions'].values())
    before = capture(system)
    assert c.r.stop() == result and capture(system) == before
    with sqlite3.connect(c.path) as db:
        assert db.execute('SELECT COUNT(*) FROM writer_operations WHERE acked=1').fetchone() == (1,)


@pytest.mark.parametrize('failure', ['quote', 'global-ack', 'drain', 'report', 'final-authority'])
def test_global_qd_stop_cannot_falsely_complete(system, failure):
    c = composed(system)
    if failure == 'quote':
        c.quotes.observe = quote_source(system, 'stale').observe
    elif failure == 'global-ack': c.custody.fail_ack = True
    elif failure == 'report':
        def refuse_report(*args, **kwargs): raise OSError('SYNTHETIC_REPORT_PERSISTENCE_FAILURE')
        c.s.runtime.runtime.reports.publish = refuse_report
    elif failure == 'final-authority': c.a.verify_drain = lambda *args: False
    else: c.s.x.flags['pending'] = 1
    result = c.r.stop()
    assert result['state'] == 'STOP_INCOMPLETE'
    if failure == 'quote': assert c.w._cut()['state']['revision'] == 1
    if failure == 'global-ack': assert c.r.uncertain


def test_empty_shutdown_has_no_financial_publication(system):
    c = composed(system, empty=True)
    assert c.r.stop()['state'] == 'STOPPED'
    assert c.w._cut()['state']['revision'] == 0


def test_emergency_preserves_position_and_never_dispatches_flatten(system):
    c = composed(system)
    assert c.r.stop(emergency=True)['state'] == 'STOP_INCOMPLETE'
    assert c.w._cut()['state']['revision'] == 1


def test_global_qd_stop_refuses_missing_shutdown_authority(system):
    c = composed(system)
    c.a.verify_shutdown_request = lambda *args: False
    assert c.r.stop()['state'] == 'STOP_INCOMPLETE'
    assert c.w._cut()['state']['revision'] == 1


def test_inclusive_session_audit_refuses_tampering_and_legacy_scope(system):
    from app.services.paper_daily_report import audit_daily_report, build_daily_report
    c = composed(system)
    assert c.r.stop()['state'] == 'STOPPED'
    history = c.stop.reports.history()
    sessions = [d['report'] for d in history if d['report']['schema'] == 'FS3_QD_SESSION_REPORT_V1']
    report = sessions[-1]
    assert report['source']['cutoff_revision'] == 2 and report['counts']['exits'] == 1
    assert report['cash']['closing'] == c.w._cut()['state']['cash']
    calendars = [d['report'] for d in history if d['report']['schema'] == 'FS3_DAILY_REPORT_V1']
    assert calendars and all(r['status'] == 'INCOMPLETE' for r in calendars)
    assert calendars[-1]['source']['cutoff_revision'] < report['source']['cutoff_revision']
    pin, manifest, rows, state, *_ = c.w.store._inspect_existing()
    scope = c.s.x.x.scope
    audit_daily_report(report, scope, manifest, pin, rows, state)
    for damage in ('cash', 'head', 'cut', 'count', 'cost', 'inventory'):
        changed = copy.deepcopy(report)
        if damage == 'cash': changed['cash']['closing'] = '1000'
        elif damage == 'head': changed['source']['head'] = 'f' * 64
        elif damage == 'cut': changed['period']['cutoff_inclusive'] -= 1
        elif damage == 'count': changed['counts']['exits'] = 0
        elif damage == 'cost': changed['realized']['costs'] = '0'
        else: changed['open_positions'] = {'invented': {}}
        with pytest.raises(ValueError): audit_daily_report(changed, scope, manifest, pin, rows, state)
    legacy = {key: value for key, value in scope.items() if key != 'session_reporting_policy'}
    legacy['schema'] = 'FS3_REPORT_SCOPE_V1'
    with pytest.raises(ValueError):
        build_daily_report(legacy, manifest, pin, rows, report['date'], report['observed_at'], session=report['session'])
