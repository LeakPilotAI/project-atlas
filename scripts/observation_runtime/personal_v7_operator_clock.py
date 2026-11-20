"""V7 PAPER operator UTC port, source-only and NOT a financial grant.

An exact local V7 selected native application plus a real two-peer NTP clock
are both required. No activation record, writer session or financial balance is
created here. It is intentionally not imported by any Start Atlas shortcut.
"""
import os
from pathlib import Path

from scripts.observation_runtime.atlas_independent_ntp_clock import (
    IndependentNtpClock, SOURCE,
)
from scripts.observation_runtime.atlas_v7_commissioning_ntp_probe import (
    V7_RELEASE, V7_ARTIFACT, SELECTOR_HEAD, SELECTOR_ROOT_NATIVE_ID,
    verify_selected_v7,
)

PROFILE = "V7_INDEPENDENT_NTP_OPERATOR_CLOCK_V1"


def _require_current_v7_selected():
    """Cheap bounded native selection chain read, never a financial grant."""
    from scripts.release_selection import digest
    from scripts.release_selection_store import NativeSelectionStore
    store = NativeSelectionStore(
        root=str(Path("D:/AtlasRuntime/selection")),
        native_root=list(SELECTOR_ROOT_NATIVE_ID),
    )
    try:
        with store.locked():
            records = store.records()
            if (len(records) != 11 or records[-1].get("revision") != 11
                    or digest(records[-1]) != SELECTOR_HEAD
                    or type(records[-1].get("selected")) is not dict
                    or records[-1]["selected"].get("release") != V7_RELEASE
                    or records[-1]["selected"].get("artifact_digest") != V7_ARTIFACT):
                raise ValueError("V7_OPERATOR_CLOCK_NATIVE_SELECTOR_CHANGED")
    finally:
        store.close()


class NativeV7PaperOperatorClock:
    """Existing QD operator-authority time surface, with V7 native custody.

    Construction verifies the complete installed release once, then each
    sample requires the same selected head. All authority still comes from the
    distinct native activation, financial writer, E1 source and Stop gates.
    """

    def __init__(self, *, runtime_id):
        if type(runtime_id) is not str or not runtime_id or len(runtime_id) > 256:
            raise ValueError("V7_OPERATOR_CLOCK_RUNTIME_ID_REQUIRED")
        # Avoid leaking installed native handles on a failed clock acquisition.
        if verify_selected_v7() is not True:
            raise ValueError("V7_OPERATOR_NATIVE_RELEASE_READBACK_REQUIRED")
        self._runtime_id = runtime_id
        self._pid = os.getpid()
        self._revoked = False
        self._clock = IndependentNtpClock(runtime_id=runtime_id)
        self._bound_clock = self._clock
        try:
            self.require_operational(runtime_id)
        except (ValueError, OSError, TypeError):
            self.revoke()
            raise

    def revoke(self):
        self._revoked = True
        # Revoke the original bound provider even if a caller replaced the
        # public _clock attribute. Never invoke an untrusted replacement.
        bound = getattr(self, "_bound_clock", None)
        if type(bound) is IndependentNtpClock:
            bound.revoke()

    def require_operational(self, runtime_id):
        if (type(self) is not NativeV7PaperOperatorClock
                or self._revoked or os.getpid() != self._pid
                or runtime_id != self._runtime_id
                or self._clock is not self._bound_clock
                or type(self._clock) is not IndependentNtpClock):
            self.revoke()
            raise ValueError("V7_OPERATOR_CLOCK_OWNER_OR_RUNTIME_CHANGED")
        try:
            _require_current_v7_selected()
            self._clock.require_operational(runtime_id)
            if (self._clock.evidence.get("source") != SOURCE
                    or self._clock.evidence.get("domain") != "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS"
                    or self._clock.evidence.get("financial_authority") is not False
                    or type(self._clock.evidence.get("bound_ms")) is not int
                    or not 0 <= self._clock.evidence["bound_ms"] <= 1000):
                raise ValueError("V7_OPERATOR_CLOCK_NTP_SOURCE_EVIDENCE_REFUSED")
        except (ValueError, OSError, TypeError, KeyError):
            self.revoke()
            raise ValueError("V7_OPERATOR_CLOCK_SELECTED_SOURCE_REVOKED") from None
        return self

    def sample(self):
        self.require_operational(self._runtime_id)
        return self._clock.sample()

    def __call__(self):
        return self.sample()["utc"]

    def verify(self, value):
        try:
            self.require_operational(self._runtime_id)
            return self._clock.verify(value)
        except ValueError:
            return False

    def runtime_sample(self):
        self.require_operational(self._runtime_id)
        return self._clock.runtime_sample()

    def verify_runtime_sample(self, value):
        try:
            self.require_operational(self._runtime_id)
            return self._clock.verify_runtime_sample(value)
        except ValueError:
            return False

    def runtime_clock(self):
        owner = self

        class RuntimeClock:
            def sample(self):
                return owner.runtime_sample()

            def verify(self, value):
                return owner.verify_runtime_sample(value)

            def __call__(self):
                return owner()

        return RuntimeClock()
