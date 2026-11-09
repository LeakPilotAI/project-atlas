"""Version-safe native release/clock identity, SOURCE-ONLY; no financial grant.

A future installed application can derive its release identity from its own native
module path and the verified selector rather than embed its own later-created
receipt SHA in source (which would be self-referential). This module cannot
select a release, authorize financial PAPER operations, or construct a clock
from the unselected workspace source.
"""
import os
import re
from pathlib import Path

from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock, SOURCE

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


# This capability is a source-only prerequisite for a FUTURE immutable release.
# It is not wired into PAPER activation and is not a financial authorization.
PROFILE = "VERSION_SAFE_INDEPENDENT_NTP_OPERATOR_CLOCK_V1"


class NativeVersionSafePaperOperatorClock:
    """Own-release, own-selection independent UTC; no financial writer/grant.

    Selection and installed-image evidence precede network access. The same
    selected head, process, runtime ID and genuine NTP object are required on
    every sample and verification. Any failure permanently revokes this clock.
    """

    def __init__(self, *, runtime_id):
        if type(runtime_id) is not str or not runtime_id or len(runtime_id) > 256:
            raise ValueError("VERSION_SAFE_CLOCK_RUNTIME_ID_REQUIRED")
        selected_head = require_native_version_safe_clock_source(deep=True)
        self._pid = os.getpid()
        self._runtime_id = runtime_id
        self._selected_head = selected_head
        self._revoked = False
        self._clock = IndependentNtpClock(runtime_id=runtime_id)
        self._bound_clock = self._clock
        try:
            self.require_operational(runtime_id)
        except (OSError, TypeError, ValueError, KeyError):
            self.revoke()
            raise

    def revoke(self):
        self._revoked = True
        bound = getattr(self, "_bound_clock", None)
        if type(bound) is IndependentNtpClock:
            bound.revoke()

    def require_operational(self, runtime_id):
        if (type(self) is not NativeVersionSafePaperOperatorClock
                or self._revoked or self._pid != os.getpid()
                or type(runtime_id) is not str or runtime_id != self._runtime_id
                or type(self._clock) is not IndependentNtpClock
                or self._clock is not self._bound_clock):
            self.revoke()
            raise ValueError("VERSION_SAFE_CLOCK_OWNER_OR_IDENTITY_CHANGED")
        try:
            if require_native_version_safe_clock_source(deep=False) != self._selected_head:
                raise ValueError("VERSION_SAFE_CLOCK_NATIVE_SELECTION_CHANGED")
            self._clock.require_operational(runtime_id)
            evidence = self._clock.evidence
            if (type(evidence) is not dict
                    or evidence.get("source") != SOURCE
                    or evidence.get("domain") != "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS"
                    or evidence.get("financial_authority") is not False
                    or type(evidence.get("bound_ms")) is not int
                    or not 0 <= evidence["bound_ms"] <= 1000):
                raise ValueError("VERSION_SAFE_CLOCK_NTP_SOURCE_REFUSED")
        except (OSError, ValueError, TypeError, KeyError):
            self.revoke()
            raise ValueError("VERSION_SAFE_CLOCK_NATIVE_OR_NTP_REVOKED") from None
        return self

    def sample(self):
        self.require_operational(self._runtime_id)
        return self._clock.sample()

    def __call__(self):
        return self.sample()["utc"]

    def verify(self, sample):
        try:
            self.require_operational(self._runtime_id)
            return self._clock.verify(sample)
        except ValueError:
            return False

    def runtime_sample(self):
        self.require_operational(self._runtime_id)
        return self._clock.runtime_sample()

    def verify_runtime_sample(self, sample):
        try:
            self.require_operational(self._runtime_id)
            return self._clock.verify_runtime_sample(sample)
        except ValueError:
            return False

    def runtime_clock(self):
        owner = self
        class RuntimeClock:
            def sample(self):
                return owner.runtime_sample()
            def verify(self, sample):
                return owner.verify_runtime_sample(sample)
            def __call__(self):
                return owner()
        return RuntimeClock()


def require_version_safe_release_digest(*, clock, runtime_id, release_digest):
    """Bind a financial caller's release digest to the same selected native head.

    Actual construction already deep-verified installed bytes; this repeats the
    exact current selection and compares the independently selected artifact.
    No new selection, approval, account or provider action is performed.
    """
    from scripts.release_selection_store import NativeSelectionStore
    if (type(clock) is not NativeVersionSafePaperOperatorClock
            or type(release_digest) is not str
            or not re.fullmatch("[0-9a-f]{64}", release_digest)):
        raise ValueError("VERSION_SAFE_CLOCK_EXACT_RELEASE_DIGEST_REQUIRED")
    clock.require_operational(runtime_id)
    source = Path(__file__).absolute()
    if source.parent.parent.parent.parent != RELEASE_PARENT:
        raise ValueError("VERSION_SAFE_CLOCK_INSTALLED_SOURCE_REQUIRED")
    store = NativeSelectionStore(root=r"D:\AtlasRuntime\selection", native_root=list(SELECTOR_NATIVE))
    try:
        with store.locked():
            head, spec = admit_version_safe_clock_source(
                source_file=source, records=store.records())
            if (head != clock._selected_head
                    or spec["artifact_digest"] != release_digest):
                raise ValueError("VERSION_SAFE_CLOCK_ARTIFACT_OR_SELECTION_MISMATCH")
        return True
    finally:
        store.close()
