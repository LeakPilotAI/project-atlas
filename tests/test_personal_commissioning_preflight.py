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
