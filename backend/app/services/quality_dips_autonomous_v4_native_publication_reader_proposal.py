"""Proposed V4 native financial history-to-publication binding, read-only.

The publication and custody acknowledgment remain claims, not authenticated
independent authority. All pins are caller supplied and must be trusted separately.
"""
from app.services.paper_financial_replay import body, digest, strict
from app.services.quality_dips_autonomous_v4_native_history_reader_proposal import inspect_bounded_proposed_v4_native_history
from app.services.quality_dips_autonomous_v4_publication_proposal import inspect_proposed_v4_publication


def inspect_proposed_v4_native_publication(reader, pins, enrollment, publication, acknowledgment):
    if type(pins) is not dict or not callable(getattr(reader, 'read_bound', None)):
        raise ValueError('V4_NATIVE_PUBLICATION_READER_REQUIRED')
    before = body(publication), body(acknowledgment)
    history = inspect_bounded_proposed_v4_native_history(reader, pins, enrollment)
    count = history['revision']
    envelopes = []
    for i in range(1, count + 1):
        name = f'{i:04d}-event.json'
        raw = reader.read_bound(name, pins[name])
        item = strict(raw.decode('utf-8'))
        if type(item) is not dict or body(item).encode('utf-8') != raw:
            raise ValueError('V4_NATIVE_PUBLICATION_EVENT_CHANGED')
        envelopes.append(item)
    raw = reader.read_bound('assertion.json', pins['assertion.json'])
    assertion = strict(raw.decode('utf-8'))
    if type(assertion) is not dict or body(assertion).encode('utf-8') != raw:
        raise ValueError('V4_NATIVE_PUBLICATION_ASSERTION_CHANGED')
    result = inspect_proposed_v4_publication(enrollment, envelopes, assertion, publication, acknowledgment)
    if result['revision'] != count or result['revision'] != history['revision'] or result['publication_digest'] != digest(publication):
        raise ValueError('V4_NATIVE_PUBLICATION_BINDING_MISMATCH')
    if (body(publication), body(acknowledgment)) != before:
        raise ValueError('V4_NATIVE_PUBLICATION_CLAIMS_MUTATED')
    # Final native readback after publication and acknowledgment checks.
    if set(reader.list_names()) != set(pins):
        raise ValueError('V4_NATIVE_PUBLICATION_ROSTER_CHANGED')
    for i in range(1, count + 1):
        name = f'{i:04d}-event.json'
        if reader.read_bound(name, pins[name]) != body(envelopes[i - 1]).encode('utf-8'):
            raise ValueError('V4_NATIVE_PUBLICATION_POST_AUDIT_EVENT_CHANGED')
    if reader.read_bound('assertion.json', pins['assertion.json']) != body(assertion).encode('utf-8'):
        raise ValueError('V4_NATIVE_PUBLICATION_POST_AUDIT_ASSERTION_CHANGED')
    return {**result, 'native_history_publication_binding_checked': True,
            'independent_custody_verified': False,
            'independent_publication_verified': False,
            'operational_authority_accepted': False,
            'paper_execution_authorized': False, 'live_order_authorized': False}


def __digest(value):
    from app.services.paper_financial_replay import digest
    return digest(value)