import pytest

from app.backtest.offline_evidence_snapshot import (
    capture_evidence_snapshot,
    EvidenceSnapshotError,
)


def test_snapshot_preserves_original_bytes(tmp_path):
    paths = []

    for name, payload in (
        ("dataset.csv", b"dataset-original"),
        ("manifest.json", b'{"manifest":true}'),
        ("receipt.json", b'{"receipt":true}'),
    ):
        path = tmp_path / name
        path.write_bytes(payload)
        paths.append(path)

    snapshot = capture_evidence_snapshot(tuple(paths))

    assert snapshot == (
        b"dataset-original",
        b'{"manifest":true}',
        b'{"receipt":true}',
    )


def test_snapshot_does_not_follow_later_mutations(tmp_path):
    paths = []

    for name, payload in (
        ("dataset.csv", b"original-dataset"),
        ("manifest.json", b"original-manifest"),
        ("receipt.json", b"original-receipt"),
    ):
        path = tmp_path / name
        path.write_bytes(payload)
        paths.append(path)

    snapshot = capture_evidence_snapshot(tuple(paths))

    for path in paths:
        path.write_bytes(b"replaced")

    assert snapshot == (
        b"original-dataset",
        b"original-manifest",
        b"original-receipt",
    )


def test_missing_file_refused(tmp_path):
    missing = tmp_path / "missing.json"

    with pytest.raises(EvidenceSnapshotError):
        capture_evidence_snapshot((missing,))


def test_oversized_file_refused(tmp_path):
    path = tmp_path / "large.bin"
    path.write_bytes(b"x" * 33)

    with pytest.raises(EvidenceSnapshotError):
        capture_evidence_snapshot(
            (path,),
            max_file_bytes=32,
        )


def test_invalid_limit_refused(tmp_path):
    path = tmp_path / "dataset.csv"
    path.write_bytes(b"data")

    with pytest.raises(EvidenceSnapshotError):
        capture_evidence_snapshot(
            (path,),
            max_file_bytes=0,
        )
