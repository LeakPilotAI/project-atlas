"""Read-only V7 dual-NTP commissioning-clock evidence. Never financial authority.

The standalone workspace source may inspect the genuine selected native V7
record and two current external public NTP peers. It does not create a runtime
clock for a financial writer, grant source rights, or waive native custody.
"""
import hashlib
import json
from pathlib import Path

V7_RELEASE = "af96bec0484a8e43f9965610e071a907a0d316bf"
V7_ARTIFACT = "94374eda7eea82ac1c44905b21ab56b524128bc49e4253f3522838d230961827"
V7_INSTALL_RECEIPT_SHA256 = "105c89ab10d20771474fe030489da7aabeb6900f22be57d25b745135bf28ac4d"
SUPPORT_ID = "eec34ad24a3fc6dd8af1ef031f3046a96f7f90f8188973b4075012461c8880c1"
SUPPORT_RECEIPT_SHA256 = "b666acef1dae1dc24f0da3173050a43eecdb9f6b3650a9ee01434f4047d56761"
SELECTOR_HEAD = "933482b46a31af43270a193a94a83353e945fbecc4eb4661e8b7f8e9c8262997"
SELECTOR_RECORD_SHA256 = "3804a749f88cbf6da1873f71b917ef440ca801e31f4a93f73759df4382898c4d"
SELECTOR_ROOT_NATIVE_ID = [4004218753, 65536, 1532785]
SOURCE_ID = "ATLAS_NTP_V1:time.cloudflare.com+time.google.com"
RUNTIME_ID = "atlas-v7-readonly-commissioning-clock"


def verify_selected_v7():
    """Native append-only selection check and independent installed-app readback."""
    from scripts.release_selection import NativeInstalledReleaseVerifier, digest
    from scripts.release_selection_store import NativeSelectionStore

    root = Path("D:/AtlasRuntime")
    record_path = root / "selection/r0011.json"
    raw = record_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SELECTOR_RECORD_SHA256:
        raise ValueError("V7_COMMISSIONING_SELECTOR_RECORD_CHANGED")

    support = root / "support-installations" / SUPPORT_ID / "receipt.json"
    if hashlib.sha256(support.read_bytes()).hexdigest() != SUPPORT_RECEIPT_SHA256:
        raise ValueError("V7_COMMISSIONING_SUPPORT_RECEIPT_CHANGED")
    receipt = Path("D:/Work/Project Atlas/logs/diagnostics") / (
        "qd-unselected-release-" + V7_RELEASE + ".json")
    if hashlib.sha256(receipt.read_bytes()).hexdigest() != V7_INSTALL_RECEIPT_SHA256:
        raise ValueError("V7_COMMISSIONING_APPLICATION_RECEIPT_CHANGED")

    store = NativeSelectionStore(root=str(root / "selection"),
                                 native_root=list(SELECTOR_ROOT_NATIVE_ID))
    try:
        with store.locked():
            rows = store.records()
            if (len(rows) != 11 or rows[-1]["revision"] != 11
                    or digest(rows[-1]) != SELECTOR_HEAD
                    or rows[-1]["selected"].get("release") != V7_RELEASE
                    or rows[-1]["selected"].get("artifact_digest") != V7_ARTIFACT
                    or rows[-1]["selected"].get("receipt_sha256") != V7_INSTALL_RECEIPT_SHA256):
                raise ValueError("V7_COMMISSIONING_NATIVE_SELECTION_NOT_PINNED")
            selected = rows[-1]["selected"]
        with NativeInstalledReleaseVerifier().open(selected):
            pass
    finally:
        store.close()
    return True


def inspect_v7_independent_ntp_clock():
    """One bounded diagnostic acquisition; a failed source never activates anything."""
    clock = None
    try:
        verify_selected_v7()
        from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock
        clock = IndependentNtpClock(runtime_id=RUNTIME_ID, lifetime=30)
        clock.require_operational(RUNTIME_ID)
        sample = clock.sample()
        if (clock.evidence.get("domain") != "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS"
                or clock.evidence.get("source") != SOURCE_ID
                or clock.evidence.get("financial_authority") is not False
                or clock.evidence.get("os_windows_time_service_required") is not False
                or type(clock.evidence.get("bound_ms")) is not int
                or not 0 <= clock.evidence["bound_ms"] <= 1000
                or clock.evidence.get("peer_difference_ms", 1000) > 250
                or not clock.verify(sample)):
            raise ValueError("V7_COMMISSIONING_INDEPENDENT_NTP_EVIDENCE_REFUSED")
        return {
            "schema": "ATLAS_V7_READONLY_INDEPENDENT_NTP_CLOCK_PROBE_V1",
            "trusted_clock_verified_for_probe": True,
            "source": SOURCE_ID,
            "selected_release": V7_RELEASE,
            "selected_revision": 11,
            "uncertainty_ms": clock.evidence["bound_ms"],
            "peer_difference_ms": clock.evidence["peer_difference_ms"],
            "public_ntp_authenticated": False,
            "windows_time_service_required": False,
            "continuous_financial_clock_lease_verified": False,
            "financial_clock_authorized": False,
            "native_activation_verified": False,
            "forward_financial_write_authorized": False,
            "live_order_authorized": False,
        }
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return {
            "schema": "ATLAS_V7_READONLY_INDEPENDENT_NTP_CLOCK_PROBE_V1",
            "trusted_clock_verified_for_probe": False,
            "blocker": str(exc).split(":", 1)[0][:120],
            "public_ntp_authenticated": False,
            "continuous_financial_clock_lease_verified": False,
            "financial_clock_authorized": False,
            "native_activation_verified": False,
            "forward_financial_write_authorized": False,
            "live_order_authorized": False,
        }
    finally:
        if clock is not None:
            clock.revoke()
