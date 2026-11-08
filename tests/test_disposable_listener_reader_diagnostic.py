"""Diagnostic must never promote observed sockets into operational authority."""
import os

import pytest

from scripts.observation_runtime.disposable_listener_reader_diagnostic import inspect


@pytest.mark.skipif(os.name != 'nt', reason='Windows TCP reader diagnostic')
def test_disposable_listener_comparison_remains_nonoperational():
    result = inspect()
    assert result['schema'] == 'ATLAS_DISPOSABLE_LISTENER_READERS_V1'
    assert result['operational_listener_accepted'] is False
    assert result['financial_authorized'] is False
    assert result['cim_exit'] == 0
    assert result['ip_helper_error'] is None
    assert isinstance(result['netstat'], list)
    assert isinstance(result['ip_helper_rows'], list)
    assert result['port'] > 0 and result['expected_pid'] > 0
    assert result['so_acceptconn'] == 1
    assert result['netstat_exit'] == 0
    assert isinstance(result['netstat_scoped_raw'], list)
    assert result['nettcp_exit'] == 0
