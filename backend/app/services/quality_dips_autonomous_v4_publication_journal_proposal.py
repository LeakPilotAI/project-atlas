"""Source-only V4 publication reserve/commit recovery model.

Models exact immutable records and fail-closed recovery; it does not write
files, issue custody ACKs, verify independent authority, or enable PAPER.
"""
from app.services.paper_financial_replay import digest

SCHEMA = 'QD_AUTO_V4_PUBLICATION_JOURNAL_PROPOSAL_V1'


def _digest64(value):
    return (type(value) is str and len(value) == 64
            and all(char in '0123456789abcdef' for char in value))


def _record_valid(value):
    return (type(value) is dict
            and set(value) == {'publication_digest', 'publication_id'}
            and _digest64(value['publication_digest'])
            and type(value['publication_id']) is str
            and 1 <= len(value['publication_id']) <= 128)


def _pending_valid(state):
    pending = state['pending']
    return (type(pending) is dict
            and set(pending) == {'revision', 'previous', 'record'}
            and type(pending['revision']) is int
            and pending['revision'] == state['revision'] + 1
            and pending['revision'] <= 128
            and pending['previous'] == state['head']
            and _record_valid(pending['record']))


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
            or (state['revision'] > 0 and not _digest64(state['head']))
            or (state['status'] != 'IDLE' and not _pending_valid(state))):
        raise ValueError('V4_JOURNAL_STATE_INVALID')
    if operation == 'RESERVE':
        if state['status'] != 'IDLE' or state['revision'] >= 128:
            raise ValueError('V4_JOURNAL_RESERVE_REFUSED')
        if not _record_valid(record):
            raise ValueError('V4_JOURNAL_RECORD_INVALID')
        pending = {'revision': state['revision'] + 1,
                   'previous': state['head'], 'record': dict(record)}
        return {**state, 'pending': pending, 'status': 'RESERVED'}
    if operation == 'COMMIT':
        if state['status'] != 'RESERVED' or record is not None:
            raise ValueError('V4_JOURNAL_COMMIT_REFUSED')
        pending = state['pending']
        if not _pending_valid(state):
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