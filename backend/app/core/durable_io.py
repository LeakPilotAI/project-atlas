"""Small file-write checks, not a power-loss or hardware durability guarantee."""
from __future__ import annotations

import os
from pathlib import Path
from typing import TextIO


def write_flushed(handle: TextIO, value: str) -> None:
    """Reject short writes and propagate the original write/flush/fsync failure."""
    written = handle.write(value)
    if written != len(value):
        raise OSError(f"Incomplete persistence write: {written!r}/{len(value)} characters")
    handle.flush()
    os.fsync(handle.fileno())


def sync_parent(path: Path) -> None:
    """Sync POSIX namespace changes; Windows directory fsync is not supported.

    On Windows the acknowledged boundary is file flush plus successful replace,
    NOT independently proven persistence of the directory entry across power loss.
    """
    if os.name == "nt":
        return
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
