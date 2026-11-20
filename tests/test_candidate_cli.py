"""Explicit build/verify CLI modes preserve source and deny activation."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from test_candidate_verifier import built
from test_offline_candidate_packaging import candidate, fixture_root


@pytest.mark.parametrize('args', [[], ['output', '--verify', 'source.zip', '--expected-sha256', '0' * 64],
    ['output', '--expected-sha256', '0' * 64], ['--verify', 'source.zip'],
    ['--verify', 'source.zip', '--expected-sha256', 'A' * 64],
    ['--verify', 'source.zip', '--expected-sha256', 'not-a-hash']])
def test_invalid_mode_or_pin_is_usage_error_without_io(tmp_path, monkeypatch, capsys, args):
    def forbidden(*args, **kwargs):
        raise AssertionError('Invalid CLI must refuse before build or verification')
    monkeypatch.setattr(candidate, 'build', forbidden)
    monkeypatch.setattr(candidate, 'verify_candidate', forbidden)
    with pytest.raises(SystemExit) as caught:
        candidate.main(args)
    assert caught.value.code == 2
    assert capsys.readouterr().out == ''
    assert list(tmp_path.iterdir()) == []


def test_positional_build_preserves_single_digest_output(tmp_path, monkeypatch, capsys):
    fixture_root(tmp_path, monkeypatch)
    destination = tmp_path / 'output'
    assert candidate.main([str(destination)]) == 0
    captured = capsys.readouterr()
    assert captured.err == ''
    assert re.fullmatch(r'[0-9a-f]{64}\n', captured.out)
    assert captured.out.strip() == (destination / 'archive.sha256').read_text(encoding='ascii').strip()


def test_verify_mode_has_stable_json_and_no_extraction(tmp_path, monkeypatch, capsys):
    archive, digest = built(tmp_path, monkeypatch)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert candidate.main(['--verify', str(archive), '--expected-sha256', digest]) == 0
    captured = capsys.readouterr()
    value = json.loads(captured.out)
    assert captured.err == ''
    assert value['archive_sha256'] == digest
    assert value['supplied_bytes_consistent'] is True
    assert value['activation_approved'] is False
    assert value['source_authenticated'] is False
    after = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert after == before


@pytest.mark.parametrize('fault', ['mismatched-pin', 'missing', 'malformed-zip'])
def test_expected_refusal_is_nonzero_and_sanitized(tmp_path, monkeypatch, capsys, fault):
    archive, digest = built(tmp_path, monkeypatch)
    if fault == 'mismatched-pin':
        digest = '0' * 64
    if fault == 'missing':
        archive = tmp_path / 'private-fixture-name.zip'
    if fault == 'malformed-zip':
        archive = tmp_path / 'private-fixture-name.zip'
        archive.write_bytes(b'not a zip archive')
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert candidate.main(['--verify', str(archive), '--expected-sha256', digest]) == 1
    captured = capsys.readouterr()
    assert captured.out == ''
    assert str(tmp_path) not in captured.err
    assert 'private-fixture-name' not in captured.err
    value = json.loads(captured.err)
    assert value['status'] == 'REFUSED'
    assert value['operation'] == 'VERIFY'
    assert value['activation_approved'] is False


def test_real_cli_process_verifies_without_importing_or_executing_archive(tmp_path, monkeypatch):
    archive, digest = built(tmp_path, monkeypatch)
    script = Path(__file__).resolve().parents[1] / 'scripts/build_release_candidate.py'
    result = subprocess.run([sys.executable, str(script), '--verify', str(archive), '--expected-sha256', digest], cwd=tmp_path, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['activation_approved'] is False
    assert not (tmp_path / 'backend').exists()


def test_existing_build_destination_preserved_on_refusal(tmp_path, monkeypatch, capsys):
    fixture_root(tmp_path, monkeypatch)
    existing = tmp_path / 'original'
    existing.mkdir()
    evidence = existing / 'evidence.txt'
    evidence.write_bytes(b'keep')
    assert candidate.main([str(existing)]) == 1
    value = json.loads(capsys.readouterr().err)
    assert value['operation'] == 'BUILD'
    assert value['error_type'] == 'FileExistsError'
    assert evidence.read_bytes() == b'keep'
