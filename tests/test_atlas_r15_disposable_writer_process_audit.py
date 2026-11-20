"""Selected installed R15 Windows self/parent process identity refusal tests.

No financial enrollment, provider connection, process discovery or live orders.
"""
import copy
import ntpath
import os
import sys
from pathlib import Path

import pytest

from scripts.observation_runtime import atlas_r15_disposable_writer_process_audit as audit
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    SELECTED_HEAD,
)


def specimen():
    root = audit.RELEASE
    image = str(root / "python/python.exe")
    source = {
        "personal_writer_self_binding_probe":
            str(root / "scripts/observation_runtime/personal_writer_self_binding_probe.py"),
        "quality_dips_read_service":
            str(root / "scripts/observation_runtime/quality_dips_read_service.py"),
        "personal_version_safe_release_clock":
            str(root / "scripts/observation_runtime/personal_version_safe_release_clock.py"),
    }
    child = {
        "schema": "ATLAS_SELECTED_R15_NATIVE_TEMPORARY_PROCESS_SELF_OBSERVATION_V1",
        "self_binding": {
            "schema": "ATLAS_PERSONAL_WRITER_SELF_BINDING_PROBE_V1",
            "expected_executable": image,
            "observed_process": {
                "pid": 12345, "creation_filetime": 134388500000000000,
                "image": image,
            },
            "installed_executable_matched": True,
            "enrolled_writer_verified": False,
            "ownership_lease_issued": False,
            "paper_start_authorized": False,
        },
        "installed_source_paths": source,
        "selected_clock_source_head": SELECTED_HEAD,
        "financial_account_enrolled": False,
        "writer_ownership_lease_issued": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }
    parent = {
        "creation_filetime": 134388500000000000,
        "image": image,
    }
    return child, parent


def test_native_windows_process_qualification_only_confirms_disposable_process():
    child, parent = specimen()
    copied = copy.deepcopy((child, parent))
    result = audit.validate_report(
        child=child, native_pid=12345, parent=parent,
        release=audit.RELEASE, expected_head=SELECTED_HEAD)
    assert (child, parent) == copied
    assert result["status"] == (
        "INSTALLED_R15_SHORT_LIVED_PROCESS_SELF_AND_PARENT_HANDLE_AGREE")
    assert result["native_module_paths_verified"] == 3
    assert result["independent_parent_windows_handle_identity_agreed"] is True
    assert result["observed_expired_disposable_child_pid"] == 12345
    assert result["native_writer_identity_enrollment_usable"] is False
    for flag in (
        "real_writer_process_currently_enrolled", "financial_account_activated",
        "financial_start_authorized", "live_trading_authorized"):
        assert result[flag] is False
    assert result["provider_requests"] == result["native_account_mutations"] == 0


