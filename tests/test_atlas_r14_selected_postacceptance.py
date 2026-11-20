"""R14 selected-code postacceptance tests; no mutable native operations."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts import atlas_r14_selection_publisher as pub
from scripts import atlas_r14_selection_proposal as proposal
from scripts import release_selection as selection
from scripts.release_selection_store import NativeSelectionStore

R12_SHA = "f685ff5c5d55ab87c4ee47b651afb823faa8d3696da4db120624bfac67c7c0c7"
R13_SHA = "6b1e04b8f733d46421c81a5d158dbafbecf052e6f3a8e8289d175caca96d4e31"
R14_RECEIPT_SHA = "4cbf4f78c4da879f0e7d35f7ab1c3e119b4e0e7fc04640f0984ad4c8ce912ba7"
LEASE = proposal.ROOT / "logs/diagnostics/atlas-r14-native-selection-single-attempt-20261110.lock"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_selected_release_is_exact_r14_with_original_12_record_ancestry():
    store=NativeSelectionStore(root=str(proposal.SEL),native_root=list(proposal.NATIVE_ID))
    try:
        with store.locked():
            rows=store.records()
            assert len(rows)==13
            assert len(proposal.chain(rows[:12]))==12
            assert selection.digest(rows[-2])==proposal.R12_HEAD
            assert rows[-1]==pub.pinned_review()["row"]
            assert rows[-1]["revision"]==13
            assert rows[-1]["action"]=="SELECT"
            assert rows[-1]["previous"]==proposal.R12_HEAD
            assert rows[-1]["selected"]["release"]==selection.R14_CODE_RELEASE
            assert selection.digest(rows[-1])==pub.EXPECTED_HEAD
    finally:
        store.close()


def test_native_hardlinked_selection_pair_is_identical_and_legacy_unmodified():
    assert sha(proposal.SEL/"r0012.json")==R12_SHA
    assert sha(proposal.SEL/"r0013.json")==R13_SHA
    assert sha(proposal.SEL/"r0013.pending")==R13_SHA
    assert sha(proposal.R14_RECEIPT)==R14_RECEIPT_SHA


def test_single_run_lease_preserved_no_reuse_and_nonfinancial():
    assert LEASE.is_file()
    lease=json.loads(LEASE.read_bytes())
    assert lease["schema"]=="ATLAS_R14_CODE_ONLY_NATIVE_SELECTION_ONE_SHOT_LEASE_V1"
    assert lease["operation"]==pub.OPERATION
    assert lease["proposed_head"]==pub.EXPECTED_HEAD
    for key in ("financial_authority","providers","paper_orders",
                "live_orders","automatic_startup"):
        assert lease[key] is False


def test_operator_one_time_selection_approval_really_revoked():
    assert pub.APPROVAL_PIN is None
    assert pub.APPROVAL.is_file()  # ignored historical consent, not active
    with pytest.raises(ValueError,match="R14_PUBLISHER_FRESH_ONE_SHOT_OPERATOR_APPROVAL_NOT_PINNED"):
        pub.require_approved_operator()


def test_repeated_selection_execution_refuses_before_clock_or_store(monkeypatch):
    from scripts import release_selection_store
    monkeypatch.setattr(release_selection_store,"NativeSelectionStore",
                        lambda **_:pytest.fail("NEW_NATIVE_SELECTION_OPEN_REFUSED"))
    with pytest.raises(ValueError,match="R14_PUBLISHER_FRESH_ONE_SHOT_OPERATOR_APPROVAL_NOT_PINNED"):
        pub.main(["--execute-one-shot-code-selection",
                  "--confirm-scope",pub.SCOPE])


def test_preselection_proposal_now_refuses_expected_occupied_revision():
    with pytest.raises(ValueError,match="R14_SELECTION_APPROVAL_FILE_PRESENT_REVIEW_REFUSED"):
        proposal.read_only_proposal()
    assert (proposal.SEL/"r0013.json").exists()
    assert (proposal.SEL/"r0013.pending").exists()
