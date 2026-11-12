"""R17 code-only future native selection publisher: no live selector writes.

Every positive decision is a synthetic pure approval validation; real execution
is impossible until exact R17 code is installed AND separate Windows operator
approval is provided/pinned. No provider, account, trading, or UTC is acquired.
"""
from __future__ import annotations

import copy

import pytest

from scripts import atlas_r17_code_only_selection_publisher as publisher
from scripts import atlas_r17_selection_handoff as handoff
from scripts import release_selection

SID = "S-1-5-21-100-200-300-400"


def synthetic_proposal():
    row = {
        "schema": "QD_RELEASE_SELECTION_RECEIPT_V1",
        "domain": "WINDOWS_LOCAL",
        "revision": 16,
        "action": "SELECT",
        "operation": "f"*32,
        "previous": handoff.R16_HEAD,
        "selected": {
            "schema": "QD_INSTALLED_RELEASE_REFERENCE_V1",
            "domain": "WINDOWS_LOCAL",
            "release": handoff.SOURCE,
            "root": str(handoff.TARGET),
            "receipt": str(handoff.RECEIPT),
            "receipt_sha256": "c"*64,
            "artifact_digest": "d"*64,
        },
        "restores": None,
    }
    return {
        "schema": handoff.SCHEMA,
        "status": "INSTALLED_RECEIPT_PROPOSED_NOT_NATIVE_HANDLE_ACCEPTED",
        "proposed_selection_record": row,
        "proposed_record_sha256": release_selection.digest(row),
    }


def specimen(proposal):
    return {
        "schema": "ATLAS_R17_CODE_ONLY_NATIVE_SELECTION_APPROVAL_V1",
        "operation": publisher.OPERATION,
        "scope": publisher.SCOPE,
        "operator_sid": SID,
        "source_commit": handoff.SOURCE,
        "installed_receipt_sha256":
            proposal["proposed_selection_record"]["selected"]["receipt_sha256"],
        "native_selection_revision": 16,
        "previous_r16_head": handoff.R16_HEAD,
        "previous_r16_record_sha256": handoff.R16_RECORD_SHA,
        "proposed_row_sha256": proposal["proposed_record_sha256"],
        "publisher_source_sha256": publisher.approval_source_digest(),
        "one_shot": True,
        "selection_allowed": True,
        "financial_authority": False,
        "provider_access": False,
        "paper_accounts": False,
        "paper_start_authorized": False,
        "live_orders_authorized": False,
    }


def test_exact_synthetic_selection_decision_never_grants_finance():
    proposal = synthetic_proposal()
    record = specimen(proposal)
    assert publisher.validate_operator_decision(
        record, sid=SID, proposal=proposal,
        publisher_source_sha256=publisher.approval_source_digest()) is record
    assert record["selection_allowed"]
    assert not record["financial_authority"]
    assert not record["provider_access"]
    assert not record["paper_accounts"]
    assert not record["paper_start_authorized"]
    assert not record["live_orders_authorized"]


@pytest.mark.parametrize("damage", [
    "schema", "operation", "scope", "operator_sid", "source_commit",
    "installed_receipt_sha256", "native_selection_revision",
    "previous_r16_head", "previous_r16_record_sha256",
    "proposed_row_sha256", "publisher_source_sha256", "one_shot",
    "selection_allowed", "financial_authority", "provider_access",
    "paper_accounts", "paper_start_authorized", "live_orders_authorized",
    "extra_grant", "missing_grant",
])
def test_no_foreign_or_broadened_native_selection_operator_decision(damage):
    proposal = synthetic_proposal()
    row = copy.deepcopy(specimen(proposal))
    if damage == "extra_grant":
        row["financial_writer_lease"] = True
    elif damage == "missing_grant":
        row.pop("live_orders_authorized")
    elif damage in ("one_shot", "selection_allowed"):
        row[damage] = False
    elif damage in (
        "financial_authority", "provider_access", "paper_accounts",
        "paper_start_authorized", "live_orders_authorized",
    ):
        row[damage] = True
    else:
        row[damage] = "UNREVIEWED"
    with pytest.raises(ValueError, match="R17_SELECTION_SID_BOUND"):
        publisher.validate_operator_decision(
            row, sid=SID, proposal=proposal,
            publisher_source_sha256=publisher.approval_source_digest())


