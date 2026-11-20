"""Read-only bounded proposed V4 native history consumer.

Caller supplies an existing confined native reader, expected identity/hash pins,
and enrollment. These are not authenticated custody or operational authority.
"""
from app.services.paper_financial_replay import body, strict
from app.services.quality_dips_autonomous_v4_native_envelope_proposal import verify_proposed_v4_native_envelopes


def inspect_bounded_proposed_v4_native_history(reader, pins, enrollment):
    if (not callable(getattr(reader, 'read_bound', None))
            or not callable(getattr(reader, 'list_names', None))
            or type(pins) is not dict or not 2 <= len(pins) <= 129
            or 'assertion.json' not in pins):
        raise ValueError('V4_NATIVE_HISTORY_READER_BOUNDARY')
    count = len(pins) - 1
    expected = {f'{i:04d}-event.json' for i in range(1, count + 1)} | {'assertion.json'}
    if set(pins) != expected or any(type(pin) is not dict or set(pin) != {'id', 'sha256'}
            or type(pin['id']) is not list or len(pin['id']) != 3
            or any(type(v) is not int or v < 0 for v in pin['id'])
            or type(pin['sha256']) is not str or len(pin['sha256']) != 64
            or any(c not in '0123456789abcdef' for c in pin['sha256'])
            for pin in pins.values()):
        raise ValueError('V4_NATIVE_HISTORY_PINS_INVALID')
    if set(reader.list_names()) != expected:
        raise ValueError('V4_NATIVE_HISTORY_ROSTER_INVALID')
    docs = {}
    for name in sorted(expected):
        raw = reader.read_bound(name, pins[name])
        if type(raw) is not bytes or len(raw) > 65536:
            raise ValueError('V4_NATIVE_HISTORY_READ_INVALID')
        value = strict(raw.decode('utf-8'))
        if type(value) is not dict or body(value).encode('utf-8') != raw:
            raise ValueError('V4_NATIVE_HISTORY_CANONICAL_INVALID')
        docs[name] = value
    envelopes = [docs[f'{i:04d}-event.json'] for i in range(1, count + 1)]
    result = verify_proposed_v4_native_envelopes(enrollment, envelopes, docs['assertion.json'])
    if result['revision'] != count or set(reader.list_names()) != expected:
        raise ValueError('V4_NATIVE_HISTORY_POST_AUDIT_ROSTER_INVALID')
    for name in sorted(expected):
        if reader.read_bound(name, pins[name]) != body(docs[name]).encode('utf-8'):
            raise ValueError('V4_NATIVE_HISTORY_POST_AUDIT_CHANGED')
    return {**result, 'native_history_readback_checked': True,
            'independent_custody_accepted': False,
            'operational_authority_accepted': False,
            'paper_execution_authorized': False, 'live_order_authorized': False}