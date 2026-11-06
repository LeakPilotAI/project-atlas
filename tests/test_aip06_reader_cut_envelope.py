"""Independent reader must refuse malformed native cut envelopes before output."""
from types import SimpleNamespace

import pytest

from scripts.observation_runtime.aip06_scoped_context import ReaderExecutionContext


@pytest.mark.parametrize('raw', [
    None, [], {}, {'native_acceptance': False, 'observer': {}, 'cuts': None},
    {'native_acceptance': False, 'observer': {}, 'cuts': {}},
    {'native_acceptance': False, 'observer': {}, 'cuts': [None]},
    {'native_acceptance': False, 'observer': {}, 'cuts': [{'reader': 'a'}]},
    *({'native_acceptance': False, 'observer': {}, 'cuts': [
        {'reader': reader, 'started_ns': started, 'finished_ns': finished}]}
      for reader, started, finished in [
          (None, 1, 2), (7, 1, 2), ('a', True, 2),
          ('a', 1.5, 2), ('a', 1, False), ('a', 1, '2')]),
], ids=['none', 'list', 'empty', 'null-cuts', 'dict-cuts', 'null-cut',
        'missing-timestamps', 'null-reader', 'numeric-reader', 'boolean-start',
        'float-start', 'boolean-finish', 'text-finish'])
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
