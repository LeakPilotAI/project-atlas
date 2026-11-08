from scripts.observation_runtime import personal_writer_self_binding_probe as probe


def test_installed_writer_self_binding_matches_only_exact_image(monkeypatch):
    from scripts.observation_runtime import quality_dips_read_service
    monkeypatch.setattr(quality_dips_read_service, 'observe_self', lambda: {
        'pid': 42, 'creation_filetime': 123456, 'image': r'D:\AtlasRuntime\python\python.exe'})
    result = probe.inspect(expected_executable=r'D:\AtlasRuntime\python\python.exe')
    assert result['installed_executable_matched'] is True
    assert result['enrolled_writer_verified'] is False
    assert result['ownership_lease_issued'] is False
    assert result['paper_start_authorized'] is False


def test_installed_writer_self_binding_rejects_other_image(monkeypatch):
    from scripts.observation_runtime import quality_dips_read_service
    monkeypatch.setattr(quality_dips_read_service, 'observe_self', lambda: {
        'pid': 42, 'creation_filetime': 123456, 'image': r'C:\Python\python.exe'})
    assert probe.inspect(expected_executable=r'D:\AtlasRuntime\python\python.exe')['installed_executable_matched'] is False
