from scripts.observation_runtime.quality_dips_source_inventory import inspect


def test_empty_child_is_not_publication(tmp_path):
    (tmp_path/'dated-source').mkdir()
    result = inspect(root=tmp_path)
    assert result['ordinary_child_count'] == 1
    assert result['children_with_direct_files'] == 0
    assert result['operational_publication_verified'] is False


def test_existing_file_is_not_publication_authority(tmp_path):
    child = tmp_path/'source'
    child.mkdir()
    (child/'publication.json').write_text('{}')
    result = inspect(root=tmp_path)
    assert result['children_with_direct_files'] == 1
    assert result['operational_publication_verified'] is False
