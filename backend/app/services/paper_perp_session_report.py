"""FS3 session cuts over existing FS1 events; no financial writer or authority.

An inclusive current cut differs from a calendar end-exclusive report. Complete
accounting does not mean flat positions, valued equity or accepted process drain.
"""
from decimal import ROUND_HALF_EVEN, Context, Inexact, localcontext

from app.services.paper_daily_report import _perp_inventory, validate_scope
from app.services.paper_financial_audit import _audit_perp, audit_financial_events
from app.services.paper_financial_replay import (
    body,
    digest,
    number,
    replay_verified_events,
    strict,
    text,
)

MONEY = ('gross', 'fees', 'slippage', 'costs', 'funding', 'net')


def _frame(scope, m, pin, rows, *, session_id, started_at, cutoff_at, observed_at, positions):
    validate_scope(scope, m)
    text(session_id)
    if (scope['schema'] != 'FS3_PERP_REPORT_SCOPE_V3'
            or any(type(t) is not int for t in (started_at, cutoff_at, observed_at))
            or not m['opened_at'] <= started_at <= cutoff_at <= observed_at <= cutoff_at + 5
            or pin['epoch'] != m['epoch'] or len(pin['entries']) != len(rows)
            or any(strict(r['command'])['timestamp'] > observed_at for r in rows)):
        raise ValueError('PERP_ACCEPTED_CURRENT_SESSION_CUT_REQUIRED')
    included = [r for r in rows if strict(r['command'])['timestamp'] <= cutoff_at]
    pending = {key: {'next_settlement_at': p['next_funding'], 'remaining': p['remaining'], 'amount': None}
               for key, p in positions.items() if p['next_funding'] <= cutoff_at}
    reasons = []
    if len(included) != len(rows): reasons.append('SOURCE_ADVANCED_BEYOND_CUTOFF')
    if pending: reasons.append('FUNDING_HISTORY_INCOMPLETE')
    if any(strict(r['receipt']).get('projection_required') is not True for r in rows):
        reasons.append('PROJECTION_ACK_REQUIRED')
    commands = [strict(r['command']) for r in included if strict(r['command'])['timestamp'] >= started_at]
    return {'schema': 'FS3_PERP_SESSION_REPORT_V1', 'report_version': 1, 'scope_digest': digest(scope),
        'account_id': scope['account_id'], 'epoch': m['epoch'], 'policy_digest': digest(m), 'currency': m['currency'],
        'strategy': m['strategy'], 'timezone': scope['timezone'], 'session_id': session_id, 'observed_at': observed_at,
        'period': {'kind': 'SESSION_CUT', 'start': started_at, 'cutoff_inclusive': cutoff_at},
        'source': {'root': pin['root'], 'inception': pin['inception'], 'revision': len(rows),
                    'head': rows[-1]['digest'] if rows else digest(m), 'record_lineage': pin['entries'],
                    'cutoff_revision': len(included)},
        'status': 'INCOMPLETE' if reasons else 'COMPLETE', 'reasons': reasons,
        'operation_status': 'FULLY_ACKNOWLEDGED', 'projection_status': 'FULLY_ACKNOWLEDGED',
        'open_positions': positions, 'pending_funding': pending,
        'counts': {key: sum(c['kind'] == kind for c in commands) for key, kind in
                (('entries', 'ENTRY'), ('exits', 'EXIT'), ('funding', 'FUNDING'), ('marks', 'MARK'))},
        'valuation': None, 'valuation_status': 'UNAVAILABLE', 'lifecycle_status': 'NOT_EVALUATED',
        'startup_authorized': False, 'production_authorized': False}


def _money(before, after):
    result = {'cash': {'opening': str(before['cash']), 'closing': str(after['cash'])},
                'realized': {k: str(number(str(after[k])) - number(str(before[k]))) for k in MONEY},
                'collateral': {'opening_reserved': str(before['reserved_margin']), 'closing_reserved': str(after['reserved_margin']),
                                'opening_available': str(before['available_cash']), 'closing_available': str(after['available_cash'])}}
    if 'liquidation_fees' in after:
        result['realized']['liquidation_fees'] = str(number(str(after['liquidation_fees'])) - number(str(before.get('liquidation_fees', '0'))))
    return result


def build_session_report(scope, manifest, pin, rows, *, session_id, started_at, cutoff_at, observed_at):
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)) as context:
        context.traps[Inexact] = True
        full = replay_verified_events(manifest, rows)[0]
        audit_financial_events(manifest, rows, full)
        before = replay_verified_events(manifest, [r for r in rows if strict(r['command'])['timestamp'] < started_at])[0]
        after = replay_verified_events(manifest, [r for r in rows if strict(r['command'])['timestamp'] <= cutoff_at])[0]
        report = _frame(scope, manifest, pin, rows, session_id=session_id, started_at=started_at,
                        cutoff_at=cutoff_at, observed_at=observed_at, positions=_perp_inventory(after['positions']))
        report.update(_money(before, after))
        audit_session_report(report, scope, manifest, pin, rows, full)
        return report


def audit_session_report(report, scope, manifest, pin, rows, snapshot):
    """Independent arithmetic, never invokes replay or the session builder."""
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)) as context:
        context.traps[Inexact] = True
        audit_financial_events(manifest, rows, snapshot)
        start, cut = report['period']['start'], report['period']['cutoff_inclusive']
        before = _audit_perp(manifest, [r for r in rows if strict(r['command'])['timestamp'] < start], None)
        after = _audit_perp(manifest, [r for r in rows if strict(r['command'])['timestamp'] <= cut], None)
        expected = _frame(scope, manifest, pin, rows, session_id=report['session_id'], started_at=start,
                          cutoff_at=cut, observed_at=report['observed_at'], positions=_perp_inventory(after['positions']))
        finances = _money(before['totals'], after['totals'])
        if set(report) != set(expected) | set(finances) or any(body(report[k]) != body(v) for k, v in expected.items()):
            raise ValueError('PERP_SESSION_SOURCE_OR_INVENTORY_MISMATCH')
        for group, values in finances.items():
            if set(report[group]) != set(values) or any(number(report[group][k]) != number(v) for k, v in values.items()):
                raise ValueError('PERP_SESSION_CASH_OR_ACCOUNTING_MISMATCH')
        return {'schema': 'FS3_PERP_SESSION_AUDIT_V1', 'financially_consistent': True, 'operational_acceptance': False}
