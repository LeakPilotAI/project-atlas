"""Bounded repeated native listener checks remain diagnostic only."""
import os

import pytest

from scripts.observation_runtime.disposable_repeated_native_listener_control import inspect


@pytest.mark.parametrize('rounds', [0, 6, True, -1])
def test_repeated_control_rejects_unbounded_rounds(rounds):
    with pytest.raises((ValueError, OSError)):
        inspect(rounds=rounds)


@pytest.mark.skipif(os.name != 'nt', reason='Windows native API required')
def test_repeated_control_redacts_endpoints_and_never_authorizes():
    result = inspect(rounds=2)
    assert result['endpoints_redacted'] is True
    assert result['operational_listener_accepted'] is False
    assert result['financial_authorized'] is False
    assert result['rounds'] == 2
    assert result['schema'] == 'ATLAS_REPEATED_NATIVE_LISTENER_CONTROL_V2'
    assert result['sample_count'] == len(result['samples'])
    for sample in result['samples']:
        assert set(sample) == {'cmdlet_initial_state', 'history'}
        assert len(sample['history']) == 2
        for observation in sample['history']:
            assert set(observation) == {'states', 'native_error', 'cmdlet_post_present', 'cmdlet_post_state'}
