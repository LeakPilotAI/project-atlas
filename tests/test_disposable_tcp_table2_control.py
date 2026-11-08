"""Alternative native TCP table is diagnostic only."""
import os

import pytest

from scripts.observation_runtime.disposable_tcp_table2_control import inspect


@pytest.mark.skipif(os.name != 'nt', reason='Windows native IP Helper required')
def test_alternate_native_table_never_authorizes():
    result = inspect()
    assert result['schema'] == 'ATLAS_TCP_TABLE2_CONTROL_V1'
    assert result['socket_accepting'] is True
    assert result['table2_count'] >= 1
    assert isinstance(result['table2_states'], list)
    assert isinstance(result['owner_pid_states'], list)
    assert result['endpoints_redacted'] is True
    assert result['operational_listener_accepted'] is False
    assert result['financial_authorized'] is False
