import os

import pytest

from app.backtest.offline_evidence_snapshot import (
    EvidenceSnapshotError,
    capture_evidence_snapshot,
)


def test_same_size_mid_read_mutation_refused(tmp_path, monkeypatch):
    path = tmp_path / "evidence.bin"
    path.write_bytes(b"A" * 128)

    original_fstat = os.fstat
    calls = 0

    def controlled_fstat(fd):
        nonlocal calls
        calls += 1

        if calls == 2:
            # Same-size mutation during the capture window.
            path.write_bytes(b"B" * 128)

        return original_fstat(fd)

    monkeypatch.setattr(os, "fstat", controlled_fstat)

    with pytest.raises(EvidenceSnapshotError):
        capture_evidence_snapshot((path,))

    assert calls >= 2


def test_path_replacement_during_capture_is_identified(
    tmp_path, monkeypatch
):
    path = tmp_path / "evidence.bin"
    path.write_bytes(b"original-evidence")

    original_fstat = os.fstat
    calls = 0

    def controlled_fstat(fd):
        nonlocal calls
        calls += 1

        if calls == 2:
            replacement = tmp_path / "replacement.bin"
            replacement.write_bytes(b"replaced-evidence")
            replacement.replace(path)

        return original_fstat(fd)

    monkeypatch.setattr(os, "fstat", controlled_fstat)

    # The open handle may still point to the original file.
    # Capture currently lacks a path recheck.
    with pytest.raises(EvidenceSnapshotError):
        capture_evidence_snapshot((path,))

    assert calls >= 2
