"""Diagnostic source-pin refusals; never enroll or initialize an account."""
import json

import pytest

from scripts.observation_runtime import personal_commissioning_preflight as preflight


@pytest.mark.parametrize('expected,changed,accepted', [(None,False,False),('a'*40,False,True),('b'*40,False,False),('a'*40,True,True)])
def test_explicit_reviewed_source_and_dirty_tree_are_separate_checks(monkeypatch, capsys, expected, changed, accepted):
    args = ['preflight','--json']+(['--expected-source',expected] if expected else [])
    monkeypatch.setattr('sys.argv', args)
    def git(command, **kwargs):
        tail = command[1:]
        if tail == ['branch','--show-current']: return preflight.EXPECTED_BRANCH+'\n'
        if tail == ['rev-parse','HEAD']: return 'a'*40+'\n'
        if tail == ['status','--porcelain','--untracked-files=no']: return ' M source.py\n' if changed else ''
        pytest.fail('unexpected subprocess')
    monkeypatch.setattr(preflight.subprocess, 'check_output', git)
    assert preflight.main() == 2  # No native activation is supplied by a source pin.
    report = json.loads(capsys.readouterr().out)
    checks = {item['check']:item['status'] for item in report['checks']}
    assert checks['SOURCE_CHECKPOINT'] == ('PASS' if accepted else 'BLOCKED')
    assert checks['TRACKED_SOURCE_UNCHANGED'] == ('BLOCKED' if changed else 'PASS')
    assert report['financial_mutations'] is report['pilot_started'] is False


@pytest.mark.parametrize('args', [['--expected-source','HEAD'], ['--activation-root',r'C:\other'],
                                ['--activation-root',r'D:\AtlasCustody\PersonalPaper\..\foreign']])
def test_unreviewed_aliases_and_foreign_activation_paths_refuse(monkeypatch, args):
    monkeypatch.setattr('sys.argv', ['preflight', *args])
    with pytest.raises(SystemExit) as result: preflight.main()
    assert result.value.code == 2


def test_scope_claims_never_substitute_native_financial_or_runtime_proof(monkeypatch, capsys):
    monkeypatch.setattr('sys.argv', ['preflight', '--json', '--expected-source', 'a'*40])
    def git(command, **kwargs):
        tail = command[1:]
        if tail == ['branch','--show-current']: return preflight.EXPECTED_BRANCH+'\n'
        if tail == ['rev-parse','HEAD']: return 'a'*40+'\n'
        if tail == ['status','--porcelain','--untracked-files=no']: return ''
        pytest.fail('unexpected subprocess')
    monkeypatch.setattr(preflight.subprocess, 'check_output', git)
    original = preflight.json.loads
    def injected_scope(text):
        scope = original(text)
        scope['financial_publication_attempted'] = True
        scope['runtime_consumable'] = True
        return scope
    monkeypatch.setattr(preflight.json, 'loads', injected_scope)
    assert preflight.main() == 2
    report = original(capsys.readouterr().out)
    checks = {row['check']: row['status'] for row in report['checks']}
    assert checks['SOURCE_CHECKPOINT'] == 'PASS'
    assert checks['TRACKED_SOURCE_UNCHANGED'] == 'PASS'
    assert checks['FINANCIAL_INCEPTION'] == 'BLOCKED'
    assert checks['RUNTIME_AUTHORIZATION'] == 'BLOCKED'
    assert report['pilot_started'] is False


def test_preflight_native_custody_inventory_does_not_authorize(monkeypatch, capsys):
    import scripts.observation_runtime.personal_installation_preflight as native_mod
    monkeypatch.setattr('sys.argv', ['preflight', '--json'])
    monkeypatch.setattr(preflight.subprocess, 'check_output',
                        lambda command, **kwargs: {'branch': 'chatgpt/atlas-rebuild-v1'}.get('branch', '')
                        if command[1:] == ['branch', '--show-current'] else '')
    monkeypatch.setattr(native_mod, 'inspect_native_personal_installation', lambda: {
        'custody_parent_exists': True, 'personal_parent_exists': True,
        'native_activation_record_verified': False,
        'operator_lease_verified': False,
        'forward_financial_write_authorized': False})
    assert preflight.main() == 2
    report = json.loads(capsys.readouterr().out)
    checks = {row['check']: row['status'] for row in report['checks']}
    assert checks['NATIVE_CUSTODY_PARENTS'] == 'PASS'
    assert checks['ACTIVATION_NATIVE_VERIFIED'] == 'BLOCKED'
    assert report['native_custody_inventory']['forward_financial_write_authorized'] is False
    assert report['pilot_started'] is False


