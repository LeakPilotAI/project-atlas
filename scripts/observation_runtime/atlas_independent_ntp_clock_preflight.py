"""Independent Google+Cloudflare NTP single-lease commissioning preflight.

Read-only. Not an Atlas installation gate until separately reviewed/admitted.
Actual CLI uses one unmodified IndependentNtpClock and 180 true elapsed
monotonic seconds, with independent peer renewal every <=45 seconds.
"""
import time

from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock

RUNTIME_ID = "atlas-dual-ntp-v1-180s-commissioning-only"
PREFLIGHT_SECONDS = 180
INTERVAL_SECONDS = 5


def check_independent_clock_lease(*, clock_factory=IndependentNtpClock,
                                  monotonic=time.perf_counter, sleep=time.sleep,
                                  duration=PREFLIGHT_SECONDS, interval=INTERVAL_SECONDS):
    """Nondefault arguments allowed only for unit-test fakes; CLI uses defaults."""
    if (type(duration) is not int or type(interval) is not int
            or not 1 <= interval <= 5 or not interval < duration <= 220):
        raise ValueError("ATLAS_INDEPENDENT_CLOCK_PREFLIGHT_DURATION_REFUSED")
    clock = clock_factory(runtime_id=RUNTIME_ID, lifetime=240)
    initial = clock.evidence["bound_ms"]
    if type(initial) is not int or not 0 <= initial <= 1000:
        clock.revoke()
        raise ValueError("ATLAS_INDEPENDENT_CLOCK_BOUND_REFUSED")
    start = monotonic()
    samples = 0
    try:
        while True:
            clock.require_operational(RUNTIME_ID)
            samples += 1
            elapsed = monotonic() - start
            if elapsed >= duration:
                break
            wait = min(interval, duration - elapsed)
            if wait <= 0:
                raise ValueError("ATLAS_INDEPENDENT_CLOCK_MONOTONIC_DISCONTINUITY")
            sleep(wait)
        if samples < 2:
            raise ValueError("ATLAS_INDEPENDENT_CLOCK_REQUIRED_MORE_SAMPLES")
        return {"schema": "ATLAS_TWO_NTP_180_SECOND_PREFLIGHT_V1",
                "status": "INDEPENDENT_NTP_LEASE_PASSED_NONFINANCIAL_ONLY",
                "elapsed_seconds": round(elapsed, 2), "samples": samples,
                "initial_bound_ms": initial,
                "final_bound_ms": clock.evidence["bound_ms"],
                "windows_time_required": False,
                "installer_ran": False, "paper_start_authorized": False,
                "provider_trading_enabled": False}
    finally:
        clock.revoke()


def main():
    outcome = check_independent_clock_lease()
    print(outcome["status"])
    print("INDEPENDENT_NTP_PREFLIGHT_SECONDS=" + str(outcome["elapsed_seconds"]))
    print("INDEPENDENT_NTP_PREFLIGHT_SAMPLES=" + str(outcome["samples"]))
    print("INDEPENDENT_NTP_INITIAL_BOUND_MS=" + str(outcome["initial_bound_ms"]))
    print("INDEPENDENT_NTP_FINAL_BOUND_MS=" + str(outcome["final_bound_ms"]))
    print("NO_NATIVE_INSTALL_OR_FINANCIAL_PAPER_AUTHORIZATION")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        raise SystemExit("ATLAS_INDEPENDENT_NTP_PREFLIGHT_REFUSED:" + str(exc)) from None
