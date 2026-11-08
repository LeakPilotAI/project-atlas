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
    with pytest.raises(ValueError, match='ACTIVATION_ACCOUNTS_OR_RELEASE_MISMATCH'):
        entry.commission(root='D:\\AtlasCustody\\PersonalPaper\\new', record_path=files[0],
                         policy_path=files[1], release_digest='a'*64, accounts_path=files[2],
                         expected_clock_source='source', runtime_id='runtime')


def test_valid_account_digest_mapping_reaches_clock_and_publisher(tmp_path, monkeypatch):
    import json
    accounts = {'QUALITY_DIPS': 'b'*64, 'HYPERLIQUID': 'c'*64}
    record = {'accounts': accounts, 'release_digest': 'a'*64}
    paths = []
    for name, value in [('record', record), ('policy', {}), ('accounts', accounts)]:
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
    result = entry.commission(root='D:\\AtlasCustody\\PersonalPaper\\new',
        record_path=paths[0], policy_path=paths[1], release_digest='a'*64,
        accounts_path=paths[2], expected_clock_source='source', runtime_id='runtime')
    assert result['status'] == 'NATIVE_VERIFIED'
    assert events == ['clock', 'publish', 'revoke']
