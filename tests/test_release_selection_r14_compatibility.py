"""R14 code-only native selector compatibility, zero operational selection.

Tests use the existing small immutable installed *receipt* and journal only,
plus fake in-memory selection store, native owner and installed verifier.
Never opens the 10,519 installed files or writes D:/AtlasRuntime/selection.
"""
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import release_selection as selection

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "logs/diagnostics" / (
    "qd-unselected-release-" + selection.R14_CODE_RELEASE + ".json")
JOURNAL = RECEIPT.with_suffix(".pending.jsonl")


@pytest.fixture(scope="module")
def verified_r14_evidence():
    raw = RECEIPT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == selection.R14_RECEIPT_SHA256
    receipt = selection.strict(raw)
    journal = JOURNAL.read_bytes()
    assert 0 < len(journal) < 4096
    reference = selection.validate_spec({
        "schema": "QD_INSTALLED_RELEASE_REFERENCE_V1",
        "domain": "WINDOWS_LOCAL",
        "release": selection.R14_CODE_RELEASE,
        "root": str(Path("D:/AtlasRuntime/releases") / selection.R14_CODE_RELEASE),
        "receipt": str(RECEIPT),
        "receipt_sha256": selection.R14_RECEIPT_SHA256,
        "artifact_digest": selection.R14_ARTIFACT_DIGEST,
    }, "WINDOWS_LOCAL")
    return reference, receipt, journal


def test_r14_exact_final_receipt_and_two_stage_ack_are_eligible(verified_r14_evidence):
    spec, receipt, journal = verified_r14_evidence
    assert selection.validate_native_install_ack(spec, receipt, journal) is True
    assert receipt["selected"] is False
    assert receipt["financial_effects"] is False
    assert receipt["provider_connections"] is False
    assert receipt["operational_acceptance"] is False


@pytest.mark.parametrize("field,value", [
    ("receipt_sha256", "0" * 64),
    ("artifact_digest", "0" * 64),
])
def test_r14_reference_pin_tampering_refuses(verified_r14_evidence, field, value):
    spec, receipt, journal = verified_r14_evidence
    with pytest.raises(ValueError, match="SELECTION_R14_EXACT_RECEIPT_REQUIRED"):
        selection.validate_native_install_ack({**spec, field:value}, receipt, journal)


@pytest.mark.parametrize("field,value", [
    ("archive_sha256", "0" * 64),
    ("inventory_sha256", "0" * 64),
    ("stage", "SOURCE_ONLY"),
])
def test_r14_receipt_changed_scope_refuses(verified_r14_evidence, field, value):
    spec, receipt, journal = verified_r14_evidence
    with pytest.raises(ValueError, match="SELECTION_R14_EXACT_RECEIPT_REQUIRED"):
        selection.validate_native_install_ack(spec, {**receipt, field:value}, journal)


@pytest.mark.parametrize("mutation", [
    "no_journal", "only_intent", "only_pending", "duplicate_pending",
    "extra_terminal", "wrong_source", "wrong_root", "wrong_archive",
    "intent_financial", "intent_selection", "intent_provider",
    "pending_financial", "pending_selection", "wrong_digest",
    "extra_field", "duplicate_json_keys", "nonfinite_value",
])
def test_r14_journal_fail_closed_on_any_nonexact_ack(verified_r14_evidence, mutation):
    spec, receipt, original = verified_r14_evidence
    first, second = [json.loads(line) for line in original.splitlines()]
    if mutation == "no_journal":
        data = b""
    elif mutation == "only_intent":
        data = json.dumps(first).encode()
    elif mutation == "only_pending":
        data = json.dumps(second).encode()
    elif mutation == "duplicate_pending":
        data = original + b"\n" + original.splitlines()[1]
    elif mutation == "extra_terminal":
        data = original + b'\n{"stage":"UNSELECTED_CODE_INSTALL_VERIFIED"}'
    else:
        if mutation == "wrong_source": first["source_commit"] = "f" * 40
        elif mutation == "wrong_root": first["destination"] = str(spec["root"]) + "-renamed"
        elif mutation == "wrong_archive": first["archive_sha256"] = "0" * 64
        elif mutation == "intent_financial": first["financial_authority"] = True
        elif mutation == "intent_selection": first["selection_allowed"] = True
        elif mutation == "intent_provider": first["provider_access"] = True
        elif mutation == "pending_financial": second["financial_authority"] = True
        elif mutation == "pending_selection": second["selection_allowed"] = True
        elif mutation == "wrong_digest": second["artifact_digest"] = "0" * 64
        elif mutation == "extra_field": second["approved_for_paper"] = True
        data = (json.dumps(first) + "\n" + json.dumps(second)).encode()
        if mutation == "duplicate_json_keys":
            data = data.replace(b'"stage":', b'"stage":"FORGED","stage":', 1)
        elif mutation == "nonfinite_value":
            data = data.replace(b'"stage":', b'"bad":NaN,"stage":', 1)
    with pytest.raises((ValueError, KeyError)):
        selection.validate_native_install_ack(spec, receipt, data)


