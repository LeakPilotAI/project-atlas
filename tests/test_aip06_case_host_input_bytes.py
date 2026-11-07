"""Inherited case-host INPUT must be exact, bounded bytes before preflight."""
from types import SimpleNamespace

import pytest

from scripts.observation_runtime import aip06_case_host_entry as host


@pytest.mark.parametrize('raw', [None, '', b'', bytearray(b'{}'), b'{}' * 32769],
                         ids=['none', 'text', 'empty', 'bytearray', 'oversized'])
def test_case_host_refuses_nonbyte_or_oversized_private_input(monkeypatch, raw):
    verifier = host.ntpath.join(host.ntpath.dirname(host.HOST_ENTRY), 'aip06_host_preflight.py')
    pins = {host.HOST_ENTRY: 'a' * 64, verifier: 'b' * 64}
    descriptor = {'argv': ['python', '-B', host.HOST_ENTRY],
                  'targets': {'case_host': host.HOST_ENTRY}, 'source_pins': pins}
    runtime = SimpleNamespace(descriptor=descriptor,
                              verify_source=lambda path: {'path': path, 'sha256': pins[path], 'closed': True})
    calls = []
    guard = SimpleNamespace(processes=SimpleNamespace(runtime=runtime,
        read_input=lambda **kwargs: (calls.append(kwargs), raw)[1]))
    monkeypatch.setattr(host, 'require_fixture', lambda name: guard)
    monkeypatch.setattr(host, 'inspect', lambda *args: pytest.fail('unbounded input reached preflight'))
    with pytest.raises(ValueError, match='BOUNDED_ORIGINAL_CASE_HOST_INPUT_BYTES_REQUIRED'):
        host.inspect_inherited_handoff()
    assert calls == [{'maximum_bytes': 65536, 'timeout': 6}]


def test_case_host_refuses_invalid_utf8_before_preflight(monkeypatch):
    verifier = host.ntpath.join(host.ntpath.dirname(host.HOST_ENTRY), 'aip06_host_preflight.py')
    pins = {host.HOST_ENTRY: 'a' * 64, verifier: 'b' * 64}
    descriptor = {'argv': ['python', '-B', host.HOST_ENTRY],
                  'targets': {'case_host': host.HOST_ENTRY}, 'source_pins': pins}
    runtime = SimpleNamespace(descriptor=descriptor,
                              verify_source=lambda path: {'path': path, 'sha256': pins[path], 'closed': True})
    guard = SimpleNamespace(processes=SimpleNamespace(
        runtime=runtime, read_input=lambda **kwargs: b'\xff'))
    monkeypatch.setattr(host, 'require_fixture', lambda name: guard)
    monkeypatch.setattr(host, 'inspect', lambda *args: pytest.fail('invalid UTF-8 reached preflight'))
    with pytest.raises(UnicodeDecodeError):
        host.inspect_inherited_handoff()
