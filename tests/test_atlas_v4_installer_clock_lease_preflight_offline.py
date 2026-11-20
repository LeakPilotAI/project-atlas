"""One persistent native-clock lease preflight, inert fake clock/time in tests."""

import pytest

from scripts.observation_runtime import (
    atlas_v4_installer_clock_lease_preflight as lease,
)


class FakeMonotonic:
    def __init__(self):
        self.current = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.current

    def sleep(self, seconds):
        assert 0 < seconds <= 5
        self.sleeps.append(seconds)
        self.current += seconds


class FakeClock:
    def __init__(self, *, expected_source, runtime_id, lifetime, fail_after=None, bound=230):
        assert expected_source == lease.SOURCE
        assert runtime_id == lease.RUNTIME_ID
        assert lifetime == 240
        self.evidence = {"bound_ms": bound}
        self.fail_after = fail_after
        self.samples = 0
        self.revocations = 0

    def require_operational(self, runtime_id):
        assert runtime_id == lease.RUNTIME_ID
        self.samples += 1
        if self.fail_after is not None and self.samples > self.fail_after:
            raise ValueError("PERSONAL_ACCEPTED_CLOCK_ANCHOR_REQUIRED")
        return self

    def revoke(self):
        self.revocations += 1


def test_one_exact_lease_reused_across_every_sample_without_restarting():
    tick = FakeMonotonic()
    created = []

    def factory(**kwargs):
        result = FakeClock(**kwargs)
        created.append(result)
        return result

    result = lease.check_native_install_lease(
        clock_factory=factory, monotonic=tick.monotonic,
        sleep=tick.sleep, duration=20, interval=5,
    )
    assert len(created) == 1 and created[0].samples == 5
    assert created[0].revocations == 1
    assert result["elapsed_seconds"] == 20
    assert result["status"] == "CONTINUOUS_NATIVE_LEASE_PREFLIGHT_PASSED_NOT_INSTALLATION_AUTHORITY"
    assert result["installer_ran"] is False
    assert result["financial_start_authorized"] is False


def test_legitimate_native_clock_expiry_refuses_and_revokes_exact_instance():
    tick = FakeMonotonic()
    created = []

    def factory(**kwargs):
        c = FakeClock(**kwargs, fail_after=2)
        created.append(c)
        return c

    with pytest.raises(ValueError, match="PERSONAL_ACCEPTED_CLOCK_ANCHOR_REQUIRED"):
        lease.check_native_install_lease(
            clock_factory=factory, monotonic=tick.monotonic,
            sleep=tick.sleep, duration=20, interval=5,
        )
    assert len(created) == 1
    assert created[0].samples == 3 and created[0].revocations == 1


def test_invalid_initial_bound_refuses_without_waiting():
    tick = FakeMonotonic()
    created = []

    def factory(**kwargs):
        c = FakeClock(**kwargs, bound=1001)
        created.append(c)
        return c

    with pytest.raises(ValueError, match="INITIAL_BOUND_INVALID"):
        lease.check_native_install_lease(
            clock_factory=factory, monotonic=tick.monotonic,
            sleep=tick.sleep, duration=20, interval=5,
        )
    assert len(created) == 1 and created[0].revocations == 1
    assert tick.sleeps == []


@pytest.mark.parametrize("kwargs", [
    {"duration": 0}, {"duration": 241}, {"duration": True},
    {"interval": 0}, {"interval": 6}, {"interval": True},
    {"duration": 5, "interval": 5},
])
def test_invalid_preflight_durations_rejected_before_any_clock_created(kwargs):
    def must_not_create(**fields):
        raise AssertionError("a rejected argument created a native clock")

    with pytest.raises(ValueError, match="BOUNDS_INVALID"):
        lease.check_native_install_lease(clock_factory=must_not_create, **kwargs)


def test_cli_only_invokes_full_length_native_readonly_clock_preflight():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] /
              "scripts/observation_runtime/atlas_v4_installer_clock_lease_preflight.py").read_text()
    assert "PREFLIGHT_SECONDS = 180" in source
    assert "INTERVAL_SECONDS = 5" in source
    assert "lifetime=240" in source
    assert "clock.require_operational(RUNTIME_ID)" in source
    assert "clock.revoke()" in source
    assert "value = check_native_install_lease()" in source
    for forbidden in ("install_verified_release", "os.system", "subprocess.run",
                      "taskkill", "Start-Process", "w32tm", "Set-ItemProperty",
                      "MaxPollInterval", "install_unselected_release("):
        assert forbidden not in source
