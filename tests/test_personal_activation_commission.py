import pytest
from scripts.observation_runtime import personal_activation_commission as entry


def test_activation_requires_explicit_inputs_before_native_write():
    with pytest.raises(ValueError, match='EXPLICIT_ACTIVATION_INPUTS_REQUIRED'):
        entry.commission(root='', record_path='', policy_path='', release_digest='',
                         accounts_path='', expected_clock_source='', runtime_id='')
    with pytest.raises(ValueError, match='EXPLICIT_RELEASE_DIGEST_REQUIRED'):
        entry.commission(root='D:\\AtlasCustody\\PersonalPaper\\new', record_path='missing',
                         policy_path='missing', release_digest='wrong', accounts_path='missing',
                         expected_clock_source='source', runtime_id='runtime')


def test_activation_refuses_account_mismatch_before_clock_or_native(tmp_path, monkeypatch):
    import json
    files = []
    for name, data in [('record', {'accounts': ['QUALITY_DIPS'], 'release_digest': 'a'*64}),
                       ('policy', {}), ('accounts', {'QUALITY_DIPS': 'b'*64, 'HYPERLIQUID': 'c'*64})]:
        path = tmp_path / name
        path.write_text(json.dumps(data))
        files.append(str(path))
    monkeypatch.setattr(entry, 'LocalWindowsClock', lambda **kwargs: pytest.fail('clock acquired'))
    with pytest.raises(ValueError, match='BOTH_NATIVE_ACCOUNT_ENROLLMENTS_REQUIRED'):
        entry.commission(root='D:\\AtlasCustody\\PersonalPaper\\new', record_path=files[0],
                         policy_path=files[1], release_digest='a'*64, accounts_path=files[2],
                         expected_clock_source='source', runtime_id='runtime')


def test_valid_account_digest_mapping_reaches_clock_and_publisher(tmp_path, monkeypatch):
    import json
    from app.services.paper_financial_replay import digest
    accounts = {'QUALITY_DIPS': 'b'*64, 'HYPERLIQUID': 'c'*64}
    from app.services.personal_paper_runtime import validate_policy
    import json as _json
    from pathlib import Path as _Path
    policy = _json.loads((_Path(__file__).resolve().parents[1] / 'docs/ATLAS_PERSONAL_PAPER_RELEASE_POLICY.json').read_text())
    record = {'accounts': accounts, 'release_digest': 'a'*64, 'policy_digest': digest(validate_policy(policy)), 'origin': 'LOCAL_OPERATOR', 'schema': 'ATLAS_PERSONAL_ACTIVATION_V1', 'actions': ['READ_ONLY']}
    paths = []
    for name, value in [('record', record), ('policy', policy), ('accounts', accounts)]:
        path = tmp_path / name
        path.write_text(json.dumps(value))
        paths.append(str(path))
    events = []
    class Clock:
        def __init__(self, **kwargs): events.append('clock')
        def revoke(self): events.append('revoke')
    monkeypatch.setattr(entry, 'LocalWindowsClock', Clock)
    monkeypatch.setattr(entry, 'current_sid', lambda: 'WINDOWS_OPERATOR')
    def publish(**kwargs):
        events.append('publish')
        assert kwargs['accounts'] == accounts
        assert kwargs['operator_id'] == 'WINDOWS_OPERATOR'
        return {'status': 'NATIVE_VERIFIED'}
    monkeypatch.setattr(entry, 'publish_personal_activation', publish)
    with pytest.raises(ValueError, match='BOTH_NATIVE_ACCOUNT_ENROLLMENTS_REQUIRED'):
        entry.commission(root='D:\\AtlasCustody\\PersonalPaper\\new',
        record_path=paths[0], policy_path=paths[1], release_digest='a'*64,
        accounts_path=paths[2], expected_clock_source='source', runtime_id='runtime')
    assert events == []


def test_invalid_native_root_refused_before_reading_activation_files():
    with pytest.raises(ValueError, match='EXPLICIT_NATIVE_ACTIVATION_ROOT_REQUIRED'):
        entry.commission(root='C:\\Temp\\activation', record_path='missing', policy_path='missing',
                         release_digest='a'*64, accounts_path='missing',
                         expected_clock_source='source', runtime_id='runtime')


def test_enrollment_pair_must_be_supplied_together():
    with pytest.raises(ValueError, match='BOTH_NATIVE_ACCOUNT_ENROLLMENTS_REQUIRED'):
        entry.commission(root='D:\\AtlasCustody\\PersonalPaper\\new',
            record_path='missing', policy_path='missing', release_digest='a'*64,
            accounts_path='missing', expected_clock_source='source', runtime_id='runtime',
            qd_enrollment_path='missing')


def test_cli_requires_both_enrollment_paths():
    with pytest.raises(SystemExit) as exc:
        entry.main(['--root', 'D:\\AtlasCustody\\PersonalPaper\\new',
                    '--record-path', 'record', '--policy-path', 'policy',
                    '--release-digest', 'a'*64, '--accounts-path', 'accounts',
                    '--expected-clock-source', 'source', '--runtime-id', 'runtime'])
    assert exc.value.code == 2
