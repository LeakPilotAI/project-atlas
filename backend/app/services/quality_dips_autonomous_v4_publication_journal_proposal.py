"""Source-only V4 publication reserve/commit recovery model.

Models exact immutable records and fail-closed recovery; it does not write
files, issue custody ACKs, verify independent authority, or enable PAPER.
"""
from app.services.paper_financial_replay import digest

SCHEMA = 'QD_AUTO_V4_PUBLICATION_JOURNAL_PROPOSAL_V1'


def initial_publication_journal():
    return {'schema': SCHEMA, 'revision': 0, 'head': None, 'pending': None,
            'status': 'IDLE'}


def transition_publication_journal(state, operation, record=None):
    if (type(state) is not dict or set(state) != {'schema', 'revision', 'head', 'pending', 'status'}
            or state['schema'] != SCHEMA or type(state['revision']) is not int
            or not 0 <= state['revision'] <= 128
            or state['status'] not in ('IDLE', 'RESERVED', 'UNCERTAIN')
            or (state['status'] == 'IDLE' and state['pending'] is not None)
            or (state['status'] != 'IDLE' and type(state['pending']) is not dict)
            or (state['revision'] == 0 and state['head'] is not None)
            or (state['revision'] > 0 and (type(state['head']) is not str or len(state['head']) != 64))):
        raise ValueError('V4_JOURNAL_STATE_INVALID')
    if operation == 'RESERVE':
        if state['status'] != 'IDLE' or state['revision'] >= 128:
            raise ValueError('V4_JOURNAL_RESERVE_REFUSED')
        if (type(record) is not dict or set(record) != {'publication_digest', 'publication_id'}
                or type(record['publication_digest']) is not str
                or len(record['publication_digest']) != 64
                or type(record['publication_id']) is not str
                or not 1 <= len(record['publication_id']) <= 128):
            raise ValueError('V4_JOURNAL_RECORD_INVALID')
        pending = {'revision': state['revision'] + 1,
                   'previous': state['head'], 'record': dict(record)}
        return {**state, 'pending': pending, 'status': 'RESERVED'}
    if operation == 'COMMIT':
        if state['status'] != 'RESERVED' or record is not None:
            raise ValueError('V4_JOURNAL_COMMIT_REFUSED')
        pending = state['pending']
        if (set(pending) != {'revision', 'previous', 'record'}
                or type(pending['revision']) is not int
                or pending['revision'] != state['revision'] + 1
                or pending['previous'] != state['head']
                or type(pending['record']) is not dict
                or set(pending['record']) != {'publication_digest', 'publication_id'}):
            raise ValueError('V4_JOURNAL_PENDING_INVALID')
        return {**state, 'revision': pending['revision'],
                'head': digest([SCHEMA, pending]), 'pending': None, 'status': 'IDLE'}
    if operation == 'RESTART':
        if record is not None:
            raise ValueError('V4_JOURNAL_RESTART_REFUSED')
        # A reserved-but-uncommitted publication cannot be guessed committed,
        # discarded, retried or ACKed after an unclean stop.
        return {**state, 'status': 'UNCERTAIN' if state['pending'] is not None else 'IDLE'}
    raise ValueError('V4_JOURNAL_UNKNOWN_OPERATION')