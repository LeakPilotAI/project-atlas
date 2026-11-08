"""Candidate source identities must be checked before source content is read."""
import os
from pathlib import Path

import pytest
from test_offline_candidate_packaging import candidate, fixture_root


def test_native_hard_link_source_is_not_read(tmp_path, monkeypatch):
    root, _ = fixture_root(tmp_path, monkeypatch)
    source = root / 'backend/app/example.py'
    alias = tmp_path / 'outside-source.py'
    os.link(source, alias)
    # Reproduce the previous Path.read_bytes boundary as a positive control.
    verified_reader = candidate.source_bytes
    monkeypatch.setattr(candidate, 'source_bytes', lambda root, name: (root / name).read_bytes())
    candidate.build(tmp_path / 'previous-read-boundary')
    monkeypatch.setattr(candidate, 'source_bytes', verified_reader)
    with pytest.raises(ValueError, match='Unsafe source identity'):
        candidate.build(tmp_path / 'candidate')
    assert alias.read_bytes() == b'VALUE = 1\n'


@pytest.mark.parametrize('name', ['../outside.py', '/outside.py', 'C:/outside.py', 'backend\\app\\example.py', 'backend/./app/example.py'])
def test_noncanonical_git_path_refuses_before_file_read(tmp_path, monkeypatch, name):
    _root, tracked = fixture_root(tmp_path, monkeypatch)
    outside = tmp_path / 'outside.py'
    outside.write_bytes(b'private synthetic control')
    tracked[:] = [name]
    with pytest.raises(ValueError, match='Unsafe source path'):
        candidate.build(tmp_path / 'candidate')


def test_file_replacement_between_metadata_and_open_refuses_before_read(tmp_path, monkeypatch):
    root, _ = fixture_root(tmp_path, monkeypatch)
    source = root / 'backend/app/example.py'
    original_open = os.open
    replaced = False
    def swapping_open(path, flags, *args, **kwargs):
        nonlocal replaced
        if Path(path) == source and not replaced:
            replacement = root / 'replacement.py'
            replacement.write_bytes(b'different synthetic source')
            os.replace(replacement, source)
            replaced = True
        return original_open(path, flags, *args, **kwargs)
    monkeypatch.setattr(candidate.os, 'open', swapping_open)
    with pytest.raises(ValueError, match='Source identity changed'):
        candidate.build(tmp_path / 'candidate')
    assert replaced

@pytest.mark.parametrize('kind', ['ancestor-reparse', 'file-symlink'])
def test_unsafe_metadata_refuses_before_any_content_open(tmp_path, monkeypatch, kind):
    import stat
    from types import SimpleNamespace

    root, _ = fixture_root(tmp_path, monkeypatch)
    target = root / ('backend' if kind == 'ancestor-reparse' else 'backend/app/example.py')
    original_stat = Path.lstat
    original_open = os.open
    def metadata(path, *args, **kwargs):
        value = original_stat(path, *args, **kwargs)
        if path == target:
            return SimpleNamespace(st_mode=value.st_mode if kind == 'ancestor-reparse' else stat.S_IFLNK | 0o777,
                                   st_nlink=1, st_file_attributes=0x400 if kind == 'ancestor-reparse' else 0)
        return value
    def no_source_open(path, *args, **kwargs):
        if Path(path).is_relative_to(root):
            raise AssertionError('Unsafe source content was opened')
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'lstat', metadata)
    monkeypatch.setattr(candidate.os, 'open', no_source_open)
    with pytest.raises(ValueError, match='Unsafe source identity'):
        candidate.source_bytes(root, 'backend/app/example.py')