@pytest.mark.parametrize("damage", [
    "wrong_receipt", "wrong_head", "wrong_revision", "wrong_action",
    "wrong_source_record_digest", "wrong_proposal_status",
    "missing_proposal_row", "nondict_proposal_row",
])
def test_unreviewed_native_row_or_partial_install_proposal_refused(damage):
    proposal = synthetic_proposal()
    decision = specimen(proposal)
    if damage == "wrong_receipt":
        proposal["proposed_selection_record"]["selected"]["receipt_sha256"] = "e"*64
    elif damage == "wrong_head":
        proposal["proposed_selection_record"]["previous"] = "e"*64
    elif damage == "wrong_revision":
        proposal["proposed_selection_record"]["revision"] = 15
    elif damage == "wrong_action":
        proposal["proposed_selection_record"]["action"] = "RESTORE"
    elif damage == "wrong_source_record_digest":
        proposal["proposed_record_sha256"] = "e"*64
    elif damage == "wrong_proposal_status":
        proposal["status"] = "WAITING_FOR_NATIVE_INSTALL"
    elif damage == "missing_proposal_row":
        proposal.pop("proposed_selection_record")
    elif damage == "nondict_proposal_row":
        proposal["proposed_selection_record"] = None
    with pytest.raises(ValueError, match="R17_SELECTION_"):
        publisher.validate_operator_decision(
            decision, sid=SID, proposal=proposal,
            publisher_source_sha256=publisher.approval_source_digest())


def test_different_windows_operator_sid_not_reusable():
    proposal = synthetic_proposal()
    with pytest.raises(ValueError, match="R17_SELECTION_SID_BOUND"):
        publisher.validate_operator_decision(
            specimen(proposal), sid="S-1-5-21-999-999-999-999",
            proposal=proposal,
            publisher_source_sha256=publisher.approval_source_digest())


def test_publisher_source_changed_refuses_existing_record():
    proposal = synthetic_proposal()
    with pytest.raises(ValueError, match="R17_SELECTION_SID_BOUND"):
        publisher.validate_operator_decision(
            specimen(proposal), sid=SID, proposal=proposal,
            publisher_source_sha256="f"*64)


def test_genuine_r16_native_waits_for_r17_install_without_mutating_selector():
    report = publisher.inspect()
    assert report["status"] == "WAITING_FOR_SEPARATELY_APPROVED_R17_NATIVE_CODE_INSTALL"
    assert report["proposed_revision"] == 16
    assert report["selected_predecessor"] == "R16"
    assert not report["new_selection_record_published"]
    assert not report["exact_operator_selection_approval_pinned"]
    assert not report["paper_start_authorized"]
    assert not (handoff.SELECTION_ROOT/"r0016.json").exists()


def test_unpinned_selection_approval_prevents_network_or_native_mutation(
        monkeypatch):
    assert publisher.APPROVAL_SHA256 is None
    monkeypatch.setattr(publisher, "qualify_clock",
                        lambda *_a: pytest.fail("NETWORK_NTP_NOT_ALLOWED"))
    monkeypatch.setattr(publisher, "NativeSelectionStore",
                        lambda **_kw: pytest.fail("NATIVE_SELECTOR_NOT_OPENED"))
    with pytest.raises(ValueError, match="R17_SELECTION_NEW_PINNED"):
        publisher.execute()
    with pytest.raises(ValueError, match="R17_SELECTION_NEW_PINNED"):
        publisher.main([
            "--execute-one-shot-code-selection",
            "--confirm-scope", publisher.SCOPE,
        ])


def test_malformed_scope_does_not_even_read_approval(monkeypatch):
    monkeypatch.setattr(publisher, "require_operator_approval",
                        lambda *_: pytest.fail("WRONG_SCOPE_READ_APPROVAL"))
    with pytest.raises(ValueError, match="EXACT_ONE_SHOT_SCOPE"):
        publisher.main([
            "--execute-one-shot-code-selection",
            "--confirm-scope", "SELECT_AND_START_PAPER",
        ])


def test_selection_does_not_inherit_r16_operator_approval():
    from scripts.atlas_r16_code_only_selection_publisher import (
        APPROVAL as OLD_SELECTION_APPROVAL,
    )
    assert publisher.APPROVAL != OLD_SELECTION_APPROVAL
    assert publisher.OPERATION != "APPROVE_ONE_R16_NATIVE_CODE_SELECTION"
    assert len(publisher.approval_source_digest()) == 64
