"""R14 selection proposal: read-only real 12-head and synthetic refusals.

No native release selection, 263MB file scan, external NTP, or service startup.
"""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import atlas_r14_selection_proposal as proposal
from scripts.release_selection import digest, encoded, strict


@pytest.fixture(scope="module")
def native_r12_records():
    """The twelve tiny already-published native selection envelope JSON files."""
    result = []
    for revision in range(1, 13):
        path = proposal.SEL / f"r{revision:04}.json"
        assert path.stat().st_size < 65536
        envelope = strict(path.read_bytes())
        assert set(envelope) == {"record", "native_id"}
        result.append(envelope["record"])
    assert proposal.chain(result)
    return result


def test_native_r12_chain_exact_previous_head_and_no_r13_record(native_r12_records):
    used = proposal.chain(native_r12_records)
    assert len(used) == 12
    assert digest(native_r12_records[-1]) == proposal.R12_HEAD
    assert native_r12_records[-1]["selected"]["release"] == proposal.R12_RELEASE
    assert hashlib.sha256((proposal.SEL/"r0012.json").read_bytes()).hexdigest() == proposal.R12_ENVELOPE_SHA256
    selected=proposal.SEL/"r0013.json"
    pending=proposal.SEL/"r0013.pending"
    assert selected.exists()==pending.exists()
    if selected.exists():
        assert hashlib.sha256(selected.read_bytes()).hexdigest()=="6b1e04b8f733d46421c81a5d158dbafbecf052e6f3a8e8289d175caca96d4e31"
        assert selected.read_bytes()==pending.read_bytes()


@pytest.mark.parametrize("mutation", [
    "short", "long", "wrong_previous", "wrong_release",
    "wrong_receipt", "duplicate_operation", "wrong_revision", "wrong_domain",
    "illegal_rollback", "invalid_source_ref",
])
def test_historical_selector_chain_tampering_refuses(native_r12_records, mutation):
    rows = copy.deepcopy(native_r12_records)
    if mutation == "short": rows.pop()
    elif mutation == "long": rows.append(copy.deepcopy(rows[-1]))
    elif mutation == "wrong_previous": rows[-1]["previous"] = "0"*64
    elif mutation == "wrong_release": rows[-1]["selected"]["release"] = "a"*40
    elif mutation == "wrong_receipt": rows[-1]["selected"]["receipt_sha256"] = "0"*64
    elif mutation == "duplicate_operation": rows[-1]["operation"] = rows[0]["operation"]
    elif mutation == "wrong_revision": rows[-1]["revision"] = 99
    elif mutation == "wrong_domain": rows[-1]["domain"] = "DISPOSABLE"
    elif mutation == "illegal_rollback": rows[-1]["action"] = "ROLLBACK"
    elif mutation == "invalid_source_ref": rows[-1]["selected"]["root"] = "D:/fake"
    with pytest.raises((ValueError, KeyError)):
        proposal.chain(rows)


def test_r14_exact_native_receipt_reference_no_installed_child_readback():
    spec = proposal.exact_r14_reference()
    assert spec["release"] == proposal.R14_CODE_RELEASE
    assert spec["receipt_sha256"] == proposal.R14_RECEIPT_SHA256
    assert spec["artifact_digest"] == proposal.R14_ARTIFACT_DIGEST
    assert spec["root"] == str(proposal.R14_DEST)


