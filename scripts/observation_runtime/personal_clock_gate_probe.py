"""Read-only native Windows PAPER clock gate check. Never grants activation."""
from __future__ import annotations

import json


def inspect_personal_clock_gate(*, source="time.windows.com,0x9") -> dict:
    from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock
    clock = None
    try:
        clock = LocalWindowsClock(expected_source=source,
                                  runtime_id="atlas-clock-readonly-probe", lifetime=30)
        return {"schema": "ATLAS_PERSONAL_CLOCK_GATE_PROBE_V1",
                "trusted_clock_verified_for_probe": True,
                "uncertainty_ms": clock.evidence["bound_ms"],
                "domain": clock.evidence["domain"],
                "native_activation_verified": False,
                "operator_lease_verified": False,
                "forward_financial_write_authorized": False,
                "live_order_authorized": False}
    except (ValueError, OSError) as exc:
        return {"schema": "ATLAS_PERSONAL_CLOCK_GATE_PROBE_V1",
                "trusted_clock_verified_for_probe": False,
                "blocker": str(exc).split(":", 1)[0],
                "native_activation_verified": False,
                "operator_lease_verified": False,
                "forward_financial_write_authorized": False,
                "live_order_authorized": False}
    finally:
        if clock is not None:
            clock.revoke()


def main():
    print(json.dumps(inspect_personal_clock_gate(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