def test_other_releases_keep_exact_original_trailing_ack():
    spec = {"release": "a"*40, "receipt_sha256": "b"*64}
    old = {"stage": "UNSELECTED_CODE_INSTALL_VERIFIED",
           "receipt_sha256": spec["receipt_sha256"]}
    assert selection.validate_native_install_ack(
        spec, {}, b'{"stage":"SOURCE_INTENT"}\n' + json.dumps(old).encode()) is True
    for wrong in ({"stage":"NATIVE_READBACK_VERIFIED_FINAL_RECEIPT_PENDING",
                   "receipt_sha256":spec["receipt_sha256"]},
                  {"stage": "UNSELECTED_CODE_INSTALL_VERIFIED",
                   "receipt_sha256": "0"*64}):
        with pytest.raises(ValueError, match="SELECTION_INSTALL_ACK_REQUIRED"):
            selection.validate_native_install_ack(spec, {}, json.dumps(wrong).encode())


def test_r14_actual_native_verifier_orchestration_is_intercepted(monkeypatch, verified_r14_evidence):
    """The real verifier does all R14 checks, but native rescans are stubbed."""
    from scripts import build_release_candidate as source
    from scripts import install_verified_release as native
    from scripts.observation_runtime import personal_release_identity as identity

    spec, receipt, journal = verified_r14_evidence
    reads, native_calls = [], []
    def fake_source_bytes(parent, name, maximum_bytes):
        assert name in (RECEIPT.name, JOURNAL.name)
        if name == JOURNAL.name:
            assert maximum_bytes == 4096
        reads.append(name)
        return RECEIPT.read_bytes() if name == RECEIPT.name else journal

    class FakeIdentity:
        def __init__(self, *, receipt, artifact_digest):
            assert receipt["source_commit"] == spec["release"]
            assert artifact_digest == spec["artifact_digest"]
            native_calls.append("original_owner_open_intercepted")
            self.outputs = {".": SimpleNamespace(_verify=lambda: native_calls.append("root_verified"))}
        def close(self):
            native_calls.append("original_owner_closed")

    def fake_readback(path, value, digest, *, timeout):
        assert path == Path(spec["root"])
        assert digest == spec["artifact_digest"]
        assert timeout == 180
        native_calls.append("installed_child_readback_intercepted")

    monkeypatch.setattr(source, "source_bytes", fake_source_bytes)
    monkeypatch.setattr(native, "installed_readback", fake_readback)
    monkeypatch.setattr(identity, "NativePersonalReleaseIdentity", FakeIdentity)
    with selection.NativeInstalledReleaseVerifier().open(spec) as seen:
        assert seen["source_commit"] == selection.R14_CODE_RELEASE
    assert reads == [RECEIPT.name, JOURNAL.name]
    assert native_calls == ["original_owner_open_intercepted",
                            "installed_child_readback_intercepted",
                            "root_verified", "original_owner_closed"]


