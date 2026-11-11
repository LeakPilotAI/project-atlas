"""R16 nonfinancial native code selection publisher fail-closed tests.

Prepublication tests are synthetic or READ ONLY. This test suite neither
creates an approval nor publishes a native selector record. A genuine
selected R16 must be independently verified in a separate postacceptance.
"""
import hashlib
from pathlib import Path

import pytest

from scripts import atlas_r16_code_only_selection_publisher as pub
from scripts import atlas_r16_selection_handoff as handoff
from scripts import release_selection

SID = "S-1-5-21-1-2-3-1001"


def fake_proposal():
    row = {
        "schema": "QD_RELEASE_SELECTION_RECEIPT_V1",
        "domain": "WINDOWS_LOCAL",
        "revision": 15,
        "action": "SELECT",
        "operation": "a" * 32,
        "previous": pub.PREDECESSOR_HEAD,
        "selected": {
            "schema": "QD_INSTALLED_RELEASE_REFERENCE_V1",
            "domain": "WINDOWS_LOCAL",
            "release": handoff.SOURCE_COMMIT,
            "root": str(handoff.TARGET),
            "receipt": str(handoff.RECEIPT),
            "receipt_sha256": "b" * 64,
            "artifact_digest": "c" * 64,
        },
        "restores": None,
    }
    return {
        "schema": "ATLAS_R16_CODE_SELECTION_HANDOFF_V1",
        "status": "NATIVE_INSTALL_RECEIPT_ELIGIBLE_FOR_SEPARATE_HANDLE_AND_OPERATOR_APPROVAL",
        "proposed_row": row,
        "proposed_row_digest": release_selection.digest(row),
    }


def decision(proposal):
    row = proposal["proposed_row"]
    return {
        "schema": "ATLAS_R16_NATIVE_CODE_SELECTION_APPROVAL_V1",
        "decision": pub.OPERATION,
        "scope": pub.SCOPE,
        "operator_sid": SID,
        "source_commit": handoff.SOURCE_COMMIT,
        "predecessor_r15_head": pub.PREDECESSOR_HEAD,
        "predecessor_r15_record_sha256": pub.PREDECESSOR_SHA,
        "native_selection_revision": 15,
        "proposed_head": proposal["proposed_row_digest"],
        "installed_receipt_sha256": row["selected"]["receipt_sha256"],
        "operation": row["operation"],
        "publisher_source_sha256": pub.approval_source_sha256(),
        "one_shot": True,
        "selection_allowed": True,
        "financial_authority": False,
        "paper_accounts": False,
        "provider_access": False,
        "paper_start_authorized": False,
        "live_orders_authorized": False,
    }


def test_real_r16_selected_native_code_and_one_shot_publisher_is_spent():
    from scripts.observation_runtime.atlas_r16_selected_code_readback import (
        selected_code,
    )
    actual = selected_code()
    assert actual["selected_revision"] == 15
    assert actual["selected_native_head"] == (
        "1244c614ccc9e89e436d90df77cebb6e44a57edcb44972660940ed29ebfcd593")
    assert actual["financial_writer_operational_accepted"] is False
    assert actual["paper_start_authorized"] is False
    assert actual["live_trading_authorized"] is False
    assert pub.APPROVAL_SHA256 is None
    assert pub.APPROVAL.exists()
    with pytest.raises(ValueError, match="R16_SELECTION_ALREADY_ATTEMPTED_DO_NOT_RETRY"):
        pub.main(["--inspect"])


def test_pure_sid_bound_operator_decision_for_one_exact_code_selection():
    proposal = fake_proposal()
    assert pub.validate_operator_decision(decision(proposal),
                                          sid=SID, proposal=proposal) == decision(proposal)


@pytest.mark.parametrize("field,value", [
    ("one_shot", False), ("selection_allowed", False),
    ("financial_authority", True), ("paper_accounts", True),
    ("provider_access", True), ("paper_start_authorized", True),
    ("live_orders_authorized", True), ("source_commit", "f"*40),
    ("predecessor_r15_head", "f"*64),
    ("predecessor_r15_record_sha256", "e"*64),
    ("native_selection_revision", 14), ("proposed_head", "f"*64),
    ("installed_receipt_sha256", "0"*64),
    ("publisher_source_sha256", "0"*64), ("operation", "a"*31),
])
def test_unauthorized_scope_or_identifier_drifts_refuse(field, value):
    p = fake_proposal()
    a = decision(p)
    a[field] = value
    with pytest.raises(ValueError, match="R16_SELECTION_EXACT_SID_BOUND_ONE_SHOT_DECISION_REQUIRED"):
        pub.validate_operator_decision(a, sid=SID, proposal=p)


