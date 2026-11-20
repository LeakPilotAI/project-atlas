"""Selected native R15 code-only postacceptance; no finance/provider access."""
from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

from scripts.release_selection_store import NativeSelectionStore
from scripts.release_selection import digest
from scripts import atlas_r15_code_only_selection_publisher as publisher
from scripts import atlas_r15_selection_handoff as handoff
from app.personal_paper import DEFAULT_HYPERLIQUID_BUDGET


R14_SHA = "6b1e04b8f733d46421c81a5d158dbafbecf052e6f3a8e8289d175caca96d4e31"
R14_HEAD = "3fd8e1972b559a5de90627a303fc663b11928f8b43e84621a6796e9f3dbe9383"
R15_SHA = "b729ff718fc41d90942400db15fc17e1bcf0cac6ae9ccf18e0492e9c6c4f2eb2"
R15_HEAD = "274f5b00ee0e2f6271c6dd1dc5316f7d9124e932483038a6d93ef62ddbd2cd25"
RECEIPT_SHA = "b313a20f0a747c4a2ac81a2c1ae11b50901786008ce75f84202bf2f2435e741c"
APPROVAL_SHA = "cac8da532607edf0760de1bacd3b10191653bbf26352c82c43543fe1f52233d6"


@pytest.fixture(scope="module")
def selected():
    root = handoff.SELECTION_ROOT
    if not (root / "r0014.json").is_file():
        pytest.skip("Native R15 code-only selection not installed on this test host")
    store = NativeSelectionStore(
        root=str(root),native_root=[4004218753,65536,1532785])
    try:
        with store.locked():
            rows = store.records()
            return rows
    finally:
        store.close()


def test_14_record_native_selection_preserves_r14_parent(selected):
    assert len(selected)==14
    assert digest(selected[12])==R14_HEAD
    assert selected[13]["previous"]==R14_HEAD
    assert digest(selected[13])==R15_HEAD
    assert selected[13]["revision"]==14
    assert selected[13]["action"]=="SELECT"
    assert selected[13]["restores"] is None


def test_exact_installed_r15_unselected_receipt_now_selected_code_only(selected):
    spec=selected[-1]["selected"]
    assert spec["release"]==handoff.SOURCE_COMMIT
    assert spec["root"]==str(handoff.TARGET)
    assert spec["receipt_sha256"]==RECEIPT_SHA
    assert hashlib.sha256(handoff.RECEIPT.read_bytes()).hexdigest()==RECEIPT_SHA
    receipt=json.loads(handoff.RECEIPT.read_bytes())
    assert len(receipt["files"])==10526
    assert len(receipt["directories"])==912
    assert all(receipt[key] is False for key in (
        "selected","financial_effects","provider_connections",
        "operational_acceptance"))


def test_native_selection_file_bytes_and_prior_record_unchanged(selected):
    root=handoff.SELECTION_ROOT
    assert hashlib.sha256((root/"r0013.json").read_bytes()).hexdigest()==R14_SHA
    assert hashlib.sha256((root/"r0014.json").read_bytes()).hexdigest()==R15_SHA
    # The native selection store retains a same-record .pending hard link;
    # that is intentional after successful publication, not an incomplete op.
    assert (root/"r0014.pending").is_file()


def test_one_shot_selection_pin_retired_even_with_retained_audit_record(selected):
    assert publisher.APPROVAL_SHA256 is None
    assert publisher.APPROVAL.is_file()
    assert hashlib.sha256(publisher.APPROVAL.read_bytes()).hexdigest()==APPROVAL_SHA
    record=json.loads(publisher.APPROVAL.read_bytes())
    assert record["one_shot"] is True
    assert record["selection_allowed"] is True
    assert all(record[k] is False for k in (
        "financial_authority","paper_accounts","provider_access",
        "paper_start_authorized","live_orders_authorized"))
    with pytest.raises(ValueError,match="APPROVAL_NOT_PINNED"):
        publisher.require_operator_approval({"proposed_row":{}})


def test_current_selection_must_not_be_replayed_or_republished(selected):
    with pytest.raises(ValueError,match="SELECTION_ALREADY_ATTEMPTED_DO_NOT_RETRY"):
        handoff.inspect()


def test_public_budget_untouched_and_financial_go_is_not_inferred(selected):
    with sqlite3.connect(
        DEFAULT_HYPERLIQUID_BUDGET.resolve().as_uri()+"?mode=ro",
        uri=True,timeout=1,
    ) as db:
        assert db.execute(
            "SELECT max_attempts,attempted FROM budget WHERE id=1"
        ).fetchone()==(12,10)
    assert publisher.APPROVAL_SHA256 is None
