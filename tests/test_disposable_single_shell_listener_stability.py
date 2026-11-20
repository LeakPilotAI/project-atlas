"""Single-shell listener inventory comparison remains bounded and read-only."""
import os

import pytest

from scripts.observation_runtime.disposable_single_shell_listener_stability import inspect


@pytest.mark.parametrize('rounds', [0, 1, 7, True, -1])
def test_single_shell_control_rejects_invalid_rounds(rounds):
    with pytest.raises((ValueError, OSError)):
        inspect(rounds=rounds)


@pytest.mark.skipif(os.name != 'nt', reason='Windows TCP cmdlet required')
def test_single_shell_control_redacts_identities_and_authority():
    result = inspect(rounds=2)
    assert result['schema'] == 'ATLAS_SINGLE_SHELL_LISTENER_STABILITY_V1'
    assert result['rounds'] == 2
    assert len(result['counts']) == 2
    assert len(result['adjacent_identity_overlap']) == 1
    assert 0 <= result['adjacent_identity_overlap'][0] <= min(result['counts'])
    assert result['endpoints_redacted'] is True
    assert result['operational_listener_accepted'] is False
    assert result['financial_authorized'] is False
