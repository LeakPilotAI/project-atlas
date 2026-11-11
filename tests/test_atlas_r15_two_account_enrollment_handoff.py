"""R15 offline two-account handoff: synthetic roots are never native proof."""
import copy
import json
from pathlib import Path

import pytest

from app.services.paper_financial_replay import digest, validate_manifest
from app.services.quality_dips_autonomous_enrollment import validate_enrollment as qd_validate
from app.services.perp_operational_contract import validate_enrollment as perp_validate
from scripts.observation_runtime import atlas_r15_two_account_enrollment_handoff as handoff
from scripts.observation_runtime.atlas_independent_ntp_clock import SOURCE
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    ARTIFACT, SELECTED_HEAD, SELECTED_SHA, RECEIPT_SHA,
)


def sample():
    # Existing archived source is digest-pinned but provides no authority.
    original = handoff.legacy_proposal()
    roots = {
        'schema': 'ATLAS_TWO_LANE_EXISTING_NATIVE_ROOT_PRE_ENROLLMENT_V1',
        'native_root_total': 12, 'native_root_ids_verified': 12,
        'existing_empty_root_namespaces': 12,
        'all_twelve_distinct_and_empty': True,
        'operator_account_enrollment_verified': False,
        'writer_ownership_verified': False,
        'native_activation_record_verified': False,
        'financial_inception_verified': False,
        'paper_start_authorized': False,
        'live_trading_authorized': False,
        'lanes': {},
    }
    for lane, item in original['accounts'].items():
        enrollment = item['native_enrollment_draft']
        roots['lanes'][lane] = {
            'epoch': enrollment['epoch'],
            'roots': {
                role: {'path': r['path'], 'native_id': list(r['native_id']),
                       'native_identity_verified': True,
                       'existing_empty_namespace_verified': True}
                for role, r in enrollment['resources'].items()
            },
        }
    selected = {
        'revision': 14,
        'selected_release': '2c79a8d846d6b33669008114732ae5896153812a',
        'selected_native_head': SELECTED_HEAD,
        'selected_native_record_sha256': SELECTED_SHA,
        'installed_receipt_sha256': RECEIPT_SHA,
        'financial_authority': False,
        'independent_live_financial_clock_lease_accepted': False,
    }
    return original, selected, roots


def test_original_two_account_proposal_is_byte_pinned():
    p = handoff.LEGACY
    assert p.is_file()
    assert handoff.legacy_proposal()['status'].endswith('NOT_ACCEPTED_OR_AUTHORIZED')


def test_historical_draft_change_refused_before_any_native_action(tmp_path):
    p = tmp_path / 'forged.json'
    p.write_bytes(handoff.LEGACY.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='DIGEST_CHANGED'):
        handoff.legacy_proposal(p)


def test_r15_two_lanes_rebound_structurally_without_account_authority():
    original, selected, roots = sample()
    frozen = copy.deepcopy((original, selected, roots))
    proposal = handoff.build_handoff(original, selected=selected, roots=roots)
    assert (original, selected, roots) == frozen
    assert proposal['status'] == 'TWO_LANE_R15_STRUCTURAL_REBIND_ONLY_NEVER_ACCEPTED'
    assert proposal['native_root_count_handle_verified'] == 12
    assert proposal['selected_r15_artifact_digest'] == ARTIFACT
    assert proposal['original_historical_release_digest'] != ARTIFACT
    assert set(proposal['accounts']) == {'QUALITY_DIPS', 'HYPERLIQUID'}
    assert proposal['filesystem_mutations'] == proposal['network_requests'] == 0
    assert proposal['financial_operating_gates_accepted'] == 0
    for key in ('account_enrollment_accepted', 'both_financial_inceptions_published',
                'native_operator_activation_present',
                'native_current_quality_dips_source_accepted',
                'native_current_hyperliquid_source_accepted',
                'paper_start_authorized', 'live_trading_authorized'):
        assert proposal[key] is False
    for lane, item in proposal['accounts'].items():
        manifest = item['provisional_r15_parameters']
        e = item['provisional_r15_native_enrollment_unaccepted']
        report_scope = item['provisional_report_scope_unaccepted']
        assert manifest['release'] == e['release_digest'] == ARTIFACT
        assert digest(manifest) == e['inception_digest'] == item['provisional_inception_digest']
        assert report_scope['policy_digest'] == digest(manifest)
        assert e['clock_source'] == SOURCE
        assert manifest['opened_at'] == original['accounts'][lane]['parameters']['opened_at']
        assert item['opened_at_is_historical_stale_not_new_inception'] is True
        assert item['existing_native_root_identity_matched'] is True
        assert item['parameters_structurally_valid_not_current'] is True
        assert item['real_enrollment_accepted'] is False
        assert item['writer_process_observed_and_leased'] is False
        assert item['account_fee_entitlement_verified'] is False
        assert item['financial_inception_published'] is False
        assert item['operational_source_rights_accepted'] is False
        assert e['writers'] is None and e['acceptance_id'] is None
        validate_manifest(manifest)
        validator = qd_validate if lane == 'QUALITY_DIPS' else perp_validate
        with pytest.raises(ValueError):
            validator(e)