@pytest.mark.parametrize("damage", [
    "wrong_selected_head", "wrong_child_schema", "unexpected_field",
    "missing_native_source_module", "workspace_source_substituted",
    "other_native_release_module", "wrong_binding_schema",
    "wrong_installed_executable", "missing_installed_match",
    "forged_writer_enrollment", "forged_owner_lease", "forged_paper_start",
    "forged_live_order", "forged_financial_account",
    "other_windows_parent_image", "other_windows_self_image",
    "wrong_parent_creation", "negative_parent_creation",
    "wrong_child_creation", "different_pid", "noninteger_pid",
    "mismatched_selected_executable", "absent_process_identity",
])
def test_native_r15_parent_handle_self_bind_rejects_forgery(damage):
    child, parent = specimen()
    pid = 12345
    if damage == "wrong_selected_head":
        child["selected_clock_source_head"] = "0" * 64
    elif damage == "wrong_child_schema":
        child["schema"] = "UNVERIFIED"
    elif damage == "unexpected_field":
        child["passed_financial_gate"] = True
    elif damage == "missing_native_source_module":
        child["installed_source_paths"].pop("quality_dips_read_service")
    elif damage == "workspace_source_substituted":
        child["installed_source_paths"]["quality_dips_read_service"] = (
            r"D:\Work\Project Atlas\scripts\observation_runtime\quality_dips_read_service.py")
    elif damage == "other_native_release_module":
        child["installed_source_paths"]["personal_version_safe_release_clock"] = (
            r"D:\AtlasRuntime\releases\oldrelease\scripts\observation_runtime\personal_version_safe_release_clock.py")
    elif damage == "wrong_binding_schema":
        child["self_binding"]["schema"] = "OTHER"
    elif damage == "wrong_installed_executable":
        child["self_binding"]["expected_executable"] = r"D:\Python\python.exe"
    elif damage == "missing_installed_match":
        child["self_binding"]["installed_executable_matched"] = False
    elif damage == "forged_writer_enrollment":
        child["self_binding"]["enrolled_writer_verified"] = True
    elif damage == "forged_owner_lease":
        child["writer_ownership_lease_issued"] = True
    elif damage == "forged_paper_start":
        child["self_binding"]["paper_start_authorized"] = True
    elif damage == "forged_live_order":
        child["live_trading_authorized"] = True
    elif damage == "forged_financial_account":
        child["financial_account_enrolled"] = True
    elif damage == "other_windows_parent_image":
        parent["image"] = r"D:\Work\untrusted.exe"
    elif damage == "other_windows_self_image":
        child["self_binding"]["observed_process"]["image"] = r"D:\Work\untrusted.exe"
    elif damage == "wrong_parent_creation":
        parent["creation_filetime"] += 1
    elif damage == "negative_parent_creation":
        parent["creation_filetime"] = -1
    elif damage == "wrong_child_creation":
        child["self_binding"]["observed_process"]["creation_filetime"] += 1
    elif damage == "different_pid":
        pid += 1
    elif damage == "noninteger_pid":
        pid = "12345"
    elif damage == "mismatched_selected_executable":
        child["self_binding"]["observed_process"]["image"] = (
            r"D:\AtlasRuntime\releases\other\python\python.exe")
    elif damage == "absent_process_identity":
        child["self_binding"]["observed_process"] = None
    with pytest.raises((ValueError, TypeError, KeyError)):
        audit.validate_report(
            child=child, native_pid=pid, parent=parent,
            release=audit.RELEASE, expected_head=SELECTED_HEAD)


@pytest.mark.skipif(sys.platform != "win32", reason="Genuine Windows PROCESS HANDLE required")
def test_real_installed_r15_short_lived_process_self_and_parent_handle():
    actual = audit.inspect()
    assert actual["schema"] == audit.SCHEMA
    assert actual["child_exited_and_expired"] is True
    assert actual["parent_reverified_selector_after_exit"] is True
    assert actual["selected_native_head"] == SELECTED_HEAD
    assert actual["native_module_paths_verified"] == 3
    assert actual["child_owns_installed_selected_release"] is True
    assert actual["independent_parent_windows_handle_identity_agreed"] is True
    assert actual["native_writer_identity_enrollment_usable"] is False
    assert actual["real_writer_process_currently_enrolled"] is False
    assert actual["financial_account_activated"] is False
    assert actual["financial_start_authorized"] is False
    assert actual["live_trading_authorized"] is False
    assert actual["provider_requests"] == 0
    assert actual["native_account_mutations"] == 0


