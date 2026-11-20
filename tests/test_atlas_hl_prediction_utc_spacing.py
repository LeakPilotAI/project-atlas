"""Disposable tests for actual UTC-based HL forecast public diagnostic cadence."""
import pytest

from scripts.observation_runtime.atlas_hl_prediction_utc_spacing import (
    MAX_WAIT_MS, MIN_SPACING_MS, SAFETY_MARGIN_MS, next_forecast_utc_start,
)

T = 1_800_000_000_000


class FakeNtp:
    def __init__(self, *, initial=0, uncertainty=139, skew_ms=0):
        self.t = initial
        self.uncertainty = uncertainty
        self.skew = skew_ms
        self.waits = []
        self.last = None
        self.mono = 0.0
        self.verified = True
        self.source = "ATLAS_NTP_V1:time.cloudflare.com+time.google.com"

    def monotonic(self):
        return self.mono

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.mono += seconds
        self.t += int(round(seconds * 1000)) + self.skew

    def sample(self):
        self.last = {
            "schema": "ATLAS_INDEPENDENT_PRECISE_UTC_V1",
            "utc_ns": (T + self.t) * 1_000_000,
            "monotonic_ns": int(self.mono * 1_000_000_000),
            "uncertainty_ms": self.uncertainty,
            "source": self.source,
        }
        return self.last

    def verify(self, value):
        return value is self.last and self.verified


def guard(fake, first=T, first_uncertainty=139):
    return next_forecast_utc_start(
        first_observed_ms=first, first_uncertainty_ms=first_uncertainty,
        sample_precise=fake.sample, verify_precise=fake.verify,
        sleep=fake.sleep, monotonic=fake.monotonic)


@pytest.mark.parametrize("uncertainty", [0, 1, 139, 500, 1000])
def test_original_10_second_utc_gap_never_relaxed_for_real_ntp_bounds(uncertainty):
    fake = FakeNtp(uncertainty=uncertainty)
    started, bound = guard(fake, first_uncertainty=uncertainty)
    assert started - T >= MIN_SPACING_MS + 2 * uncertainty + SAFETY_MARGIN_MS
    assert started - T <= 12_250
    assert bound == uncertainty
    assert 1 <= len(fake.waits) <= 4
    assert sum(fake.waits) <= MAX_WAIT_MS / 1000


@pytest.mark.parametrize("initial", [9996, 9999, 10000, 10100, 10250])
def test_old_consented_four_ms_shortfall_never_promotes(initial):
    fake = FakeNtp(initial=initial, uncertainty=0)
    started, _ = guard(fake, first_uncertainty=0)
    assert started - T >= MIN_SPACING_MS + SAFETY_MARGIN_MS
    if initial < MIN_SPACING_MS + SAFETY_MARGIN_MS:
        assert fake.waits


def test_initial_sample_already_robustly_eligible_requires_no_sleep():
    fake = FakeNtp(initial=12_500, uncertainty=1000)
    started, _ = guard(fake, first_uncertainty=1000)
    assert started == T + 12_500
    assert fake.waits == []


@pytest.mark.parametrize("bad", [None, True, "0", -1, 1001, 1.5])
def test_forbidden_clock_uncertainty_never_grants_cadence(bad):
    fake = FakeNtp()
    with pytest.raises(ValueError, match="ORIGINAL_EVIDENCE_REQUIRED"):
        guard(fake, first_uncertainty=bad)


@pytest.mark.parametrize("bad", [None, False, T - 1_800_000_000_000, T + 0.5, "timestamp"])
def test_first_timestamp_must_be_genuine_unix_ms(bad):
    fake = FakeNtp()
    with pytest.raises(ValueError, match="ORIGINAL_EVIDENCE_REQUIRED"):
        guard(fake, first=bad)


def test_invalid_or_replayed_original_clock_sample_is_refused():
    fake = FakeNtp()
    fake.verified = False
    with pytest.raises(ValueError, match="ORIGINAL_NTP_PROOF_REFUSED"):
        guard(fake)
    assert fake.waits == []


def test_counterfeit_os_time_source_is_rejected():
    fake = FakeNtp()
    fake.source = "WINDOWS_OS_WALL_CLOCK_NOT_NTP"
    with pytest.raises(ValueError, match="ORIGINAL_NTP_PROOF_REFUSED"):
        guard(fake)


@pytest.mark.parametrize("uncertainty", [-1, 1001, True])
def test_drifted_new_sample_bound_never_authorizes(uncertainty):
    fake = FakeNtp(uncertainty=uncertainty)
    with pytest.raises(ValueError, match="ORIGINAL_NTP_PROOF_REFUSED"):
        guard(fake)


def test_utc_rollback_refused_without_retry():
    fake = FakeNtp(initial=-5)
    with pytest.raises(ValueError, match="UTC_ROLLBACK"):
        guard(fake)
    assert fake.waits == []


def test_monotonic_backward_refused_without_retry():
    fake = FakeNtp(initial=0)
    calls = 0

    def backwards():
        nonlocal calls
        calls += 1
        return 0 if calls == 1 else -1

    with pytest.raises(ValueError, match="MONOTONIC_ROLLBACK"):
        next_forecast_utc_start(
            first_observed_ms=T, first_uncertainty_ms=0,
            sample_precise=fake.sample, verify_precise=fake.verify,
            sleep=fake.sleep, monotonic=backwards)


def test_frozen_clock_exhausts_bounded_samples():
    fake = FakeNtp(skew_ms=-1000)
    with pytest.raises(ValueError, match="SAMPLES_EXHAUSTED|BUDGET_EXHAUSTED"):
        guard(fake, first_uncertainty=0)
    assert sum(fake.waits) <= MAX_WAIT_MS / 1000


def test_replayed_original_utc_sample_is_not_an_operational_authority():
    fake = FakeNtp()
    fake.verified = False
    with pytest.raises(ValueError, match="ORIGINAL_NTP_PROOF_REFUSED"):
        guard(fake, first_uncertainty=0)
