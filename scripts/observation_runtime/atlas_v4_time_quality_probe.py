"""Read-only native Windows clock quality probe for the reviewed V4 release.

Invoked as ``python -B -m scripts.observation_runtime.atlas_v4_time_quality_probe``
to avoid Windows PowerShell native-command quote/argument mangling with ``-c``.
It does not install, select, enroll, start a runtime, or change Windows Time.
"""

from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock

EXPECTED_PEERS = "time.cloudflare.com,0x8 time.google.com,0x8"
RUNTIME_ID = "atlas-v4-time-qualification-only"


def main():
    clock = LocalWindowsClock(
        expected_source=EXPECTED_PEERS,
        runtime_id=RUNTIME_ID,
        lifetime=240,
    )
    try:
        clock.require_operational(RUNTIME_ID)
        print(f"NATIVE_CLOCK_QUALITY_ACCEPTED:{clock.evidence['bound_ms']}ms")
    finally:
        clock.revoke()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        # A native quality refusal is not a parser failure. Keep the exact
        # approved clock diagnostic visible to the elevated operator.
        raise SystemExit(f"NATIVE_CLOCK_QUALITY_REFUSED:{exc}") from None