def test_real_readonly_selection_proposal_is_pinned_and_nonfinancial():
    if (proposal.SEL/"r0013.json").exists():
        # Once R14 is selected, the original unapproved proposal is
        # deliberately stale: it cannot be re-admitted or reused.
        with pytest.raises(ValueError,match="R14_SELECTION_APPROVAL_FILE_PRESENT_REVIEW_REFUSED"):
            proposal.read_only_proposal()
        return
    before_r12 = hashlib.sha256((proposal.SEL/"r0012.json").read_bytes()).hexdigest()
    before_r14 = hashlib.sha256(proposal.R14_RECEIPT.read_bytes()).hexdigest()
    result = proposal.read_only_proposal()
    assert result["schema"] == "ATLAS_R14_NONFINANCIAL_CODE_SELECTION_PROPOSAL_V1"
    assert result["status"] == "READ_ONLY_PROPOSAL_NOT_OPERATOR_PERMISSION"
    assert result["previous_release"] == proposal.R12_RELEASE
    assert result["previous_head"] == proposal.R12_HEAD
    assert result["predecessor_records_verified"] == 12
    assert result["row"]["revision"] == 13
    assert result["row"]["action"] == "SELECT"
    assert result["row"]["previous"] == proposal.R12_HEAD
    assert result["row"]["selected"]["release"] == proposal.R14_CODE_RELEASE
    assert result["proposed_head"] == digest(result["row"])
    assert result["clock_profile"] == proposal.R14_NTP_SELECTION_PROFILE
    assert result["native_selection_root_identity"] == proposal.NATIVE_ID
    assert result["fresh_180s_independent_two_peer_clock_required"] is True
    assert result["native_installed_child_readback_required_before_publication"] is True
    for key in ("clock_qualification_performed","native_installed_child_readback_performed",
                "r14_selected","operator_approval_present","selection_authorized",
                "selection_mutation_performed","financial_authority","paper_accounts",
                "providers","paper_start","simulated_orders","live_orders",
                "automatic_startup"):
        assert result[key] is False
    assert before_r12 == hashlib.sha256((proposal.SEL/"r0012.json").read_bytes()).hexdigest()
    assert before_r14 == hashlib.sha256(proposal.R14_RECEIPT.read_bytes()).hexdigest()
    assert not (proposal.SEL/"r0013.json").exists()
    assert not (proposal.SEL/"r0013.pending").exists()


def test_stale_selector_source_pin_refuses_before_native_lock(monkeypatch,tmp_path):
    # Isolate the old planning state from consumed one-shot consent.
    monkeypatch.setattr(proposal, "APPROVAL", tmp_path/"no-consent-file.json")
    monkeypatch.setattr(proposal, "SELECTOR_SHA256", "0"*64)
    with pytest.raises(ValueError,match="R14_SELECTION_PINNED_BYTES_CHANGED"):
        proposal.read_only_proposal()


def test_review_refuses_unrequested_approval_file_before_native_read(monkeypatch,tmp_path):
    fake = tmp_path/"bogus-selection-consent.json"
    fake.write_text("{}")
    monkeypatch.setattr(proposal, "APPROVAL", fake)
    with pytest.raises(ValueError, match="R14_SELECTION_APPROVAL_FILE_PRESENT_REVIEW_REFUSED"):
        proposal.read_only_proposal()


def test_r14_installed_receipt_hash_change_refuses(monkeypatch):
    monkeypatch.setattr(proposal, "R14_RECEIPT_SHA256", "0"*64)
    with pytest.raises(ValueError,match="R14_SELECTION_PINNED_BYTES_CHANGED"):
        proposal.exact_r14_reference()


def test_create_only_review_writes_docs_only_and_refuses_second_write(monkeypatch,tmp_path):
    if (proposal.SEL/"r0013.json").exists():
        # Once selected, no new preselection review may be minted.
        output=tmp_path/"r14-proposal.json"
        monkeypatch.setattr(proposal,"REVIEW",output)
        with pytest.raises(ValueError,match="R14_SELECTION_APPROVAL_FILE_PRESENT_REVIEW_REFUSED"):
            proposal.main(["--write-review-once"])
        assert not output.exists()
        return
    output=tmp_path/"r14-proposal.json"
    monkeypatch.setattr(proposal,"REVIEW",output)
    before = set(proposal.SEL.iterdir())
    result=proposal.main(["--write-review-once"])
    assert result["review_recorded"] is True
    exact=strict(output.read_bytes())
    assert encoded(exact)==output.read_bytes()
    assert exact["proposed_head"]==result["proposed_head"]
    assert exact["selection_mutation_performed"] is False
    with pytest.raises(ValueError,match="R14_SELECTION_CREATE_ONLY_REVIEW_ALREADY_USED"):
        proposal.main(["--write-review-once"])
    assert set(proposal.SEL.iterdir()) == before
    assert not (proposal.SEL/"r0013.json").exists()


def test_inspect_cannot_perform_selection_even_with_inert_flag(monkeypatch,tmp_path):
    if (proposal.SEL/"r0013.json").exists():
        with pytest.raises(ValueError,match="R14_SELECTION_APPROVAL_FILE_PRESENT_REVIEW_REFUSED"):
            proposal.main(["--inspect"])
        with pytest.raises(SystemExit):
            proposal.main(["--execute-one-shot-selection"])
        return
    monkeypatch.setattr(proposal,"REVIEW",tmp_path/"absent.json")
    result=proposal.main(["--inspect"])
    assert result["review_recorded"] is False
    assert result["selection_authorized"] is False
    assert result["selection_mutation_performed"] is False
    with pytest.raises(SystemExit):
        proposal.main(["--execute-one-shot-selection"])
