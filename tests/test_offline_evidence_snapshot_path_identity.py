import os
from types import SimpleNamespace

import pytest

from app.backtest.offline_evidence_snapshot import (
    EvidenceSnapshotError,
    capture_evidence_snapshot,
)


def test_path_identity_mismatch_refused(tmp_path, monkeypatch):
    path = tmp_path / "evidence.bin"
    path.write_bytes(b"stable-evidence")

    original_stat = os.stat
    intercepted = False

    def controlled_stat(target, *args, **kwargs):
        nonlocal intercepted

        result = original_stat(target, *args, **kwargs)

        if target == path:
            intercepted = True

            return SimpleNamespace(
                st_dev=result.st_dev,
                st_ino=result.st_ino + 1,
            )

        return result

    monkeypatch.setattr(
        os,
        "stat",
        controlled_stat,
    )

    with pytest.raises(
        EvidenceSnapshotError,
        match="evidence path identity changed during capture",
    ):
        capture_evidence_snapshot((path,))

    assert intercepted


def test_matching_path_identity_accepted(tmp_path):
    path = tmp_path / "evidence.bin"
    path.write_bytes(b"stable-evidence")

    result = capture_evidence_snapshot((path,))

    assert result == (b"stable-evidence",)
