"""Independent reader rejects malformed input before provider construction."""
from types import SimpleNamespace

import pytest

from scripts.observation_runtime import aip06_reader_context_entry as entry
from scripts.observation_runtime import aip06_fixture_guard as fixture


@pytest.mark.parametrize('raw', [None, '', b'', bytearray(b'{}'), b'{}' * 32769],
                         ids=['none', 'text', 'empty', 'bytearray', 'oversized'])
def test_reader_refuses_nonbounded_input(monkeypatch, raw):
    calls = []
    guard = SimpleNamespace(read_input=lambda **kwargs: calls.append(kwargs) or raw)
    monkeypatch.setattr(fixture, 'require_fixture', lambda name: guard)
    with pytest.raises(ValueError, match='BOUNDED_INDEPENDENT_READER_INPUT_BYTES_REQUIRED'):
        entry.prepare_reader(None, None)
    assert calls == [{'maximum_bytes': 65536, 'timeout': 6}]


def test_reader_refuses_malformed_utf8(monkeypatch):
    guard = SimpleNamespace(read_input=lambda **kwargs: bytes([255]))
    monkeypatch.setattr(fixture, 'require_fixture', lambda name: guard)
    with pytest.raises(UnicodeDecodeError):
        entry.prepare_reader(None, None)
