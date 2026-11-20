"""Existing-listener read-only control never confers Atlas acceptance."""
import os

import pytest

from scripts.observation_runtime.disposable_existing_listener_state_control import inspect


@pytest.mark.skipif(os.name != 'nt', reason='Windows listener control')
def test_existing_listener_control_redacts_endpoints_and_authority():
    result = inspect()
    assert result['schema'] == 'ATLAS_EXISTING_LISTENER_STATE_CONTROL_V1'
    assert result['endpoints_redacted'] is True
    assert result['operational_listener_accepted'] is False
    assert result['financial_authorized'] is False
    assert isinstance(result['listener_count'], int)
    assert isinstance(result['samples'], list)
    assert sum(result['address_classes'].values()) == result['listener_count']
    assert sum(result['owner_classes'].values()) == result['listener_count']
    for item in result['samples']:
        assert set(item) == {'address_class', 'owner_class', 'process_class', 'nettcp_state', 'native_error', 'native_states', 'owner_match'}
