"""Bounded R14 native installation host admission tests: no real installs."""
from pathlib import Path

import pytest

from scripts.observation_runtime import native_install_host_admission as host
from scripts import atlas_r14_low_impact_installer as r14

PARENT = Path("D:/AtlasRuntime/releases")
HIGH_RAM = 16 * 1024**3
HIGH_DISK = 10 * 1024**3


def test_exact_windows_release_parent_ready_with_injected_idle_host():
    result = host.require_code_install_host_ready(
        PARENT, process_names={"explorer.exe", "python.exe"},
        free_ram_bytes=HIGH_RAM, free_disk_bytes=HIGH_DISK)
    assert result["status"] == "RESOURCE_ADMITTED_NOT_INSTALL_AUTHORIZATION"
    assert result["available_ram_bytes"] == HIGH_RAM
    assert result["available_disk_bytes"] == HIGH_DISK
    assert result["interactive_game_detected"] is False
    assert result["selection_allowed"] is False
    assert result["financial_authority"] is False


@pytest.mark.parametrize("name", ["NBA2K27.exe", "nba2k27.exe", "NbA2k27.EXE"])
def test_game_playing_blocks_native_bulk_copy(name):
    with pytest.raises(ValueError, match="NATIVE_HOST_GAME_ACTIVE_DEFER_BULK_COPY"):
        host.require_code_install_host_ready(
            PARENT, process_names={"explorer.exe", name},
            free_ram_bytes=HIGH_RAM, free_disk_bytes=HIGH_DISK)


@pytest.mark.parametrize("ram", [0, host.MIN_FREE_RAM_BYTES - 1])
def test_low_free_ram_blocks_native_copy(ram):
    with pytest.raises(ValueError, match="NATIVE_HOST_RAM_HEADROOM_REFUSED"):
        host.require_code_install_host_ready(
            PARENT, process_names={"explorer.exe"},
            free_ram_bytes=ram, free_disk_bytes=HIGH_DISK)


@pytest.mark.parametrize("disk", [0, host.MIN_FREE_DISK_BYTES - 1])
def test_low_free_disk_blocks_native_copy(disk):
    with pytest.raises(ValueError, match="NATIVE_HOST_DISK_HEADROOM_REFUSED"):
        host.require_code_install_host_ready(
            PARENT, process_names={"explorer.exe"},
            free_ram_bytes=HIGH_RAM, free_disk_bytes=disk)


@pytest.mark.parametrize("bad_names", [("explorer.exe", None), "nba2k27.exe"])
def test_injected_host_process_evidence_must_be_bounded(bad_names):
    with pytest.raises(ValueError, match="NATIVE_HOST_RESOURCE_EVIDENCE_INVALID"):
        host.require_code_install_host_ready(
            PARENT, process_names=bad_names,
            free_ram_bytes=HIGH_RAM, free_disk_bytes=HIGH_DISK)


def test_host_parent_must_be_the_exact_release_root():
    with pytest.raises(ValueError, match="NATIVE_HOST_EXACT_RELEASE_PARENT_REQUIRED"):
        host.require_code_install_host_ready(
            Path("D:/AtlasRuntime"), process_names={"explorer.exe"},
            free_ram_bytes=HIGH_RAM, free_disk_bytes=HIGH_DISK)


def test_native_host_check_reads_real_process_table_without_watcher():
    names = host._snapshot_windows_process_names()
    assert isinstance(names, frozenset)
    assert 1 <= len(names) <= host.MAX_PROCESSES
    assert "python.exe" in names
    assert host._windows_free_ram_bytes() > 0


def test_r14_game_conflict_precedes_any_clock_or_native_io(monkeypatch):
    events = []
    monkeypatch.setattr(r14, "_require_separate_consent",
                        lambda: events.append("synthetic_consent"))
    def game_active(*_):
        events.append("game_active")
        raise ValueError("NATIVE_HOST_GAME_ACTIVE_DEFER_BULK_COPY")
    monkeypatch.setattr(r14, "require_code_install_host_ready", game_active)
    monkeypatch.setattr(r14, "prepare_readonly",
                        lambda: pytest.fail("NO_SOURCE_PREP_BEFORE_HOST"))
    monkeypatch.setattr(r14, "write_new_json",
                        lambda *_: pytest.fail("NO_NATIVE_JOURNAL_BEFORE_HOST"))
    monkeypatch.setattr(r14, "_copy_prepared_code",
                        lambda **_: pytest.fail("NO_NATIVE_COPY_BEFORE_HOST"))
    with pytest.raises(ValueError, match="NATIVE_HOST_GAME_ACTIVE_DEFER_BULK_COPY"):
        r14.install(execute_approved=True, clock=None)
    assert events == ["synthetic_consent", "game_active"]


def test_r14_midcopy_host_headroom_refresh_and_refusal(monkeypatch):
    calls = []
    def qualify(*_):
        calls.append("host")
        if len(calls) == 2:
            raise ValueError("NATIVE_HOST_GAME_ACTIVE_DEFER_BULK_COPY")
        return True
    monkeypatch.setattr(r14, "require_code_install_host_ready", qualify)

    class Guard:
        checks = 0
        now = 10.0
        def tick(self):
            self.checks += 1
        def monotonic(self):
            return self.now
    class Clock:
        def require_operational(self, _):
            return self
    guard = Guard()
    clock = Clock()
    assert r14._native_admission(clock, "r14-code-only-test", guard)
    for _ in range(7):
        assert r14._native_admission(clock, "r14-code-only-test", guard)
    assert calls == ["host"]  # Do not enumerate processes on every chunk.
    guard.now += r14.HOST_ADMISSION_REFRESH_SECONDS
    with pytest.raises(ValueError, match="NATIVE_HOST_GAME_ACTIVE_DEFER_BULK_COPY"):
        r14._native_admission(clock, "r14-code-only-test", guard)
    assert calls == ["host", "host"]
