"""Fail-closed tests for the dedicated case-host child entry."""

import pytest
from types import SimpleNamespace

from scripts.observation_runtime import aip06_case_host_entry as host


def test_case_host_main_checks_handoff_then_refuses_native_execution(monkeypatch):
    observed = []
    monkeypatch.setattr(host, 'inspect_inherited_handoff', lambda: observed.append('checked'))
    with pytest.raises(ValueError, match='NATIVE_CASE_HOST_EXECUTION_NOT_YET_QUALIFIED'):
        host.main()
    assert observed == ['checked']


def test_case_host_main_never_promotes_failed_handoff(monkeypatch):
    def reject():
        raise ValueError('ORIGINAL_PHYSICAL_HOST_RESERVATION_STILL_HELD')
    monkeypatch.setattr(host, 'inspect_inherited_handoff', reject)
    with pytest.raises(ValueError, match='ORIGINAL_PHYSICAL_HOST_RESERVATION_STILL_HELD'):
        host.main()


def test_case_host_reads_bounded_private_handoff_and_calls_preflight(monkeypatch):
    observed = []
    descriptor = {'private': 'descriptor', 'argv': ['python', '-B', host.HOST_ENTRY],
                  'targets': {'case_host': host.HOST_ENTRY},
                  'source_pins': {host.HOST_ENTRY: 'a' * 64}}
    packet = {'schema': 'packet'}
    guard = SimpleNamespace(processes=SimpleNamespace(runtime=SimpleNamespace(descriptor=descriptor)))
    def read_input(*, maximum_bytes, timeout):
        observed.append((maximum_bytes, timeout))
        return b'{"schema":"packet"}'
    guard.read_input = read_input
    monkeypatch.setattr(host, 'require_fixture', lambda name: guard)
    monkeypatch.setattr(host, 'inspect', lambda p, d, g: (p, d, g))
    assert host.inspect_inherited_handoff() == (packet, descriptor, guard)
    assert observed == [(65536, 6)]


@pytest.mark.parametrize('field', ['argv', 'targets', 'source_pins'])
def test_case_host_refuses_unbound_launch_descriptor_before_read(monkeypatch, field):
    descriptor = {'argv': ['python', '-B', host.HOST_ENTRY],
                  'targets': {'case_host': host.HOST_ENTRY},
                  'source_pins': {host.HOST_ENTRY: 'a' * 64}}
    descriptor.pop(field)
    guard = SimpleNamespace(processes=SimpleNamespace(runtime=SimpleNamespace(descriptor=descriptor)),
                            read_input=lambda **kwargs: pytest.fail('read before launch verification'))
    monkeypatch.setattr(host, 'require_fixture', lambda name: guard)
    with pytest.raises(ValueError, match='PINNED_INHERITED_CASE_HOST_COMMAND_REQUIRED'):
        host.inspect_inherited_handoff()


@pytest.mark.parametrize('maximum_bytes,timeout', [(0, 6), (65537, 6), (65536, 0), (65536, 7), (True, 6), (65536, True)])
def test_case_host_rejects_unbounded_read_before_fixture_lookup(maximum_bytes, timeout, monkeypatch):
    monkeypatch.setattr(host, 'require_fixture', lambda name: pytest.fail('unexpected fixture lookup'))
    with pytest.raises(ValueError, match='BOUNDED_CASE_HOST_HANDOFF_READ_REQUIRED'):
        host.inspect_inherited_handoff(maximum_bytes=maximum_bytes, timeout=timeout)


def test_case_host_rejects_invalid_private_payload_before_preflight(monkeypatch):
    descriptor = {'argv': ['python', '-B', host.HOST_ENTRY],
                  'targets': {'case_host': host.HOST_ENTRY},
                  'source_pins': {host.HOST_ENTRY: 'a' * 64}}
    guard = SimpleNamespace(processes=SimpleNamespace(runtime=SimpleNamespace(descriptor=descriptor)),
                            read_input=lambda **kwargs: b'not-json')
    monkeypatch.setattr(host, 'require_fixture', lambda name: guard)
    monkeypatch.setattr(host, 'inspect', lambda *args: pytest.fail('preflight must not run'))
    with pytest.raises((ValueError, TypeError)):
        host.inspect_inherited_handoff()


def test_case_host_requires_original_guard(monkeypatch):
    def refuse(name):
        assert name == 'independent-case-host-preflight'
        raise ValueError('ORIGINAL_GUARD_NOT_INSTALLED')
    monkeypatch.setattr(host, 'require_fixture', refuse)
    with pytest.raises(ValueError, match='ORIGINAL_GUARD_NOT_INSTALLED'):
        host.inspect_inherited_handoff()
