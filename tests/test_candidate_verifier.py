"""Read-only candidate verification never extracts or authorizes activation."""
import hashlib
import json
import stat
import zipfile

import pytest
from test_offline_candidate_packaging import candidate, fixture_root


def built(tmp_path, monkeypatch):
    fixture_root(tmp_path, monkeypatch)
    directory = tmp_path / 'candidate'
    digest = candidate.build(directory)
    return directory / 'atlas-source.zip', digest


def test_verified_archive_is_consistent_without_activation_or_extraction(tmp_path, monkeypatch):
    archive, digest = built(tmp_path, monkeypatch)
    before = {p.relative_to(tmp_path) for p in tmp_path.rglob('*')}
    result = candidate.verify_candidate(archive, expected_sha256=digest)
    assert result['supplied_bytes_consistent'] is True
    assert result['source_files'] >= 5
    assert result['source_authenticated'] is False
    assert result['installation_verified'] is False
    assert result['activation_approved'] is False
    assert {p.relative_to(tmp_path) for p in tmp_path.rglob('*')} == before


@pytest.mark.parametrize('digest', [None, '', 'x' * 64, 'A' * 64, '0' * 64])
def test_invalid_or_mismatched_archive_pin_refuses(tmp_path, monkeypatch, digest):
    archive, _ = built(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        candidate.verify_candidate(archive, expected_sha256=digest)


@pytest.mark.parametrize('fault', ['hash', 'length', 'boolean-length', 'activation', 'duplicate-declaration',
    'undeclared', 'missing', 'traversal', 'symlink', 'duplicate-member', 'missing-companion',
    'duplicate-json-key', 'compression'])
def test_rehashed_malformed_archive_still_refuses(tmp_path, monkeypatch, fault):
    archive, _ = built(tmp_path, monkeypatch)
    with zipfile.ZipFile(archive) as source:
        contents = {name: source.read(name) for name in source.namelist()}
    manifest = json.loads(contents['release-manifest.json'])
    first = manifest['files'][0]
    if fault == 'hash':
        first['sha256'] = '0' * 64
    if fault == 'length':
        first['bytes'] += 1
    if fault == 'boolean-length':
        first['bytes'] = True
    if fault == 'activation':
        manifest['activation_approved'] = True
    if fault == 'duplicate-declaration':
        manifest['files'].append(first)
    if fault == 'undeclared':
        contents['unlisted.py'] = b'value=1\n'
    if fault == 'missing':
        del contents[first['path']]
    if fault == 'traversal':
        contents['../outside.py'] = b'value=1\n'
    if fault == 'missing-companion':
        del contents['requirements-observed.txt']
    contents['release-manifest.json'] = json.dumps(manifest).encode()
    if fault == 'duplicate-json-key':
        contents['release-manifest.json'] = contents['release-manifest.json'].replace(b'{', b'{"contract":"duplicate",', 1)
    changed = tmp_path / 'changed.zip'
    with zipfile.ZipFile(changed, 'x') as target:
        for name, data in contents.items():
            info = zipfile.ZipInfo(name)
            info.external_attr = (stat.S_IFLNK | 0o777) << 16 if fault == 'symlink' and name == first['path'] else 0o100644 << 16
            info.compress_type = zipfile.ZIP_BZIP2 if fault == 'compression' else zipfile.ZIP_DEFLATED
            target.writestr(info, data)
        if fault == 'duplicate-member':
            with pytest.warns(UserWarning, match='Duplicate name'):
                target.writestr(first['path'], contents[first['path']])
    expected = hashlib.sha256(changed.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        candidate.verify_candidate(changed, expected_sha256=expected)

def test_source_read_bound_refuses_before_open(tmp_path, monkeypatch):
    source = tmp_path / 'synthetic.py'
    source.write_bytes(b'1234')
    def forbidden_open(*args, **kwargs):
        raise AssertionError('Bounded rejection must precede opening')
    monkeypatch.setattr(candidate.os, 'open', forbidden_open)
    with pytest.raises(ValueError, match='explicit read bound'):
        candidate.source_bytes(tmp_path, source.name, maximum_bytes=3)


@pytest.mark.parametrize('fault', ['entry-size', 'total-size', 'manifest-size'])
def test_declared_zip_sizes_are_bounded_before_decompression(tmp_path, fault):
    import struct

    archive = tmp_path / 'bounded.zip'
    with zipfile.ZipFile(archive, 'x') as target:
        target.writestr('release-manifest.json', '{}')
        target.writestr('requirements-observed.txt', '')
        for i in range(9):
            target.writestr(f'{i}.py', 'x')
    raw = bytearray(archive.read_bytes())
    offset = 0
    while (offset := raw.find(b'PK\x01\x02', offset)) >= 0:
        length = struct.unpack_from('<H', raw, offset + 28)[0]
        name = bytes(raw[offset + 46:offset + 46 + length]).decode()
        size = None
        if fault == 'manifest-size' and name == 'release-manifest.json':
            size = 1024 * 1024 + 1
        if name.endswith('.py'):
            if fault == 'entry-size':
                size = 16 * 1024 * 1024 + 1
            if fault == 'total-size':
                size = 16 * 1024 * 1024
        if size is not None:
            struct.pack_into('<I', raw, offset + 24, size)
        offset += 46 + length
    changed = tmp_path / 'oversized-declaration.zip'
    changed.write_bytes(raw)
    with pytest.raises(ValueError, match={'entry-size': 'entry exceeds', 'total-size': 'Decoded archive exceeds', 'manifest-size': 'Manifest exceeds'}[fault]):
        candidate.verify_candidate(changed, expected_sha256=hashlib.sha256(raw).hexdigest())


def test_archive_member_count_is_bounded(tmp_path):
    archive = tmp_path / 'too-many.zip'
    with zipfile.ZipFile(archive, 'x') as target:
        for i in range(5001):
            target.writestr(f'{i}.py', '')
    with pytest.raises(ValueError, match='member count'):
        candidate.verify_candidate(archive, expected_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
