"""Bounded offline evidence byte capture.

Captures immutable bytes for subsequent structural validation.

This is not an atomic multi-file filesystem snapshot and does not
authenticate historical publication or establish predictive skill.
"""

from __future__ import annotations

from pathlib import Path
import stat


DEFAULT_MAX_FILE_BYTES = 64 * 1024 * 1024


class EvidenceSnapshotError(ValueError):
    """Evidence cannot be captured within the declared limits."""


def capture_evidence_snapshot(
    paths: tuple[Path, ...],
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> tuple[bytes, ...]:
    """Capture bounded immutable evidence bytes.

    Each file is read through one open handle. Changes detectable
    through file identity or metadata are refused.

    Cross-file atomicity is not guaranteed.
    """
    if (
        type(max_file_bytes) is not int
        or max_file_bytes <= 0
    ):
        raise EvidenceSnapshotError(
            "max_file_bytes must be a positive integer"
        )

    if not isinstance(paths, tuple) or not paths:
        raise EvidenceSnapshotError(
            "nonempty tuple of evidence paths required"
        )

    captured = []

    for supplied_path in paths:
        if not isinstance(supplied_path, Path):
            raise EvidenceSnapshotError(
                "evidence path must be a pathlib.Path"
            )

        try:
            with supplied_path.open("rb") as handle:
                before = handle.fileno()
                import os

                initial = os.fstat(before)

                if not stat.S_ISREG(initial.st_mode):
                    raise EvidenceSnapshotError(
                        "evidence must be a regular file"
                    )

                if initial.st_size > max_file_bytes:
                    raise EvidenceSnapshotError(
                        "evidence file exceeds size limit"
                    )

                # Read one byte beyond the limit to detect growth.
                payload = handle.read(max_file_bytes + 1)

                if len(payload) > max_file_bytes:
                    raise EvidenceSnapshotError(
                        "evidence file exceeds size limit"
                    )

                final = os.fstat(before)

                # Verify the pathname still identifies the open file.
                # This is a point-in-time identity check, not a lock.
                pathname = os.stat(supplied_path)

                if (
                    pathname.st_dev,
                    pathname.st_ino,
                ) != (
                    final.st_dev,
                    final.st_ino,
                ):
                    raise EvidenceSnapshotError(
                        "evidence path identity changed during capture"
                    )

                identity_before = (
                    initial.st_dev,
                    initial.st_ino,
                    initial.st_size,
                    initial.st_mtime_ns,
                    initial.st_ctime_ns,
                )

                identity_after = (
                    final.st_dev,
                    final.st_ino,
                    final.st_size,
                    final.st_mtime_ns,
                    final.st_ctime_ns,
                )

                if identity_before != identity_after:
                    raise EvidenceSnapshotError(
                        "evidence changed during capture"
                    )

                if len(payload) != final.st_size:
                    raise EvidenceSnapshotError(
                        "evidence size changed during capture"
                    )

                captured.append(bytes(payload))

        except OSError as exc:
            raise EvidenceSnapshotError(
                "evidence capture unavailable: " + str(exc)
            ) from exc

    return tuple(captured)
