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