def _sample_native_twelve_root_handles():
    from scripts.observation_runtime.personal_existing_native_resource_evidence import ROLES

    expected = {
        'schema': 'ATLAS_TWO_LANE_EXISTING_NATIVE_ROOT_PRE_ENROLLMENT_V1',
        'native_root_total': 12, 'native_root_ids_verified': 12,
        'existing_empty_root_namespaces': 12,
        'all_twelve_distinct_and_empty': True,
        'lanes': {},
    }
    roster = []
    index = 0
    for lane in ('HYPERLIQUID', 'QUALITY_DIPS'):
        roots = {}
        for role in ROLES:
            index += 1
            path = rf'D:\AtlasPaper\{lane}\synthetic-only\{role}'
            row = {
                'path': path, 'native_id': [1234, 5678, index],
                'native_identity_verified': True,
                'existing_empty_namespace_verified': True,
            }
            roots[role] = row
            roster.append({
                'lane': lane, 'role': role, 'path': path,
                'native_id': list(row['native_id']),
            })
        expected['lanes'][lane] = {'roots': roots, 'epoch': 'synthetic-only'}
    image = str(audit.RELEASE / 'python/python.exe')
    child = {
        'schema': 'ATLAS_R15_INSTALLED_EXISTING_12_ROOT_HANDLES_LIFETIME_V1',
        'installed_self': {
            'pid': 12345, 'creation_filetime': 134388500000000000,
            'image': image,
        },
        'selected_native_head': SELECTED_HEAD,
        'opened_first': copy.deepcopy(roster),
        'rechecked_before_exit': copy.deepcopy(roster),
        'financial_account_enrolled': False,
        'writer_lease_issued': False,
        'financial_paper_start': False,
        'live_trading': False,
        'native_files_created': 0,
        'provider_calls': 0,
    }
    parent = {
        'image': image,
        'creation_filetime': 134388500000000000,
    }
    return child, expected, parent


def test_selected_r15_real_native_twelve_root_handle_identity_contract_is_not_enrollment():
    child, roots, parent = _sample_native_twelve_root_handles()
    before = copy.deepcopy((child, roots, parent))
    r = audit.verify_root_handle_lifetime(
        child, expected_roots=roots, native_pid=12345, parent=parent)
    assert (child, roots, parent) == before
    assert r['status'] == 'INSTALLED_NATIVE_R15_TWELVE_READ_ONLY_ROOT_HANDLES_RECHECKED'
    assert r['actual_existing_native_roots_verified'] == 12
    assert r['root_handles_held_and_rechecked_in_same_process'] is True
    assert r['financial_writer_process_enrolled'] is False
    assert r['financial_writer_lease_active'] is False
    assert r['native_paper_account_inception'] is False
    assert r['paper_start_authorized'] is False
    assert r['real_money_order_authorized'] is False
    assert r['native_financial_files_written'] == 0
    assert r['market_provider_requests'] == 0


