"""Source-only V4 inception replay; never supplies publication or custody authority.

Nonzero revisions require an independently specified V4 event transition and audit
protocol; this verifier refuses them instead of trusting an event-head assertion.
"""
from app.services.paper_financial_replay import body, digest, number
from app.services.quality_dips_autonomous_publication_binding import bind_financial_publication_to_native_cut


class V4InceptionFinancialReplay:
    """Financial verification of the zero-event V4 publication, not an issuer."""

    def verify(self, enrollment, publication, cut, documents, now, *, scope):
        if scope != 'LOCAL_ENROLLED' or type(now) is not int or now <= 0:
            raise ValueError('AUTO_V4_REPLAY_SCOPE_OR_CLOCK')
        if type(cut) is not dict or cut.get('scope') != scope:
            raise ValueError('AUTO_V4_REPLAY_CUT_SCOPE')
        bind_financial_publication_to_native_cut(enrollment, publication, cut, documents)
        if publication['revision'] != 0:
            raise ValueError('AUTO_V4_REPLAY_NONZERO_PROTOCOL_NOT_ACCEPTED')
        inception = documents['source']['inception.json']
        projection = documents['projection']['projection.json']
        report = documents['report']['report.json']
        if (set(inception) != {'schema', 'account_id', 'epoch', 'enrollment_digest',
                              'inception_digest', 'opening_cash', 'positions', 'obligations'}
                or number(inception['opening_cash']) != 1000
                or inception['positions'] != {} or inception['obligations'] != []):
            raise ValueError('AUTO_V4_REPLAY_INCEPTION_INVALID')
        state = {'cash': inception['opening_cash'], 'positions': {}, 'gross': '0',
                 'costs': '0', 'net': '0', 'revision': 0}
        if (set(projection) != {'schema', 'account_id', 'epoch', 'enrollment_digest', 'revision', 'state'}
                or type(projection['revision']) is not int or projection['revision'] != 0
                or body(projection['state']) != body(state)
                or set(report) != {'schema', 'account_id', 'epoch', 'enrollment_digest',
                                   'revision', 'head', 'state_digest', 'status'}
                or type(report['revision']) is not int or report['revision'] != 0
                or report['status'] != 'COMPLETE'
                or report['head'] != digest(['QD_AUTO_NATIVE_INCEPTION_V4', digest(inception)])
                or report['state_digest'] != digest(state)):
            raise ValueError('AUTO_V4_REPLAY_INCEPTION_RECONCILIATION_FAILED')
        return True