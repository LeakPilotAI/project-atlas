"""Read-only, one-instance native clock lease preflight for V4 code installation.

This does not install or activate Atlas. Passing cannot guarantee a future copy;
its only purpose is to reject an immediately unreliable long-lived clock.
Existing installer must still enforce its own native clock throughout copying.
"""

import time

from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock

SOURCE = "time.cloudflare.com,0x8 time.google.com,0x8"
RUNTIME_ID = "atlas-v4-code-install-clock-lease-preflight-only"
PREFLIGHT_SECONDS = 180  # Longer than the previous ~153s native copy/readback.
INTERVAL_SECONDS = 5


def check_native_install_lease(*, clock_factory=LocalWindowsClock,
                               monotonic=time.perf_counter, sleep=time.sleep,
                               duration=PREFLIGHT_SECONDS, interval=INTERVAL_SECONDS):
    """One genuine instance, not a series of newly accepted short-lived ones.

    Non-default arguments exist only for inert, deterministic test doubles.
    The CLI invokes this with no parameters and no shortened durations.
    """
    if (type(duration) is not int or type(interval) is not int
            or not 1 <= interval <= 5 or not interval < duration <= 220):
        raise ValueError("ATLAS_V4_INSTALL_CLOCK_PREFLIGHT_BOUNDS_INVALID")
    clock = clock_factory(expected_source=SOURCE, runtime_id=RUNTIME_ID, lifetime=240)
    initial = clock.evidence["bound_ms"]
    if type(initial) is not int or not 0 <= initial <= 1000:
        clock.revoke()
        raise ValueError("ATLAS_V4_INSTALL_CLOCK_INITIAL_BOUND_INVALID")
    start = monotonic()
    samples = 0
    try:
        while True:
            clock.require_operational(RUNTIME_ID)
            samples += 1
            elapsed = monotonic() - start
            if elapsed >= duration:
                break
            delay = min(interval, duration - elapsed)
            if delay <= 0:
                raise ValueError("ATLAS_V4_INSTALL_CLOCK_MONOTONIC_DISCONTINUITY")
            sleep(delay)
        if samples < 2:
            raise ValueError("ATLAS_V4_INSTALL_CLOCK_SUSTAINED_SAMPLES_REQUIRED")
        return {"status": "CONTINUOUS_NATIVE_LEASE_PREFLIGHT_PASSED_NOT_INSTALLATION_AUTHORITY",
                "elapsed_seconds": round(elapsed, 2), "samples": samples,
                "initial_bound_ms": initial, "selected_release_changed": False,
                "financial_start_authorized": False, "installer_ran": False}
    finally:
        clock.revoke()


def main():
    value = check_native_install_lease()
    print(value["status"])
    print(f"ATLAS_V4_INSTALL_CLOCK_PREFLIGHT_SAMPLES={value['samples']}")
    print(f"ATLAS_V4_INSTALL_CLOCK_INITIAL_BOUND={value['initial_bound_ms']}ms")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        raise SystemExit(f"ATLAS_V4_INSTALL_CLOCK_LEASE_PREFLIGHT_REFUSED:{exc}") from None
