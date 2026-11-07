"""Read-only crash inspection of externally pinned proposed V4 native journal.

No recovery grant, no self-issued pins, no unfencing, no operational authority.
A final RESERVED record is always UNCERTAIN, even when internally consistent.
"""
from app.services.paper_financial_replay import body, strict
from app.services.quality_dips_autonomous_v4_publication_journal_proposal import (
    initial_publication_journal, transition_publication_journal)


def inspect_pinned_native_v4_journal(native, pins):
    if (not callable(getattr(native, 'read_bound', None))
            or not callable(getattr(native, 'list_names', None))
            or type(pins) is not dict or not 1 <= len(pins) <= 256):
        raise ValueError('V4_JOURNAL_RECOVERY_PINNED_NATIVE_REQUIRED')
    names = set(pins)
    if (len(names) != len(pins) or set(native.list_names()) != names
            or any(type(pin) is not dict or set(pin) != {'id', 'sha256'}
                   or type(pin['id']) is not list or len(pin['id']) != 3
                   or any(type(x) is not int or x < 0 for x in pin['id'])
                   or type(pin['sha256']) is not str or len(pin['sha256']) != 64
                   or any(c not in '0123456789abcdef' for c in pin['sha256'])
                   for pin in pins.values())):
        raise ValueError('V4_JOURNAL_RECOVERY_PIN_ROSTER_INVALID')
    state = initial_publication_journal()
    documents = {}
    for number in range(1, 129):
        reserved_name = f'{number:04d}-reserved.json'
        if reserved_name not in names:
            break
        raw = native.read_bound(reserved_name, pins[reserved_name])
        doc = strict(raw.decode('utf-8'))
        if type(doc) is not dict or body(doc).encode('utf-8') != raw:
            raise ValueError('V4_JOURNAL_RECOVERY_NONCANONICAL')
        if doc['status'] != 'RESERVED':
            raise ValueError('V4_JOURNAL_RECOVERY_EXPECTED_RESERVATION')
        expected = transition_publication_journal(state, 'RESERVE', doc['pending']['record'])
        if doc != expected:
            raise ValueError('V4_JOURNAL_RECOVERY_CHAIN_INVALID')
        documents[reserved_name] = raw
        state = expected
        committed_name = f'{number:04d}-committed.json'
        if committed_name not in names:
            break
        raw = native.read_bound(committed_name, pins[committed_name])
        doc = strict(raw.decode('utf-8'))
        if type(doc) is not dict or body(doc).encode('utf-8') != raw:
            raise ValueError('V4_JOURNAL_RECOVERY_NONCANONICAL')
        expected = transition_publication_journal(state, 'COMMIT')
        if doc != expected:
            raise ValueError('V4_JOURNAL_RECOVERY_CHAIN_INVALID')
        documents[committed_name] = raw
        state = expected
    if set(documents) != names or set(native.list_names()) != names:
        raise ValueError('V4_JOURNAL_RECOVERY_GAP_OR_ROSTER')
    for name, raw in documents.items():
        if native.read_bound(name, pins[name]) != raw:
            raise ValueError('V4_JOURNAL_RECOVERY_POST_AUDIT_CHANGED')
    if set(native.list_names()) != names:
        raise ValueError('V4_JOURNAL_RECOVERY_POST_AUDIT_ROSTER')
    stopped = transition_publication_journal(state, 'RESTART')
    return {'schema': 'QD_AUTO_V4_NATIVE_CRASH_INSPECTION_PROPOSAL_V1',
            'revision': stopped['revision'], 'head': stopped['head'],
            'status': stopped['status'], 'snapshot_count': len(documents),
            'native_history_consistent': True, 'restart_fenced': True,
            'independent_pin_custody_accepted': False,
            'operational_authority_accepted': False,
            'paper_execution_authorized': False, 'live_order_authorized': False}