def test_optional_real_clock_probe_is_not_lease_or_financial_authority(monkeypatch, capsys):
    import scripts.observation_runtime.personal_clock_gate_probe as clock_mod
    monkeypatch.setattr('sys.argv', ['preflight', '--json', '--check-native-clock'])
    monkeypatch.setattr(preflight.subprocess, 'check_output', lambda command, **kwargs: '')
    monkeypatch.setattr(clock_mod, 'inspect_personal_clock_gate', lambda: {
        'trusted_clock_verified_for_probe': True, 'uncertainty_ms': 350,
        'native_activation_verified': False, 'operator_lease_verified': False,
        'forward_financial_write_authorized': False, 'live_order_authorized': False})
    assert preflight.main() == 2
    report = json.loads(capsys.readouterr().out)
    checks = {row['check']: row['status'] for row in report['checks']}
    assert checks['NATIVE_CLOCK_PROBE'] == 'PASS'
    assert checks['ACTIVATION_NATIVE_VERIFIED'] == 'BLOCKED'
    assert checks['RUNTIME_AUTHORIZATION'] == 'BLOCKED'
    assert report['native_clock_probe']['uncertainty_ms'] == 350
    assert report['financial_mutations'] is False


def test_optional_failed_clock_probe_blocks(monkeypatch, capsys):
    import scripts.observation_runtime.personal_clock_gate_probe as clock_mod
    monkeypatch.setattr('sys.argv', ['preflight', '--json', '--check-native-clock'])
    monkeypatch.setattr(preflight.subprocess, 'check_output', lambda command, **kwargs: '')
    monkeypatch.setattr(clock_mod, 'inspect_personal_clock_gate', lambda: {
        'trusted_clock_verified_for_probe': False, 'blocker': 'CLOCK_UNCERTAINTY_EXCEEDED'})
    assert preflight.main() == 2
    report = json.loads(capsys.readouterr().out)
    checks = {row['check']: row['status'] for row in report['checks']}
    assert checks['NATIVE_CLOCK_PROBE'] == 'BLOCKED'
    assert report['native_clock_probe']['blocker'] == 'CLOCK_UNCERTAINTY_EXCEEDED'


def test_native_qd_custody_directory_never_counts_as_operational_source(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr('sys.argv', ['preflight', '--json'])
    monkeypatch.setattr(preflight.subprocess, 'check_output', lambda command, **kwargs: '')
    original_path = preflight.Path
    # Use a real empty native-style custody root for the inventory check.
    original_is_dir = original_path.is_dir
    original_iterdir = original_path.iterdir
    def is_dir(path):
        if str(path).replace('\\', '/').endswith('AtlasCustody/QualityDips'):
            return True
        return original_is_dir(path)
    def iterdir(path):
        if str(path).replace('\\', '/').endswith('AtlasCustody/QualityDips'):
            return iter([tmp_path])
        return original_iterdir(path)
    monkeypatch.setattr(original_path, 'is_dir', is_dir)
    monkeypatch.setattr(original_path, 'iterdir', iterdir)
    assert preflight.main() == 2
    report = json.loads(capsys.readouterr().out)
    checks = {row['check']: row['status'] for row in report['checks']}
    assert checks['OPERATIONAL_QD_SOURCE_PUBLICATION'] == 'BLOCKED'
    assert report['quality_dips_custody_inventory']['ordinary_child_count'] == 1
    assert report['quality_dips_custody_inventory']['operational_publication_verified'] is False
    assert report['pilot_started'] is False
