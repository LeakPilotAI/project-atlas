"""Confined updater copies; never edits the canonical roadmap in a test."""
import shutil
import subprocess
from pathlib import Path

import pytest

START = '=== ATLAS MANAGED CURRENT CHECKPOINT V1 ==='
END = '=== END ATLAS MANAGED CURRENT CHECKPOINT V1 ==='
SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/windows/Atlas-Roadmap-Checkpoint.ps1'
NEW = 'Milestone:SOURCE\nStatus:ACTIVE;startup NO\nEvidence:synthetic updater fixture\nNext action:source engineering'


def run(tmp_path, *, archive=True, checkpoint=NEW):
    host = shutil.which('pwsh')
    if host is None: pytest.skip('NOT EXECUTED: PowerShell host unavailable')
    source = tmp_path / 'checkpoint.txt'
    source.write_bytes(checkpoint.encode())
    args = [host, '-NoProfile', '-File', str(SCRIPT), '-RoadmapPath', str(tmp_path / 'roadmap.txt'), '-CheckpointFile', str(source)]
    if archive: args.append('-ArchivePriorCheckpoint')
    return subprocess.run(args, capture_output=True, timeout=15, check=False)


@pytest.fixture
def existing(tmp_path):
    prefix = ('ATLAS PERMANENT FUTURE STRATEGY V1 - MARKET INTELLIGENCE OS\r\n'
              'ATLAS PERMANENT EXECUTION AND CONVERSATION RECOVERY CONTRACT V1\r\n'
              + ''.join(f'Phase {n}\r\n' for n in range(1, 8)))
    body = '\r\nPrior evidence — preserved\r\n' + 'retained history\r\n' * 3500
    suffix = '\r\n' + ''.join(f'Decision {n}:UNCHANGED\r\n' for n in range(21))
    raw = (prefix + START + body + END + suffix).encode()
    path = tmp_path / 'roadmap.txt'
    path.write_bytes(raw)
    return path, prefix.encode(), body.encode(), suffix.encode(), raw


def test_archive_retains_history_bytes_and_exact_backup(existing, tmp_path):
    path, prefix, body, suffix, raw = existing
    result = run(tmp_path)
    assert result.returncode == 0, result.stderr
    updated = path.read_bytes()
    assert updated.startswith(prefix) and updated.endswith(suffix) and body in updated
    assert updated.count(START.encode()) == updated.count(END.encode()) == 1
    assert updated.count(body) == 1 and NEW.encode() in updated
    assert any(p.read_bytes() == raw for p in tmp_path.glob('*.bak'))


def test_default_behavior_unchanged_without_archive(existing, tmp_path):
    path, prefix, _body, suffix, _ = existing
    assert run(tmp_path, archive=False).returncode == 0
    assert path.read_bytes() == prefix + START.encode() + b'\r\n' + NEW.encode() + b'\r\n' + END.encode() + suffix


def test_over_capacity_refuses_before_any_mutation(existing, tmp_path):
    path, _, _, _, raw = existing
    assert run(tmp_path, checkpoint=NEW + 'x' * 60000).returncode != 0
    assert path.read_bytes() == raw and not list(tmp_path.glob('*.bak'))


def test_successive_archive_is_linear_not_nested_duplicate(existing, tmp_path):
    path, prefix, body, suffix, _ = existing
    assert run(tmp_path).returncode == 0
    prior = path.read_bytes()
    next_checkpoint = NEW.replace('Milestone:SOURCE', 'Milestone:SUCCESSOR')
    assert run(tmp_path, checkpoint=next_checkpoint).returncode == 0
    current = path.read_bytes()
    assert current.startswith(prefix) and current.endswith(suffix) and current.count(body) == 1
    assert current.count(NEW.encode()) == current.count(next_checkpoint.encode()) == 1
    assert current.count(START.encode()) == 1
    assert any(p.read_bytes() == prior for p in tmp_path.glob('*.bak'))
