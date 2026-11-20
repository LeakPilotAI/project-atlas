"""R22 precise dual-NTP source-only real-network proof; READ ONLY.

Verifies the new authenticated nanosecond issuance against actual Google and
Cloudflare UDP NTP peers on the Windows machine. No credentials, financial
accounts, release selection, market/order APIs or PAPER authority.
A workspace observation cannot replace an installed selected original clock.
"""
from __future__ import annotations

import json

from scripts.observation_runtime.atlas_independent_ntp_clock import (
    IndependentNtpClock,
)

SCHEMA = "ATLAS_R22_SOURCE_ONLY_SUBSECOND_NTP_REAL_NETWORK_READONLY_V1"
RUNTIME = "atlas-r22-source-only-subsecond-utc-proof"


def inspect():
    clock = IndependentNtpClock(runtime_id=RUNTIME, lifetime=90)
    try:
        issued = clock.sample_precise()
        if (
            issued.get("schema") != "ATLAS_INDEPENDENT_PRECISE_UTC_V1"
            or not clock.verify_precise(issued)
            or not 0 <= issued["uncertainty_ms"] <= 1000
            or clock.evidence.get("domain")
            != "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS"
            or clock.evidence.get("financial_authority") is not False
        ):
            raise ValueError("R22_AUTHENTIC_ORIGINAL_TWO_PEER_UTC_REQUIRED")
        legacy = clock.sample()
        if not clock.verify(legacy):
            raise ValueError("R22_BACKWARDS_COMPATIBLE_UTC_REQUIRED")
        return {
            "schema": SCHEMA,
            "status": "REAL_TWO_PEER_PRECISE_UTC_SOURCEONLY_VERIFIED",
            "independent_time_sources": 2,
            "trusted_subsecond_sample_verified": True,
            "trusted_subsecond_fraction_observed": (
                issued["utc_ns"] % 1_000_000_000 != 0
            ),
            "independent_ntp_uncertainty_ms": issued["uncertainty_ms"],
            "independent_peer_difference_ms": clock.evidence["peer_difference_ms"],
            "original_whole_second_clock_retained": True,
            "native_selected_source_installation_verified": False,
            "native_financial_clock_grant_issued": False,
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        }
    finally:
        clock.revoke()


if __name__ == "__main__":
    print(json.dumps(inspect(), sort_keys=True))
