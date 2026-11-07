"""Source-only V4 inception financial verifier; no custody, publisher or grant.

Validates an already authenticated immutable native document cut. This is a
narrow zero-revision inception verifier, NOT an operational replay adapter.
"""
from app.services.paper_financial_replay import body, digest, number, strict
from app.services.quality_dips_autonomous_enrollment import publication_intent, validate_enrollment


class AutonomousInceptionFinancialVerifier:
    """Fail-closed financial port for the zero-event autonomous inception cut."""

    def verify_cut(self, enrollment, current, documents, now, *, scope):
        if scope not in ('LOCAL_ENROLLED', 'DISPOSABLE_TEST') or type(now) is not int or now <= 0:
            raise ValueError('AUTO_FINANCIAL_SCOPE_OR_CLOCK_REFUSED')
        e = validate_enrollment(enrollment)
        if type(documents) is not dict or set(documents) != set(e['resources']):
            raise ValueError('AUTO_FINANCIAL_COMPLETE_ROSTER_REQUIRED')
        if type(current) is not dict or current.get('scope') != scope:
            raise ValueError('AUTO_FINANCIAL_CURRENT_SCOPE_REFUSED')
        if any(current.get(k) != 0 for k in ('revision', 'acknowledged_revision', 'high_water')):
            raise ValueError('AUTO_FINANCIAL_INCEPTION_REVISION_REQUIRED')
        if current.get('status') != 'ACKNOWLEDGED' or type(current.get('publication_ack')) is not str:
            raise ValueError('AUTO_FINANCIAL_PUBLICATION_ACK_REQUIRED')
        intent = publication_intent(e)
        publication = current.get('publication')
        if (type(publication) is not dict or publication.get('intent_digest') != digest(intent)
                or publication.get('operation_id') != intent['operation_id']
                or publication.get('status') != 'ACKNOWLEDGED'
                or publication.get('ack_id') != current['publication_ack']):
            raise ValueError('AUTO_FINANCIAL_FOREIGN_PUBLICATION')
        expected = {'source': {'inception.json'}, 'projection': {'projection.json'},
                    'report': {'report.json'}, 'control': set(),
                    'coordination': set(), 'custody': set()}
        if any(type(documents[role]) is not dict or set(documents[role]) != names
               for role, names in expected.items()):
            raise ValueError('AUTO_FINANCIAL_INCEPTION_NAMESPACE_REQUIRED')
        inception = strict(body(documents['source']['inception.json']))
        projection = strict(body(documents['projection']['projection.json']))
        report = strict(body(documents['report']['report.json']))
        if (set(inception) != {'schema', 'account_id', 'epoch', 'enrollment_digest', 'inception_digest', 'opening_cash', 'positions', 'obligations'}
                or inception['schema'] != 'QD_AUTO_NATIVE_INCEPTION_V4'
                or inception['account_id'] != e['account_id'] or inception['epoch'] != e['epoch']
                or inception['enrollment_digest'] != digest(e)
                or inception['inception_digest'] != e['inception_digest']
                or number(inception['opening_cash']) != 1000
                or inception['positions'] != {} or inception['obligations'] != []):
            raise ValueError('AUTO_FINANCIAL_INCEPTION_MISMATCH')
        state = {'cash': inception['opening_cash'], 'positions': {}, 'gross': '0',
                 'costs': '0', 'net': '0', 'revision': 0}
        if (set(projection) != {'schema', 'account_id', 'epoch', 'enrollment_digest', 'revision', 'state'}
                or projection['schema'] != 'QD_AUTO_NATIVE_PROJECTION_V4'
                or projection['account_id'] != e['account_id'] or projection['epoch'] != e['epoch']
                or projection['enrollment_digest'] != digest(e)
                or type(projection['revision']) is not int or projection['revision'] != 0
                or body(projection['state']) != body(state)):
            raise ValueError('AUTO_FINANCIAL_PROJECTION_MISMATCH')
        if (set(report) != {'schema', 'account_id', 'epoch', 'enrollment_digest', 'revision', 'state_digest', 'status'}
                or report['schema'] != 'QD_AUTO_NATIVE_REPORT_V4'
                or report['account_id'] != e['account_id'] or report['epoch'] != e['epoch']
                or report['enrollment_digest'] != digest(e)
                or type(report['revision']) is not int or report['revision'] != 0
                or report['state_digest'] != digest(state) or report['status'] != 'COMPLETE'):
            raise ValueError('AUTO_FINANCIAL_REPORT_MISMATCH')
        return True
