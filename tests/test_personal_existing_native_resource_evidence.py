from scripts.observation_runtime import personal_existing_native_resource_evidence as evidence


def test_existing_native_resources_missing_coordination_fail_closed(monkeypatch, tmp_path):
    base = tmp_path / 'epoch'
    custody = tmp_path / 'custody'
    from scripts.observation_runtime import personal_paper_inception
    from types import SimpleNamespace
    class Output:
        def __init__(self, path): self.path = path
        def __enter__(self):
            if self.path.endswith('coordination'):
                raise FileNotFoundError('coordination')
            self.root_handle = self.path
            return self
        def __exit__(self, *args): pass
    class Native:
        @staticmethod
        def file_identity(handle): return [1, 2, len(handle)]
    monkeypatch.setattr(personal_paper_inception, 'native_primitives',
                        lambda: SimpleNamespace(w=SimpleNamespace(WindowsOutput=Output), native=Native))
    result = evidence.inspect(base=base, custody=custody)
    assert result['all_six_verified'] is False
    assert result['resources']['coordination']['reason'] == 'FileNotFoundError'
    assert result['enrollment_accepted'] is False
    assert result['paper_start_authorized'] is False


def test_existing_native_resources_all_distinct_still_no_authority(monkeypatch, tmp_path):
    from scripts.observation_runtime import personal_paper_inception
    from types import SimpleNamespace
    class Output:
        def __init__(self, path): self.path = path
        def __enter__(self): self.root_handle = self.path; return self
        def __exit__(self, *args): pass
    class Native:
        @staticmethod
        def file_identity(handle): return [1, 2, sum(map(ord, handle))]
    monkeypatch.setattr(personal_paper_inception, 'native_primitives',
                        lambda: SimpleNamespace(w=SimpleNamespace(WindowsOutput=Output), native=Native))
    result = evidence.inspect(base=tmp_path / 'epoch', custody=tmp_path / 'custody')
    assert result['all_six_verified'] is True
    assert result['writer_ownership_verified'] is False
    assert result['financial_inception_authorized'] is False


def _make_two_lane_test_roots(tmp_path, monkeypatch, *, same_id=False):
    from types import SimpleNamespace
    from pathlib import Path
    import hashlib
    from scripts.observation_runtime import personal_paper_inception

    paths={}
    for lane in ('qd','hl'):
        base=tmp_path/lane/'epoch'
        custody=tmp_path/lane/'custody'
        for role in evidence.ROLES:
            path=custody if role=='custody' else base/role
            path.mkdir(parents=True,exist_ok=True)
        paths[lane]=(base,custody)
    class Output:
        def __init__(self,path):self.path=path
        def __enter__(self):
            self.root_handle=self.path
            return self
        def __exit__(self,*a):return False
    class Native:
        @staticmethod
        def file_identity(handle):
            if same_id:return [1,2,3]
            n=int(hashlib.sha256(handle.encode('utf-8')).hexdigest()[:12],16)
            return [1,2,n]
    monkeypatch.setattr(personal_paper_inception,'native_primitives',
        lambda:SimpleNamespace(w=SimpleNamespace(WindowsOutput=Output),native=Native))
    return paths


def _two_lane_report(roots):
    return evidence.inspect_two_lane_native_roots(
        qd_base=roots['qd'][0],qd_custody=roots['qd'][1],
        hl_base=roots['hl'][0],hl_custody=roots['hl'][1])


def test_two_lane_existing_twelve_windows_roots_are_not_activation(monkeypatch,tmp_path):
    paths=_make_two_lane_test_roots(tmp_path,monkeypatch)
    report=_two_lane_report(paths)
    assert report['native_root_total']==12
    assert report['native_root_ids_verified']==12
    assert report['existing_empty_root_namespaces']==12
    assert report['all_twelve_distinct_and_empty'] is True
    assert report['next_unmet_stage']==(
        'INDEPENDENT_ACCOUNT_ENROLLMENTS_WITH_ACCEPTED_WRITER_OWNERSHIP')
    for lane in ('QUALITY_DIPS','HYPERLIQUID'):
        assert len(report['lanes'][lane]['roots'])==6
        assert all(x['native_identity_verified'] for x in report['lanes'][lane]['roots'].values())
    for key in ('operator_account_enrollment_verified','writer_ownership_verified',
                'native_activation_record_verified','financial_inception_verified',
                'current_scanner_source_issuer_accepted','paper_start_authorized',
                'live_trading_authorized','activation_publication_can_precede_account_enrollment'):
        assert report[key] is False
    assert report['source_archive_genesis_requires_existing_native_activation'] is True
    assert report['filesystem_writes']==0 and report['network_requests']==0


def test_two_lane_resource_identity_aliases_refuse_candidate_ready(monkeypatch,tmp_path):
    paths=_make_two_lane_test_roots(tmp_path,monkeypatch,same_id=True)
    report=_two_lane_report(paths)
    assert report['native_root_ids_verified']==12
    assert report['existing_empty_root_namespaces']==12
    assert report['all_twelve_distinct_and_empty'] is False
    assert report['operator_account_enrollment_verified'] is False
    assert report['paper_start_authorized'] is False


def test_two_lane_nonempty_source_refuses_pre_activation_namespace(monkeypatch,tmp_path):
    paths=_make_two_lane_test_roots(tmp_path,monkeypatch)
    source=paths['hl'][0]/'source'
    (source/'unaccepted.tmp').write_text('NOT AN ACCOUNT')
    report=_two_lane_report(paths)
    assert report['native_root_ids_verified']==12
    assert report['existing_empty_root_namespaces']==11
    assert report['all_twelve_distinct_and_empty'] is False
    assert report['lanes']['HYPERLIQUID']['roots']['source'][
        'existing_empty_namespace_verified'] is False
    assert (source/'unaccepted.tmp').read_text()=='NOT AN ACCOUNT'
    assert report['paper_start_authorized'] is False


def test_two_lane_missing_or_moved_native_root_refuses(monkeypatch,tmp_path):
    paths=_make_two_lane_test_roots(tmp_path,monkeypatch)
    (paths['qd'][0]/'coordination').rmdir()
    report=_two_lane_report(paths)
    assert report['native_root_ids_verified']==11
    assert report['all_twelve_distinct_and_empty'] is False
    assert report['lanes']['QUALITY_DIPS']['roots']['coordination'][
        'native_identity_verified'] is False
    assert report['native_activation_record_verified'] is False


def test_two_lane_reparse_custody_refuses_before_handle_read(monkeypatch,tmp_path):
    import os
    import pytest
    paths=_make_two_lane_test_roots(tmp_path,monkeypatch)
    custody=paths['hl'][1]
    custody.rmdir()
    try:
        os.symlink(paths['qd'][1],custody,target_is_directory=True)
    except OSError:
        pytest.skip('Windows symlink privilege not available')
    try:
        report=_two_lane_report(paths)
        assert report['all_twelve_distinct_and_empty'] is False
        assert report['lanes']['HYPERLIQUID']['roots']['custody'][
            'native_identity_verified'] is False
        assert report['paper_start_authorized'] is False
    finally:
        custody.unlink()
