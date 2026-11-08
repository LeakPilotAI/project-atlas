"""Listener-class diagnostics do not confer operational acceptance."""
import os

import pytest

from scripts.observation_runtime.disposable_iphelper_table_classes import inspect


@pytest.mark.skipif(os.name != 'nt', reason='Windows native IP Helper required')
def test_native_table_classes_are_diagnostic_only():
    result = inspect()
    assert result['schema'] == 'ATLAS_DISPOSABLE_IPHELPER_TABLE_CLASS_V1'
    assert result['operational_listener_accepted'] is False
    assert result['financial_authorized'] is False
    assert result['port'] > 0 and result['expected_pid'] > 0
    for table_class in ('3', '4', '5'):
        assert result['tables'][table_class]['code'] == 0
        assert isinstance(result['tables'][table_class]['rows'], list)
