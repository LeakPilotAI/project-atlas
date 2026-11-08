"""Single exact independent-NTP lease: no shortcuts or synthetic operational CLI."""
from pathlib import Path

import pytest
from scripts.observation_runtime import atlas_independent_ntp_clock_preflight as subject


class FakeElapsed:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, delay):
        assert 0 < delay <= 5
        self.sleeps.append(delay)
        self.now += delay


class FakeAuthority:
    def __init__(self, *, runtime_id, lifetime, fail_after=None, bound=141):
        assert runtime_id == subject.RUNTIME_ID and lifetime == 240
        self.evidence = {"bound_ms": bound}
        self.samples = 0
        self.revocations = 0
        self.fail_after = fail_after

    def require_operational(self, scope):
        assert scope == subject.RUNTIME_ID
        self.samples += 1
        if self.fail_after and self.samples > self.fail_after:
            raise ValueError("NTP_REFRESH_FAILED_CAPABILITY_REVOKED")
        return self

    def revoke(self):
        self.revocations += 1


def test_one_clock_lease_and_exact_elapsed_window():
    tick = FakeElapsed()
    created = []

    def factory(**kwargs):
        c = FakeAuthority(**kwargs)
        created.append(c)
        return c

    result = subject.check_independent_clock_lease(
        clock_factory=factory, monotonic=tick.monotonic, sleep=tick.sleep,
        duration=20, interval=5)
    assert len(created) == 1 and created[0].samples == 5
    assert created[0].revocations == 1
    assert result["elapsed_seconds"] == 20
    assert result["status"] == "INDEPENDENT_NTP_LEASE_PASSED_NONFINANCIAL_ONLY"
    assert result["windows_time_required"] is False
    assert result["installer_ran"] is False
    assert result["paper_start_authorized"] is False


def test_fail_closed_revokes_single_authority_never_rebuilds():
    tick = FakeElapsed()
    created = []

    def factory(**kwargs):
        c = FakeAuthority(**kwargs, fail_after=2)
        created.append(c)
        return c

    with pytest.raises(ValueError, match="REFRESH_FAILED"):
        subject.check_independent_clock_lease(
            clock_factory=factory, monotonic=tick.monotonic, sleep=tick.sleep,
            duration=20, interval=5)
    assert len(created) == 1
    assert created[0].samples == 3 and created[0].revocations == 1


def test_high_initial_uncertainty_refuses_before_any_wait():
    tick = FakeElapsed()
    c = FakeAuthority(runtime_id=subject.RUNTIME_ID, lifetime=240, bound=1001)
    with pytest.raises(ValueError, match="BOUND_REFUSED"):
        subject.check_independent_clock_lease(
            clock_factory=lambda **kwargs: c,
            monotonic=tick.monotonic, sleep=tick.sleep, duration=20)
    assert c.revocations == 1 and tick.sleeps == []


@pytest.mark.parametrize("values", [
    {"duration": 0}, {"duration": 221}, {"duration": True},
    {"interval": 0}, {"interval": 6}, {"interval": True},
    {"duration": 5, "interval": 5},
])
def test_invalid_duration_and_interval_prevent_clock_creation(values):
    with pytest.raises(ValueError, match="DURATION_REFUSED"):
        subject.check_independent_clock_lease(
            clock_factory=lambda **kwargs: pytest.fail("created clock on invalid argument"),
            **values)


def test_real_cli_wires_only_direct_dual_ntp_no_os_clock_or_financial_action():
    file = Path(subject.__file__)
    src = file.read_text(encoding="utf-8")
    assert "PREFLIGHT_SECONDS = 180" in src
    assert "INTERVAL_SECONDS = 5" in src
    assert "clock.require_operational(RUNTIME_ID)" in src
    assert "clock.revoke()" in src
    assert "IndependentNtpClock" in src
    assert "value = check_independent_clock_lease()" not in src
    assert "outcome = check_independent_clock_lease()" in src
    for excluded in ("LocalWindowsClock", "w32tm", "Set-Date", "install_verified_release",
                     "Start-Atlas", "os.system", "subprocess", 'paper_start_authorized=True'):
        assert excluded not in src
