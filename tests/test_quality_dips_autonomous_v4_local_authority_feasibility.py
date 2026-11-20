"""Do not mistake local synthetic witness/claimed approval for independent authority."""
import copy
import pytest
from app.services.quality_dips_autonomous_v4_local_authority_feasibility import inspect_local_v4_authority_feasibility


def test_local_authority_inventory_identifies_actual_missing_independence():
    report = inspect_local_v4_authority_feasibility()
    assert report['status'] == 'SOURCE_ONLY_BLOCKED'
    assert report['local_only_possible_in_principle'] is True
    assert report['local_only_independence_proven'] is False
    assert {r['role'] for r in report['candidate_roles']} == {
        'publisher', 'custody', 'financial_replay', 'native_reader'}
    assert all(r['missing'] for r in report['candidate_roles'])
    assert report['startup_authorized'] is False


@pytest.mark.parametrize('flags', [
    {'external_witness_accepted': True},
    {'provider_rights_accepted': True},
    {'native_protocol_accepted': True},
    {'external_witness_accepted': True, 'provider_rights_accepted': True,
     'native_protocol_accepted': True},
])
def test_claimed_acceptance_flags_never_upgrade_local_authority(flags):
    report = inspect_local_v4_authority_feasibility(**flags)
    assert report['independent_publisher_accepted'] is False
    assert report['independent_custody_accepted'] is False
    assert report['nonzero_v4_replay_accepted'] is False
    assert report['provider_rights_accepted'] is False
    assert report['startup_authorized'] is False
    assert report['production_authorized'] is False


@pytest.mark.parametrize('bad', [1, 'true', None, [], {}])
def test_non_boolean_claims_refused(bad):
    with pytest.raises(ValueError):
        inspect_local_v4_authority_feasibility(external_witness_accepted=bad)


def test_local_authority_inventory_cannot_be_mutated_across_calls():
    first = inspect_local_v4_authority_feasibility()
    first['candidate_roles'][0]['missing'] = ()
    assert inspect_local_v4_authority_feasibility()['candidate_roles'][0]['missing']