"""Fail-closed tests for the dedicated case-host child entry."""

import pytest

from scripts.observation_runtime import aip06_case_host_entry as host


def test_case_host_main_cannot_run_without_native_qualification():
    with pytest.raises(ValueError, match='NATIVE_CASE_HOST_EXECUTION_NOT_YET_QUALIFIED'):
        host.main()


@pytest.mark.parametrize('maximum_bytes,timeout', [(0, 6), (65537, 6), (65536, 0), (65536, 7), (True, 6), (65536, True)])
def test_case_host_rejects_unbounded_read_before_fixture_lookup(maximum_bytes, timeout, monkeypatch):
    monkeypatch.setattr(host, 'require_fixture', lambda name: pytest.fail('unexpected fixture lookup'))
    with pytest.raises(ValueError, match='BOUNDED_CASE_HOST_HANDOFF_READ_REQUIRED'):
        host.inspect_inherited_handoff(maximum_bytes=maximum_bytes, timeout=timeout)


def test_case_host_requires_original_guard(monkeypatch):
    def refuse(name):
        assert name == 'independent-case-host-preflight'
        raise ValueError('ORIGINAL_GUARD_NOT_INSTALLED')
    monkeypatch.setattr(host, 'require_fixture', refuse)
    with pytest.raises(ValueError, match='ORIGINAL_GUARD_NOT_INSTALLED'):
        host.inspect_inherited_handoff()
