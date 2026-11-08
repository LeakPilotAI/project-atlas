"""Disposable handshake verifies data flow without granting socket acceptance."""
import os

import pytest

from scripts.observation_runtime.disposable_tcp_handshake_control import inspect


@pytest.mark.skipif(os.name != 'nt', reason='Windows native IP Helper required')
def test_handshake_control_never_grants_authority():
    result = inspect()
    assert result['schema'] == 'ATLAS_TCP_HANDSHAKE_CONTROL_V1'
    assert result['loopback_payload_verified'] is True
    assert result['socket_accepting'] is True
    assert result['endpoints_redacted'] is True
    assert result['operational_listener_accepted'] is False
    assert result['financial_authorized'] is False
    for stage in ('before', 'during', 'after'):
        assert isinstance(result[stage]['states'], list)
        assert set(result[stage]) == {'states', 'error'}