@pytest.mark.parametrize('damage', [
    'source_accepted','source_financial_inception','source_provider_approved',
    'source_release_already_r15','source_writer_forged',
    'source_acceptance_forged','source_policy_changed',
    'source_parameter_digest','source_manifest_older_release',
    'source_double_epoch','source_report_scope_changed',
    'root_missing','root_occupied','root_duplicate_fileid','root_tampered_fileid',
    'root_foreign_path','root_missing_role','root_forged_authority',
    'wrong_selected_head','wrong_selected_release','selected_financial_claim',
    'selected_clock_authority_claim',
])
def test_r15_handoff_never_accepts_stale_fake_or_modified_inputs(damage):
    original, selected, roots = sample()
    qd = original['accounts']['QUALITY_DIPS']
    hl = original['accounts']['HYPERLIQUID']
    if damage == 'source_accepted':original['enrollment_accepted'] = True
    elif damage == 'source_financial_inception':original['account_inception_authorized'] = True
    elif damage == 'source_provider_approved':original['provider_check_authorized'] = True
    elif damage == 'source_release_already_r15':
        original['selected_release_artifact_digest'] = ARTIFACT
    elif damage == 'source_writer_forged':
        qd['native_enrollment_draft']['writers'] = {'decision': 'SYNTHETIC'}
    elif damage == 'source_acceptance_forged':
        qd['native_enrollment_draft']['acceptance_id'] = 'FAKE'
    elif damage == 'source_policy_changed':
        qd['parameters']['autonomous_policy']['mos_thresholds'] = [1,2,3]
    elif damage == 'source_parameter_digest':
        hl['parameters_digest'] = '0' * 64
    elif damage == 'source_manifest_older_release':
        qd['parameters']['release'] = ARTIFACT
    elif damage == 'source_double_epoch':
        qd['native_enrollment_draft']['epoch'] = hl['native_enrollment_draft']['epoch']
    elif damage == 'source_report_scope_changed':
        hl['report_scope_draft']['policy_digest'] = '0' * 64
    elif damage == 'root_missing':
        roots['native_root_ids_verified'] = 11
    elif damage == 'root_occupied':
        roots['lanes']['QUALITY_DIPS']['roots']['source']['existing_empty_namespace_verified'] = False
    elif damage == 'root_duplicate_fileid':
        roots['lanes']['HYPERLIQUID']['roots']['source']['native_id'] = (
            roots['lanes']['QUALITY_DIPS']['roots']['source']['native_id'])
        hl['native_enrollment_draft']['resources']['source']['native_id'] = (
            roots['lanes']['HYPERLIQUID']['roots']['source']['native_id'])
    elif damage == 'root_tampered_fileid':
        roots['lanes']['HYPERLIQUID']['roots']['control']['native_id'] = [1,2,3]
    elif damage == 'root_foreign_path':
        roots['lanes']['QUALITY_DIPS']['roots']['source']['path'] = 'D:\\foreign'
    elif damage == 'root_missing_role':
        roots['lanes']['HYPERLIQUID']['roots'].pop('custody')
    elif damage == 'root_forged_authority':
        roots['native_activation_record_verified'] = True
    elif damage == 'wrong_selected_head':
        selected['selected_native_head'] = '0' * 64
    elif damage == 'wrong_selected_release':
        selected['selected_release'] = 'UNKNOWN'
    elif damage == 'selected_financial_claim':
        selected['financial_authority'] = True
    elif damage == 'selected_clock_authority_claim':
        selected['independent_live_financial_clock_lease_accepted'] = True
    with pytest.raises((ValueError,KeyError,TypeError)):
        handoff.build_handoff(original,selected=selected,roots=roots)


def test_r15_handoff_synthetic_root_roster_does_not_create_files(tmp_path):
    original, selected, roots = sample()
    before = list(tmp_path.iterdir())
    handoff.build_handoff(original,selected=selected,roots=roots)
    assert list(tmp_path.iterdir()) == before


def test_r15_handoff_cannot_relabel_incomplete_draft_as_enrolled():
    original,selected,roots = sample()
    res = handoff.build_handoff(original,selected=selected,roots=roots)
    for lane in ('QUALITY_DIPS','HYPERLIQUID'):
        assert len(res['accounts'][lane]['required_live_commissioning_inputs']) == 5
        assert all(res['accounts'][lane]['provisional_r15_native_enrollment_unaccepted'].get(k) is None
                   for k in ('writers','acceptance_id'))
    assert res['financial_operating_gates_accepted'] == 0
