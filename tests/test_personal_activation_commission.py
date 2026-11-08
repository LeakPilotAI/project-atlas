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
                       ('policy', {}), ('accounts', ['QUALITY_DIPS', 'HYPERLIQUID'])]:
        path = tmp_path / name
        path.write_text(json.dumps(data))
        files.append(str(path))
    monkeypatch.setattr(entry, 'LocalWindowsClock', lambda **kwargs: pytest.fail('clock acquired'))
    with pytest.raises(ValueError, match='ACTIVATION_ACCOUNTS_OR_RELEASE_MISMATCH'):
        entry.commission(root='D:\\AtlasCustody\\PersonalPaper\\new', record_path=files[0],
                         policy_path=files[1], release_digest='a'*64, accounts_path=files[2],
                         expected_clock_source='source', runtime_id='runtime')