def synthetic_native_selector(profile):
    """Construct ONLY an inert test double; do not create NativeSelectionStore."""
    class FakeStore:
        domain = "WINDOWS_LOCAL"
        def __init__(self):
            self.rows=[]
            self.published=[]
        @contextmanager
        def locked(self):
            yield
        def records(self):
            return list(self.rows)
        def publish(self,row):
            self.published.append(row)
            self.rows.append(row)
    class FakeVerifier:
        domain = "WINDOWS_LOCAL"
        @contextmanager
        def open(self, target):
            assert target["release"] == selection.R14_CODE_RELEASE
            yield {"selected":False, "operational_acceptance":False}
    class FakeClock:
        def __init__(self):
            self.calls=[]
        def require_operational(self, runtime_id):
            self.calls.append(runtime_id)
    store, verifier, clock = FakeStore(), FakeVerifier(), FakeClock()
    obj = selection.ReleaseSelector.__new__(selection.ReleaseSelector)
    obj.store, obj.verifier, obj.clock = store, verifier, clock
    obj.domain, obj.clock_profile = "WINDOWS_LOCAL", profile
    obj._ports=(store,verifier,clock,"WINDOWS_LOCAL",profile)
    obj._known=None
    return obj, store, clock


def synthetic_grant(target):
    return {
        "schema": "QD_CODE_SELECTION_AUTHORIZATION_V1",
        "domain": "WINDOWS_LOCAL",
        "action": "SELECT",
        "operation": "c" * 32,
        "expected_head": None,
        "target": target,
        "restores": None,
    }


@pytest.mark.parametrize("old_profile", [
    "WINDOWS_TIME_CODE_SELECTION_V1",
    "INDEPENDENT_TWO_PEER_NTP_CODE_SELECTION_V1",
])
def test_r14_cannot_use_windows_clock_or_old_v7_ntp_profile(
        verified_r14_evidence, old_profile):
    spec, _, _ = verified_r14_evidence
    selector, store, clock = synthetic_native_selector(old_profile)
    with pytest.raises(ValueError, match="R14_INDEPENDENT_TWO_PEER_NTP_PROFILE_REQUIRED"):
        selector.change(synthetic_grant(spec), approved=True)
    assert store.published == [] and clock.calls == []


@pytest.mark.parametrize("mutation", [
    "wrong_digest", "wrong_receipt", "old_release", "rollback",
])
def test_r14_new_ntp_profile_only_accepts_exact_unselected_release_reference(
        verified_r14_evidence, mutation):
    spec, _, _ = verified_r14_evidence
    selector, store, clock = synthetic_native_selector(selection.R14_NTP_SELECTION_PROFILE)
    g = synthetic_grant(spec)
    if mutation == "wrong_digest":
        g["target"] = {**spec, "artifact_digest":"0"*64}
    elif mutation == "wrong_receipt":
        g["target"] = {**spec, "receipt_sha256":"0"*64}
    elif mutation == "old_release":
        g["target"] = {**spec, "release":"a"*40}
    else:
        g["action"] = "ROLLBACK"
    with pytest.raises(ValueError, match="EXACT_R14_INDEPENDENT_NTP_SELECTION_REQUIRED"):
        selector.change(g, approved=True)
    assert store.published == [] and clock.calls == []


def test_r14_new_ntp_profile_requires_explicit_separate_selection_approval(
        verified_r14_evidence):
    spec, _, _ = verified_r14_evidence
    selector, store, clock = synthetic_native_selector(selection.R14_NTP_SELECTION_PROFILE)
    with pytest.raises(ValueError, match="EXPLICIT_CODE_SELECTION_AUTHORIZATION_REQUIRED"):
        selector.change(synthetic_grant(spec))
    assert store.published == [] and clock.calls == []


def test_synthetic_r14_only_profile_still_requires_bound_clock_and_native_verifier(
        verified_r14_evidence):
    spec, _, _ = verified_r14_evidence
    selector, store, clock = synthetic_native_selector(selection.R14_NTP_SELECTION_PROFILE)
    result = selector.change(synthetic_grant(spec), approved=True)
    assert result["receipt"]["selected"] == spec
    assert len(store.published) == 1  # Test-only in-memory store, NO native writes.
    assert clock.calls == ["qd-code-selection-" + "c"*32]