@pytest.mark.parametrize('damage',[
    'wrong_selected_head','unverified_native_roots','missing_role',
    'unexpected_role','native_root_was_nonempty','root_fileid_changed',
    'last_observation_changed','partial_root_list','duplicate_native_id',
    'duplicated_path','incorrect_lane','unexpected_extra_packet_field',
    'fake_financial_account','fake_financial_writer_lease','fake_financial_start',
    'fake_live_trade','pretend_native_file_write','pretend_provider_call',
    'parent_image_substituted','child_image_substituted','child_pid_changed',
    'parent_creation_changed','child_creation_changed','negative_creation',
    'invalid_child_pid','wrong_selected_native_release','missing_parent_identity',
])
def test_selected_r15_native_root_handle_continuity_refuses_incorrect_identity(damage):
    child, roots, parent = _sample_native_twelve_root_handles()
    pid = 12345
    if damage == 'wrong_selected_head':
        child['selected_native_head'] = '0' * 64
    elif damage == 'unverified_native_roots':
        roots['native_root_ids_verified'] = 11
    elif damage == 'missing_role':
        roots['lanes']['QUALITY_DIPS']['roots'].pop('source')
    elif damage == 'unexpected_role':
        roots['lanes']['QUALITY_DIPS']['roots']['extra'] = {}
    elif damage == 'native_root_was_nonempty':
        roots['lanes']['HYPERLIQUID']['roots']['projection'][
            'existing_empty_namespace_verified'] = False
    elif damage == 'root_fileid_changed':
        roots['lanes']['HYPERLIQUID']['roots']['report']['native_id'][2] += 1
    elif damage == 'last_observation_changed':
        child['rechecked_before_exit'][0]['native_id'][2] += 1
    elif damage == 'partial_root_list':
        child['opened_first'].pop()
    elif damage == 'duplicate_native_id':
        roots['lanes']['QUALITY_DIPS']['roots']['source']['native_id'] = (
            roots['lanes']['HYPERLIQUID']['roots']['source']['native_id'].copy())
        for row in child['opened_first']:
            if (row['lane'],row['role']) == ('QUALITY_DIPS','source'):
                row['native_id'] = roots['lanes']['QUALITY_DIPS']['roots']['source']['native_id'].copy()
        for row in child['rechecked_before_exit']:
            if (row['lane'],row['role']) == ('QUALITY_DIPS','source'):
                row['native_id'] = roots['lanes']['QUALITY_DIPS']['roots']['source']['native_id'].copy()
    elif damage == 'duplicated_path':
        other = roots['lanes']['HYPERLIQUID']['roots']['source']['path']
        roots['lanes']['QUALITY_DIPS']['roots']['source']['path'] = other
        for collection in ('opened_first','rechecked_before_exit'):
            for row in child[collection]:
                if (row['lane'],row['role']) == ('QUALITY_DIPS','source'):
                    row['path'] = other
    elif damage == 'incorrect_lane':
        child['opened_first'][0]['lane'] = 'QUALITY_DIPS'
    elif damage == 'unexpected_extra_packet_field':
        child['writer_identity_accepted'] = True
    elif damage == 'fake_financial_account':
        child['financial_account_enrolled'] = True
    elif damage == 'fake_financial_writer_lease':
        child['writer_lease_issued'] = True
    elif damage == 'fake_financial_start':
        child['financial_paper_start'] = True
    elif damage == 'fake_live_trade':
        child['live_trading'] = True
    elif damage == 'pretend_native_file_write':
        child['native_files_created'] = 1
    elif damage == 'pretend_provider_call':
        child['provider_calls'] = 1
    elif damage == 'parent_image_substituted':
        parent['image'] = r'C:\other\python.exe'
    elif damage == 'child_image_substituted':
        child['installed_self']['image'] = r'D:\other\python.exe'
    elif damage == 'child_pid_changed':
        child['installed_self']['pid'] += 1
    elif damage == 'parent_creation_changed':
        parent['creation_filetime'] += 1
    elif damage == 'child_creation_changed':
        child['installed_self']['creation_filetime'] += 1
    elif damage == 'negative_creation':
        child['installed_self']['creation_filetime'] = -1
    elif damage == 'invalid_child_pid':
        pid = '12345'
    elif damage == 'wrong_selected_native_release':
        child['installed_self']['image'] = r'D:\AtlasRuntime\releases\other\python\python.exe'
    elif damage == 'missing_parent_identity':
        parent.pop('creation_filetime')
    with pytest.raises((ValueError,TypeError,KeyError)):
        audit.verify_root_handle_lifetime(
            child, expected_roots=roots, native_pid=pid, parent=parent)


@pytest.mark.skipif(sys.platform != 'win32',reason='Genuine R15 Windows native resource handles required')
def test_actual_r15_installed_child_holds_twelve_existing_paper_root_handles_only():
    # Runs one bounded below-normal disposable child; no account files or services.
    result = audit.inspect_two_lane_native_root_handles()
    assert result['actual_existing_native_roots_verified'] == 12
    assert result['root_handles_held_and_rechecked_in_same_process'] is True
    assert result['sample_count_while_process_alive'] == 3
    assert result['child_exited_and_handles_closed'] is True
    assert result['all_twelve_root_ids_unchanged_after_exit'] is True
    assert result['financial_writer_process_enrolled'] is False
    assert result['financial_writer_lease_active'] is False
    assert result['native_paper_account_inception'] is False
    assert result['paper_start_authorized'] is False
    assert result['real_money_order_authorized'] is False
    assert result['native_financial_files_written'] == 0
    assert result['market_provider_requests'] == 0