def test_extra_hidden_authority_and_foreign_sid_refuse():
    p = fake_proposal()
    a = decision(p)
    a["allow_live_money"] = True
    with pytest.raises(ValueError, match="EXACT_SID_BOUND"):
        pub.validate_operator_decision(a, sid=SID, proposal=p)
    a.pop("allow_live_money")
    with pytest.raises(ValueError, match="EXACT_SID_BOUND"):
        pub.validate_operator_decision(a, sid="S-1-5-21-999-888-777-1001", proposal=p)


def test_forged_proposal_evidence_never_grants_selection():
    p = fake_proposal()
    approved = decision(p)
    for override in ({"status": "GO"},
                     {"proposed_row_digest": "0"*64},
                     {"proposed_row": {**p["proposed_row"], "revision": 14}}):
        with pytest.raises(ValueError, match="EXACT_SID_BOUND"):
            pub.validate_operator_decision(approved, sid=SID, proposal={**p, **override})


def test_unpinned_code_selection_requires_new_operator_consent_before_clock_or_native_writer(monkeypatch):
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    monkeypatch.setattr(ntp, "IndependentNtpClock",
                        lambda **kwargs: pytest.fail("UNAPPROVED_NTP_MUST_NOT_START"))
    with pytest.raises(ValueError, match="R16_SELECTION_ONE_SHOT_OPERATOR_APPROVAL_NOT_PINNED"):
        pub.require_operator_approval(fake_proposal())
    with pytest.raises(ValueError, match="R16_SELECTION_ALREADY_ATTEMPTED_DO_NOT_RETRY"):
        pub.main(["--execute-one-shot-code-selection",
                  "--confirm-scope", pub.SCOPE])
    with pytest.raises(ValueError, match="R16_SELECTION_EXACT_NONFINANCIAL_CODE_SCOPE_REQUIRED"):
        pub.main(["--execute-one-shot-code-selection", "--confirm-scope", "LIVE_MONEY"])
    assert (handoff.SELECTION_ROOT / "r0015.pending").is_file()
    assert (handoff.SELECTION_ROOT / "r0015.json").is_file()


def test_no_reentrant_native_selection_lock(monkeypatch):
    import inspect
    source = inspect.getsource(pub.publish)
    assert source.count("proposal = handoff.inspect()") == 1
    locked = source.split("with store.locked():",1)[1]
    assert "handoff.inspect()" not in "\n".join(
        line for line in locked.splitlines() if not line.lstrip().startswith("#"))
    assert "refreshed = handoff.candidate_from_receipt" in locked
    assert "store.publish(row)" in locked


def test_source_digest_changes_only_with_one_pin_value(monkeypatch, tmp_path):
    baseline = pub.approval_source_sha256()
    raw = Path(pub.__file__).read_bytes()
    marker = b"APPROVAL_SHA256 = None  # R16 separate one-shot operator approval, never install authorization."
    pinned = (b'APPROVAL_SHA256 = "' + b"f"*64 +
              b'"  # R16 separate one-shot operator approval, never install authorization.')
    assert sum(ln==marker for ln in raw.splitlines())==1
    altered = tmp_path / "r16_selection_publisher_test.py"
    altered.write_bytes(raw.replace(b"\n"+marker+b"\n", b"\n"+pinned+b"\n",1))
    monkeypatch.setattr(pub,"__file__",str(altered))
    assert pub.approval_source_sha256() == baseline
    altered.write_bytes(altered.read_bytes()+b"\n# FOREIGN_SOURCE_CHANGE\n")
    assert pub.approval_source_sha256() != baseline


def test_no_serialized_clock_proof_can_be_substituted_for_held_clock(monkeypatch):
    p = fake_proposal()
    monkeypatch.setattr(pub, "require_operator_approval", lambda _: decision(p))
    monkeypatch.setattr(handoff, "inspect", lambda: p)
    with pytest.raises(ValueError, match="CURRENT_PROCESS_180S_CLOCK_PROOF_REQUIRED"):
        pub.publish(clock=object(), proof={"elapsed_seconds":180,"samples":37})
    assert (handoff.SELECTION_ROOT/"r0015.pending").is_file()
