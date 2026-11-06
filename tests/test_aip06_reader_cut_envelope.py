"""Independent reader must refuse malformed native cut envelopes before output."""
from types import SimpleNamespace

import pytest

from scripts.observation_runtime.aip06_scoped_context import ReaderExecutionContext


@pytest.mark.parametrize('raw', [
    None, [], {}, {'native_acceptance': False, 'observer': {}, 'cuts': None},
    {'native_acceptance': False, 'observer': {}, 'cuts': {}},
    {'native_acceptance': False, 'observer': {}, 'cuts': [None]},
    {'native_acceptance': False, 'observer': {}, 'cuts': [{'reader': 'a'}]},
], ids=['none', 'list', 'empty', 'null-cuts', 'dict-cuts', 'null-cut', 'missing-timestamps'])
def test_malformed_native_cut_envelope_fails_closed(raw):
    emitted = []
    context = object.__new__(ReaderExecutionContext)
    context.packet = {'request': {'scope': 'fixture'}}
    context.result = None
    context.failed = False
    context.guard = SimpleNamespace(clock=lambda: 100,
        processes=SimpleNamespace(emit_output=lambda value: emitted.append(value)))
    context.adapters = SimpleNamespace(collect=lambda *args, **kwargs: raw)
    context.verify = lambda **kwargs: None
    with pytest.raises(ValueError, match='INDEPENDENT_RAW_CUT_ENVELOPE_REQUIRED'):
        context.collect(context.packet['request'], deadline_ns=200)
    assert context.failed and context.result is None and emitted == []
