"""A23: legacy Windows lifecycle must remain fail-closed."""

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
WINDOWS = ROOT / "scripts" / "windows"

BLOCK_MARKER = "ATLAS_LEGACY_LIFECYCLE_BLOCKED"


@pytest.mark.parametrize(
    "filename",
    [
        "Atlas-Launch.ps1",
        "Atlas-Stop.ps1",
    ],
)
def test_legacy_lifecycle_has_block_marker(filename: str) -> None:
    source = (WINDOWS / filename).read_text(encoding="utf-8")

    assert source.count(BLOCK_MARKER) == 1


def test_legacy_launch_guard_precedes_original_operations() -> None:
    source = (WINDOWS / "Atlas-Launch.ps1").read_text(
        encoding="utf-8"
    )

    guard = source.index(BLOCK_MARKER)
    exit_statement = source.index("exit 1", guard)

    assert guard < exit_statement
    assert exit_statement < source.index("$ErrorActionPreference")


def test_legacy_stop_guard_precedes_original_operations() -> None:
    source = (WINDOWS / "Atlas-Stop.ps1").read_text(
        encoding="utf-8"
    )

    guard = source.index(BLOCK_MARKER)
    original_operations = source.index("$ErrorActionPreference")

    assert guard < original_operations


def test_legacy_launch_guard_has_immediate_exit() -> None:
    source = (WINDOWS / "Atlas-Launch.ps1").read_text(
        encoding="utf-8"
    )

    assert (
        'Write-Error "ATLAS_LEGACY_LIFECYCLE_BLOCKED: '
        'Legacy startup is disabled pending safety certification."'
    ) in source

    assert "\nexit 1\n" in source.replace("\r\n", "\n")


def test_legacy_stop_guard_throws() -> None:
    source = (WINDOWS / "Atlas-Stop.ps1").read_text(
        encoding="utf-8"
    )

    assert (
        'throw "ATLAS_LEGACY_LIFECYCLE_BLOCKED: '
        'Legacy shutdown is disabled pending safety certification."'
    ) in source
