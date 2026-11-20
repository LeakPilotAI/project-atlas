"""R23 source-side next native SELECT, never a financial or local authorization."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import atlas_r23_code_only_install as inst
from scripts import atlas_r23_code_only_select as select


def test_exact_separate_native_21st_selection_scope_and_hash():
    assert select.RECORD_REVISION == 21
    assert select.ACTION == b"ATLAS_R23_NATIVE_CODE_ONLY_REV21_SELECTION_V1"
    assert select.SCOPE == "APPROVE_ONE_R23_CODE_ONLY_NATIVE_SELECTION_NO_FINANCIAL_START"
    assert select.APPROVAL_PIN is None
    assert select.APPROVAL != inst.APPROVAL
    assert select.SELECTION_ROOT == Path("D:/AtlasRuntime/selection")
    assert select.source_hash() == hashlib.sha256(Path(select.__file__).read_bytes()).hexdigest()


def test_no_install_no_selection_candidate(monkeypatch, tmp_path):
    monkeypatch.setattr(select.install, "original_selected_r21", lambda: {
        "release": inst.R21_SOURCE,
    })
    monkeypatch.setattr(select.install, "original_accounts", lambda: True)
    monkeypatch.setattr(select, "SELECTION_ROOT", tmp_path)
    monkeypatch.setattr(select.install, "TARGET", tmp_path / "not-installed")
    with pytest.raises(ValueError, match="ORIGINAL_NATIVE_INSTALL_AND_ACK_REQUIRED"):
        select.candidate()


def test_requires_separate_selection_approval_before_nativeselect(monkeypatch):
    with pytest.raises(ValueError, match="DISTINCT_NATIVE_SELECTION_OPERATOR_APPROVAL"):
        select.approval_digest({})
    with pytest.raises(ValueError, match="SELECTION_OPERATOR_APPROVAL_REQUIRED"):
        select.select(clock=object(), approved=False)
    monkeypatch.setattr(
        select, "candidate",
        lambda: pytest.fail("No installed target inspection for wrong scope"),
    )
    with pytest.raises(ValueError, match="EXACT_OPERATOR_SCOPE_REQUIRED"):
        select.main(["--execute-approved-code-only", "--confirm-scope", "APPROVE_ALL"])


def test_fake_two_peer_clock_never_accepted():
    with pytest.raises(ValueError, match="ORIGINAL_TWO_PEER_CLOCK_REQUIRED"):
        select.clock_required(SimpleNamespace(evidence={
            "domain": "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS",
            "bound_ms": 1,
            "financial_authority": False,
        }))


@pytest.mark.parametrize("fault", ("good", "wrong_root", "bad_ledger", "bad_ack"))
def test_candidate_native_receipt_and_two_stage_journal_bindings(
    monkeypatch, tmp_path, fault,
):
    base = tmp_path / "native"
    base.mkdir()
    receipt_path = tmp_path / "receipt.json"
    journal_path = tmp_path / "receipt.pending.jsonl"
    receipt_path.touch()
    journal_path.touch()
    monkeypatch.setattr(inst, "TARGET", base)
    monkeypatch.setattr(inst, "RECEIPT", receipt_path)
    monkeypatch.setattr(inst, "JOURNAL", journal_path)
    monkeypatch.setattr(inst, "EXPECTED_FILES", 2)
    monkeypatch.setattr(inst, "EXPECTED_DIRECTORIES", 2)
    files = ["a", "b"]
    artifact = hashlib.sha256(json.dumps(
        files, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode()).hexdigest()
    receipt = {
        "schema": "ATLAS_QD_D_RUNTIME_INSTALLATION_V1",
        "stage": "D_RUNTIME_LAYOUT_VERIFIED",
        "release_path": str(base),
        "source_commit": inst.SOURCE,
        "files": files,
        "directories": ["x", "y"],
        "archive_sha256": inst.ARCHIVE_SHA,
        "inventory_sha256": inst.INVENTORY_SHA,
        "selected": False,
        "financial_effects": False,
        "provider_connections": False,
        "operational_acceptance": False,
        "layout": {
            "executable": str(base / "python/python.exe"),
            "base": str(base / "python/python.exe"),
            "prefix": str(base / "python"),
            "base_prefix": str(base / "python"),
            "stdlib": str(base / "python/Lib"),
            "bits": 64,
            "version": [3, 12],
        },
        "artifact_digest": artifact,
    }
    if fault == "wrong_root":
        receipt["release_path"] = str(tmp_path / "other")
    if fault == "bad_ledger":
        receipt["financial_effects"] = True
    raw = json.dumps(receipt, sort_keys=True, allow_nan=False).encode()
    receipt_sha = hashlib.sha256(raw).hexdigest()
    first = {
        "schema": "ATLAS_R23_UNSELECTED_CODE_INSTALL_INTENT_V1",
        "source_commit": inst.SOURCE,
        "archive_sha256": inst.ARCHIVE_SHA,
        "target": str(base),
        "financial_authority": False,
        "selection_allowed": False,
        "paper_start_authorized": False,
    }
    last = {
        "stage": "UNSELECTED_CODE_INSTALL_VERIFIED",
        "receipt_sha256": receipt_sha if fault != "bad_ack" else "f" * 64,
    }
    journal = b"\n".join(
        json.dumps(row, sort_keys=True).encode() for row in (first, last)
    )
    monkeypatch.setattr(
        select, "source_bytes",
        lambda path, name, maximum_bytes: (
            raw if name == receipt_path.name else journal
        ),
    )
    monkeypatch.setattr(
        select.releases, "validate_spec", lambda value, domain: value,
    )
    monkeypatch.setattr(
        select.releases, "validate_native_install_ack",
        lambda spec, received, journal_bytes: True,
    )
    if fault == "good":
        value = select._receipt_and_journal()
        assert value["receipt_sha256"] == receipt_sha
        assert value["artifact_digest"] == artifact
    else:
        with pytest.raises(ValueError, match="R23_"):
            select._receipt_and_journal()


def test_source_only_selection_cannot_deem_financial_authorization():
    src = Path(select.__file__).read_text(encoding="utf-8")
    assert '"paper_start_authorized": False' in src
    assert '"financial_authority": False' in src
    assert '"live_trading_authorized": False' in src
    assert "store.publish(row)" in src
    assert 'approval_digest(candidate())' in src
