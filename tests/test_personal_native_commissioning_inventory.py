from scripts.observation_runtime.personal_native_commissioning_inventory import inspect


def test_inventory_is_read_only_and_never_authenticates_files(tmp_path):
    personal, qd = tmp_path / 'personal', tmp_path / 'qd'
    personal.mkdir()
    qd.mkdir()
    (personal / 'activation-test').mkdir()
    (personal / 'activation-test' / 'activation.json').write_text('{}')
    (qd / 'qd-root').mkdir()
    result = inspect(personal_parent=personal, qd_parent=qd)
    assert result['ordinary_activation_file_candidates'] == ['activation-test']
    assert result['quality_dips_child_count'] == 1
    assert result['native_activation_verified'] is False
    assert result['paper_start_authorized'] is False


def test_missing_parents_remain_unverified(tmp_path):
    result = inspect(personal_parent=tmp_path / 'missing', qd_parent=tmp_path / 'other')
    assert result['personal_parent_present'] is False
    assert result['account_enrollment_verified'] is False
