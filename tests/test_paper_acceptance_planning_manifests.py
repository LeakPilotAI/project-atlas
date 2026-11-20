"""Planning packets cannot masquerade as accepted runtime enrollment."""
import json
from pathlib import Path

import pytest
from app.services.unified_writer_roster import EXCLUSIONS, ROLES

DOCS=Path(__file__).resolve().parents[1]/'docs'
NAMES=['PAPER_B1_AUTONOMOUS_ACCEPTANCE_PACKET_V4_2026-10-26.json',
       'PAPER_C1_STATIC_ROSTER_ACCEPTANCE_V1_2026-10-26.json',
       'PAPER_D1_DEPENDENCY_ENROLLMENT_MANIFEST_V1_2026-10-26.json',
       'PAPER_E1_PROVIDER_READINESS_MANIFEST_V1_2026-10-26.json']


def read(index):return json.loads((DOCS/NAMES[index]).read_text(encoding='utf8'))


@pytest.mark.parametrize('index',range(4))
def test_planning_not_runtime_authority(index):
    value=read(index)
    assert value['status']=='PROPOSED_NOT_ACCEPTED'
    assert value['runtime_consumable'] is False and value['startup_authorized'] is False
    assert value['operational_action_authorized'] is False and value['gate_promotions']==0


def test_B1_separate_autonomous_account_scope_and_unassigned_independent_review():
    b=read(0)
    assert [(r['lane'],r['currency'],r['opening_simulated_cash']) for r in b['accounts']]==[
        ('QUALITY_DIPS','USD','1000'),('HYPERLIQUID','USDC','1000')]
    assert b['manual_per_trade_confirmation_required'] is False
    assert not b['legacy_adoption'] and not b['legacy_positions_assumed_closed']
    assert b['independent_acceptance'] is None
    assert b['reviewers_and_owners']['independent_B1_scope_reviewer']=='UNASSIGNED'


def test_C1_complete_static_roster_is_not_observed_ownership():
    value=read(1)
    assert set(value['roles'])==set(ROLES) and set(value['exclusions'])==set(EXCLUSIONS)
    for row in value['roles'].values():
        assert row['process_pid_creation_image'] is None and row['native_resource_identity'] is None
    assert value['reviewer']=='UNASSIGNED' and not value['read_only_actual_preflight_authorized']


@pytest.mark.parametrize('row',read(2)['dependencies'],ids=lambda row:row['dependency'])
def test_D1_exact_dependency_fields_without_installed_issuer(row):
    assert row['issuer']=='UNASSIGNED' and row['evidence_owner']=='UNASSIGNED'
    assert row['installation_location'].startswith('D:/')
    for key in ['purpose','trust_and_integrity_requirements','required_permissions','recovery_requirements','rollback_procedure']:
        assert row[key]
    assert row['operator_approval_required'] and not row['accepted']


@pytest.mark.parametrize('provider',read(3)['providers'],ids=lambda row:row['id'])
def test_E1_explicit_unaccepted_rights_and_current_provenance(provider):
    assert not provider['connection_authorized'] and not provider['subscription_activated']
    assert provider['rights_evidence'] is None and provider['request_budget'] is None
    assert provider['reviewer']=='UNASSIGNED' and provider['evidence_owner']=='UNASSIGNED'
    assert provider['rights_required'] and provider['timestamps'] and provider['provenance']
