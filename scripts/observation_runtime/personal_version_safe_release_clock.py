"""Version-safe native release/clock identity, SOURCE-ONLY; no financial grant.

A future installed application can derive its release identity from its own native
module path and the verified selector rather than embed its own later-created
receipt SHA in source (which would be self-referential). No V8 r12 selection
or PAPER clock construction is authorized by this module.
"""
import re
from pathlib import Path

V7_R11_HEAD = "933482b46a31af43270a193a94a83353e945fbecc4eb4661e8b7f8e9c8262997"
V7_RELEASE = "af96bec0484a8e43f9965610e071a907a0d316bf"
SELECTOR_NATIVE = [4004218753, 65536, 1532785]
RELEASE_PARENT = Path("D:/AtlasRuntime/releases")
CLOCK_RELATIVE = Path("scripts/observation_runtime/personal_version_safe_release_clock.py")


def admit_version_safe_clock_source(*, source_file, records):
    """Pure, fail-closed source/selector binding: never an operational approval.

    Returns selected native head/spec only when a NEW installed candidate
    physically owns the given module location and has an append-only r12 chain.
    The installed files/receipt are independently reopened by the native verifier.
    """
    from scripts.release_selection import digest, validate_spec

    source = Path(source_file)
    if (not source.is_absolute() or source.name != CLOCK_RELATIVE.name
            or source.parent.name != "observation_runtime"
            or source.parent.parent.name != "scripts"):
        raise ValueError("VERSION_SAFE_CLOCK_INSTALLED_SOURCE_REQUIRED")
    release_root = source.parents[2]
    if (release_root.parent != RELEASE_PARENT
            or not re.fullmatch("[0-9a-f]{40}", release_root.name)
            or release_root.name == V7_RELEASE):
        raise ValueError("VERSION_SAFE_CLOCK_OWN_RELEASE_REQUIRED")
    if (type(records) is not list or len(records) != 12
            or type(records[10]) is not dict
            or records[10].get("revision") != 11
            or digest(records[10]) != V7_R11_HEAD
            or type(records[10].get("selected")) is not dict
            or records[10]["selected"].get("release") != V7_RELEASE):
        raise ValueError("VERSION_SAFE_CLOCK_NATIVE_V7_PREDECESSOR_REQUIRED")
    r12 = records[11]
    if (type(r12) is not dict or r12.get("revision") != 12
            or r12.get("action") != "SELECT"
            or r12.get("previous") != V7_R11_HEAD
            or r12.get("restores") is not None):
        raise ValueError("VERSION_SAFE_CLOCK_NATIVE_NEW_SELECT_REQUIRED")
    spec = validate_spec(r12.get("selected"), "WINDOWS_LOCAL")
    if (spec["release"] != release_root.name
            or Path(spec["root"]) != release_root):
        raise ValueError("VERSION_SAFE_CLOCK_SELECTED_CODE_MISMATCH")
    return digest(r12), spec


def require_native_version_safe_clock_source(*, deep=True):
    """Read native selection and optionally reopen installed code; no NTP/order.

    Unselected sources refuse before accessing network time. An installed caller
    must separately establish genuine independent UTC and financial approvals.
    """
    from scripts.release_selection import NativeInstalledReleaseVerifier
    from scripts.release_selection_store import NativeSelectionStore

    # Do not allow the workspace copy to masquerade as an installed release.
    source = Path(__file__).absolute()
    if source.parent.parent.parent.parent != RELEASE_PARENT:
        raise ValueError("VERSION_SAFE_CLOCK_INSTALLED_SOURCE_REQUIRED")
    store = NativeSelectionStore(root=r"D:\AtlasRuntime\selection", native_root=list(SELECTOR_NATIVE))
    try:
        with store.locked():
            head, spec = admit_version_safe_clock_source(
                source_file=source, records=store.records())
            if deep:
                with NativeInstalledReleaseVerifier().open(spec) as receipt:
                    if receipt.get("source_commit") != spec["release"]:
                        raise ValueError("VERSION_SAFE_CLOCK_NATIVE_RECEIPT_MISMATCH")
        return head
    finally:
        store.close()
