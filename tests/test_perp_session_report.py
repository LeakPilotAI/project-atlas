"""Source-pinned intraday reports; no operational authority in pure fixtures."""
import copy
from types import SimpleNamespace

import pytest
from app.services.paper_daily_report import build_daily_report
from app.services.paper_financial_replay import (
    apply_event,
    body,
    digest,
    event_stream_record,
    initial_state,
)
from app.services.paper_perp_session_report import (
    audit_session_report,
    build_session_report,
)
from test_perp_financial_v2 import entry, exit_command, funding, manifest


def source():
    m = manifest()
    s = SimpleNamespace(manifest=m, state=initial_state(m), rows=[], pin={'epoch': m['epoch'], 'root': [1, 2, 3], 'inception': {'synthetic': True}, 'entries': []})
    s.snapshot = lambda: s.state
    def execute(c):
        parent = s.rows[-1]['digest'] if s.rows else digest(m)
        state, r = apply_event(m, s.state, c)
        r['projection_required'] = True
        s.rows.append(event_stream_record(r['source_revision'], c['operation_id'], body(c), parent, digest([parent, c, r]), body(r)))
        s.pin['entries'].append({'SYNTHETIC_BOUND_RECEIPT': digest(r)})
        s.state = state
    s.execute = execute
    s.scope = {'schema': 'FS3_PERP_REPORT_SCOPE_V3', 'account_id': 'synthetic', 'epoch': m['epoch'], 'policy_digest': digest(m), 'timezone': 'UTC',
                   'funding_reporting_policy': 'POSTED_CASH_AND_SETTLEMENT_ACCRUAL_V1', 'session_reporting_policy': 'ACKNOWLEDGED_EVENT_TIME_INCLUSIVE_CUT_V1'}
    return s


def build(s, cutoff=3603, started=3601):
    return build_session_report(s.scope, s.manifest, s.pin, s.rows, session_id='synthetic-session', started_at=started, cutoff_at=cutoff, observed_at=cutoff)


def test_same_second_final_exit_is_inclusive_but_calendar_report_incomplete():
    s = source()
    s.execute(entry())
    s.execute(exit_command(s))
    r = build(s)
    assert r['status'] == 'COMPLETE' and r['open_positions'] == {} and r['source']['cutoff_revision'] == 2
    assert r['cash']['closing'] == s.state['cash']
    assert r['lifecycle_status'] == 'NOT_EVALUATED'
    daily = build_daily_report(s.scope, s.manifest, s.pin, s.rows, '1970-01-01', 3603)
    assert daily['status'] == 'INCOMPLETE' and daily['source']['cutoff_revision'] == 1


def test_open_position_can_be_financially_complete_without_flat_or_valuation_claim():
    s = source()
    s.execute(entry())
    r = build(s)
    assert r['status'] == 'COMPLETE' and len(r['open_positions']) == 1
    assert r['valuation'] is None and r['lifecycle_status'] == 'NOT_EVALUATED'
    assert build(s, 7200)['status'] == 'INCOMPLETE'
    assert next(iter(build(s, 7200)['pending_funding'].values()))['amount'] is None


def test_partial_funding_full_close_and_new_session_cash():
    s = source()
    s.execute(entry())
    s.execute(exit_command(s, '0.2'))
    old = build(s)
    s.execute(funding(s))
    s.execute(exit_command(s, '0.3', 7202, 'final', '104'))
    r = build(s, 7202, 7200)
    assert r['cash']['opening'] == old['cash']['closing']
    assert r['cash']['closing'] == '1001.52936' and r['counts']['funding'] == 1
    assert r['status'] == 'COMPLETE' and r['open_positions'] == {}


@pytest.mark.parametrize('damage', ['cash', 'quantity', 'source', 'complete', 'clock', 'scope', 'kind'])
def test_independent_audit_rejects_tampered_session(damage):
    s = source()
    s.execute(entry())
    r = build(s)
    if damage == 'cash': r['cash']['closing'] = '1000'
    elif damage == 'quantity': next(iter(r['open_positions'].values()))['remaining'] = '0'
    elif damage == 'source': r['source']['head'] = 'f' * 64
    elif damage == 'complete': r['lifecycle_status'] = 'CLEAN_SHUTDOWN'
    elif damage == 'clock': r['observed_at'] += 10
    elif damage == 'scope': r['scope_digest'] = 'e' * 64
    else: r['period']['kind'] = 'CALENDAR_DAY'
    with pytest.raises(ValueError): audit_session_report(r, s.scope, s.manifest, s.pin, s.rows, s.state)


def test_old_report_scope_does_not_silently_authorize_session_reports():
    s = source()
    s.scope.update(schema='FS3_PERP_REPORT_SCOPE_V2')
    del s.scope['session_reporting_policy']
    with pytest.raises(ValueError): build(s)


def test_advanced_source_cannot_certify_historical_cut_as_current():
    s = source()
    s.execute(entry())
    s.execute(exit_command(s))
    report = build_session_report(s.scope, s.manifest, s.pin, s.rows, session_id='synthetic', started_at=3601, cutoff_at=3602, observed_at=3603)
    assert report['status'] == 'INCOMPLETE' and 'SOURCE_ADVANCED_BEYOND_CUTOFF' in report['reasons']


def test_independent_auditor_never_calls_session_builder_or_replay(monkeypatch):
    import app.services.paper_perp_session_report as module
    s = source()
    s.execute(entry())
    r = build(s)
    def forbidden(*args, **kwargs): raise AssertionError('Audit invoked builder/replay')
    monkeypatch.setattr(module, 'build_session_report', forbidden)
    monkeypatch.setattr(module, 'replay_verified_events', forbidden)
    assert audit_session_report(r, s.scope, s.manifest, s.pin, s.rows, copy.deepcopy(s.state))['financially_consistent']
