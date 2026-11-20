"""V8 native PAPER clock identity: selected-code proof, NOT financial authority.

Unselected V8 must not create any clock. A future genuine V8 selection must
be separately authorized; once selected, this binds to that exact native head.
The currently installed V8 application does NOT contain this new source.
"""
import hashlib
import os
from pathlib import Path

from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock, SOURCE

PROFILE = "V8_INDEPENDENT_NTP_OPERATOR_CLOCK_V1"
APP = "c8cc4846508b29483d10a0b4c4353f8a26f1fc9c"
ARTIFACT = "65c4b4661ec6aef7359e9dae716a416327379f5082a5b309ccdb5a148a569c95"
APP_RECEIPT = "ecb94e00e262e371caea494b1cc552352c892fa437a3b5f4946b54f7f863ae34"
SUPPORT = "03122857979ccbc97572acda7a63d98640bb081c868de13929dcedd556883a26"
SUPPORT_RECEIPT = "85bd24430576a8cfde7735c8412263da4ca6aea8459c55ec3d70c1f6a0c62d60"
V7_APP = "af96bec0484a8e43f9965610e071a907a0d316bf"
V7_R11_HEAD = "933482b46a31af43270a193a94a83353e945fbecc4eb4661e8b7f8e9c8262997"
ROOT = Path(r"D:\AtlasRuntime")
SELECTOR_NATIVE = [4004218753, 65536, 1532785]


def require_selected_v8(*, deep):
    """Return current immutable r12 head only with exact V7->V8 native chain.

    Read-only ledger/selector operation. Deep mode verifies physical sources.
    """
    from scripts.release_selection import NativeInstalledReleaseVerifier, digest, validate_spec
    from scripts.release_selection_store import NativeSelectionStore

    app_receipt = Path(r"D:\Work\Project Atlas\logs\diagnostics") / (
        "qd-unselected-release-" + APP + ".json")
    support_receipt = ROOT / "support-installations" / SUPPORT / "receipt.json"
    if (hashlib.sha256(app_receipt.read_bytes()).hexdigest() != APP_RECEIPT
            or hashlib.sha256(support_receipt.read_bytes()).hexdigest() != SUPPORT_RECEIPT):
        raise ValueError("V8_OPERATOR_NATIVE_APPLICATION_OR_SUPPORT_RECEIPT_CHANGED")
    store = NativeSelectionStore(root=str(ROOT / "selection"),
                                 native_root=list(SELECTOR_NATIVE))
    try:
        with store.locked():
            rows = store.records()
            if (len(rows) != 12 or rows[10]["revision"] != 11
                    or digest(rows[10]) != V7_R11_HEAD
                    or rows[10]["selected"].get("release") != V7_APP):
                raise ValueError("V8_OPERATOR_SELECTED_NATIVE_V7_PREDECESSOR_REQUIRED")
            r12 = rows[11]
            spec = r12.get("selected")
            if (r12.get("revision") != 12 or r12.get("action") != "SELECT"
                    or r12.get("previous") != V7_R11_HEAD
                    or r12.get("restores") is not None
                    or type(spec) is not dict
                    or spec.get("release") != APP
                    or spec.get("artifact_digest") != ARTIFACT
                    or spec.get("receipt_sha256") != APP_RECEIPT
                    or spec.get("root") != str(ROOT / "releases" / APP)
                    or spec.get("receipt") != str(app_receipt)
                    or spec.get("schema") != "QD_INSTALLED_RELEASE_REFERENCE_V1"
                    or spec.get("domain") != "WINDOWS_LOCAL"):
                raise ValueError("V8_OPERATOR_SELECTED_NATIVE_R12_BOUNDARY_REQUIRED")
            validate_spec(spec, "WINDOWS_LOCAL")
            head = digest(r12)
            if deep:
                with NativeInstalledReleaseVerifier().open(spec):
                    pass
        if deep:
            from scripts import support_deployment
            import json
            manifest = json.loads((Path(r"D:\Work\Project Atlas\logs\diagnostics") /
                "atlas-v8-ntp-support-offline-proposal-20261108-r11" /
                "deployment.json").read_bytes())
            if manifest["application"]["release"] != APP:
                raise ValueError("V8_OPERATOR_SUPPORT_WRONG_APPLICATION")
            support_deployment.verify_deployment(
                manifest, expected_receipt_sha256=SUPPORT_RECEIPT)
        return head
    finally:
        store.close()


class NativeV8PaperOperatorClock:
    """Exact V8 native clock capability; not an activation, writer or provider."""

    def __init__(self, *, runtime_id):
        if type(runtime_id) is not str or not runtime_id or len(runtime_id) > 256:
            raise ValueError("V8_OPERATOR_RUNTIME_ID_REQUIRED")
        selected_head = require_selected_v8(deep=True)
        self._pid = os.getpid()
        self._runtime_id = runtime_id
        self._selected_head = selected_head
        self._revoked = False
        self._clock = IndependentNtpClock(runtime_id=runtime_id)
        self._bound_clock = self._clock
        try:
            self.require_operational(runtime_id)
        except (OSError, ValueError, TypeError):
            self.revoke()
            raise

    def revoke(self):
        self._revoked = True
        bound = getattr(self, "_bound_clock", None)
        if type(bound) is IndependentNtpClock:
            bound.revoke()

    def require_operational(self, runtime_id):
        if (type(self) is not NativeV8PaperOperatorClock
                or self._revoked or self._pid != os.getpid()
                or runtime_id != self._runtime_id
                or type(self._clock) is not IndependentNtpClock
                or self._clock is not self._bound_clock):
            self.revoke()
            raise ValueError("V8_OPERATOR_CLOCK_OWNER_OR_IDENTITY_CHANGED")
        try:
            if require_selected_v8(deep=False) != self._selected_head:
                raise ValueError("V8_OPERATOR_NATIVE_SELECTION_CHANGED")
            self._clock.require_operational(runtime_id)
            evidence = self._clock.evidence
            if (evidence.get("source") != SOURCE
                    or evidence.get("domain") != "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS"
                    or evidence.get("financial_authority") is not False
                    or type(evidence.get("bound_ms")) is not int
                    or not 0 <= evidence["bound_ms"] <= 1000):
                raise ValueError("V8_OPERATOR_CLOCK_TWO_PEER_SOURCE_REFUSED")
        except (OSError, ValueError, TypeError, KeyError):
            self.revoke()
            raise ValueError("V8_OPERATOR_NATIVE_OR_NTP_REVOKED") from None
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
