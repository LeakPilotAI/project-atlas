"""R17 exact install-ACK -> future native r0016 selection proposal, no publish.

Synthetic receipt cases are pure JSON only; no actual installed file is used
as an acceptance claim and no native selection record is written.
"""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from scripts import atlas_r17_selection_handoff as handoff
from scripts import release_selection


@pytest.fixture(scope="module")
def synthetic_complete_receipt():
    files = [{
        "path": f"python/Lib/site-packages/review_{i:05d}.dat",
        "id": [1, 1, i+1], "bytes": 0, "sha256": "a"*64,
    } for i in range(handoff.EXPECTED_TOTAL_FILES)]
    directories = [{"path": ".", "id": [2, 1, 1]}] + [
        {"path": f"python/Lib/section_{i:04d}", "id": [2, 1, i+2]}
        for i in range(handoff.EXPECTED_TOTAL_DIRECTORIES - 1)
    ]
    target = handoff.TARGET
    receipt = {
        "schema": "ATLAS_QD_D_RUNTIME_INSTALLATION_V1",
        "stage": "D_RUNTIME_LAYOUT_VERIFIED",
        "source_commit": handoff.SOURCE,
        "release_path": str(target),
        "files": files, "directories": directories,
        "archive_sha256": handoff.ARCHIVE_SHA,
        "inventory_sha256": handoff.INVENTORY_SHA,
        "selected": False, "financial_effects": False,
        "provider_connections": False, "operational_acceptance": False,
        "layout": {
            "executable": str(target/"python/python.exe"),
            "base": str(target/"python/python.exe"),
            "prefix": str(target/"python"),
            "base_prefix": str(target/"python"),
            "stdlib": str(target/"python/Lib"),
            "bits": 64, "version": [3, 12],
        },
        "artifact_digest": hashlib.sha256(json.dumps(
            files, sort_keys=True, separators=(",",":")).encode()).hexdigest(),
    }
    return receipt


def encode_and_journal(receipt):
    raw = json.dumps(receipt, sort_keys=True, allow_nan=False).encode()
    intent = {
        "schema": "ATLAS_R17_UNSELECTED_CODE_INSTALL_INTENT_V1",
        "source_commit": handoff.SOURCE,
        "archive_sha256": handoff.ARCHIVE_SHA,
        "target": str(handoff.TARGET),
        "financial_authority": False,
        "selection_allowed": False,
        "paper_start_authorized": False,
    }
    ack = {
        "stage": "UNSELECTED_CODE_INSTALL_VERIFIED",
        "receipt_sha256": hashlib.sha256(raw).hexdigest(),
    }
    journal = (
        json.dumps(intent, sort_keys=True).encode() + b"\n"
        + json.dumps(ack, sort_keys=True).encode()
    )
    return raw, journal


def test_pure_full_install_receipt_proposes_nonfinancial_r0016_exactly(
        synthetic_complete_receipt):
    receipt = synthetic_complete_receipt
    raw, journal = encode_and_journal(receipt)
    row = handoff.candidate_from_receipt(
        receipt=receipt, receipt_bytes=raw, journal_bytes=journal)
    assert row["schema"] == "QD_RELEASE_SELECTION_RECEIPT_V1"
    assert row["revision"] == 16
    assert row["previous"] == handoff.R16_HEAD
    assert row["action"] == "SELECT"
    assert row["restores"] is None
    assert row["selected"]["release"] == handoff.SOURCE
    assert row["selected"]["artifact_digest"] == receipt["artifact_digest"]
    assert row["selected"]["receipt_sha256"] == hashlib.sha256(raw).hexdigest()
    assert release_selection.validate_spec(row["selected"], "WINDOWS_LOCAL") == row["selected"]
    assert len(release_selection.digest(row)) == 64


@pytest.mark.parametrize("damage", [
    "selected", "financial_effects", "provider_connections",
    "operational_acceptance", "release_path", "source_commit", "archive_sha256",
    "inventory_sha256", "stage", "schema", "artifact_digest",
    "wrong_python_executable", "missing_file", "duplicate_file",
    "bad_file_sha", "missing_directory", "duplicate_root_dir",
    "extra_receipt_field",
])
def test_unreviewed_or_partial_install_receipt_cannot_become_selected(
        synthetic_complete_receipt, damage):
    record = copy.deepcopy(synthetic_complete_receipt)
    if damage in ("selected", "financial_effects", "provider_connections",
                  "operational_acceptance"):
        record[damage] = True
    elif damage == "wrong_python_executable":
        record["layout"]["executable"] = "C:\\Foreign\\python.exe"
    elif damage == "missing_file":
        record["files"].pop()
    elif damage == "duplicate_file":
        record["files"][1] = copy.deepcopy(record["files"][0])
    elif damage == "bad_file_sha":
        record["files"][0]["sha256"] = "INVALID"
    elif damage == "missing_directory":
        record["directories"].pop()
    elif damage == "duplicate_root_dir":
        record["directories"][1] = copy.deepcopy(record["directories"][0])
    elif damage == "extra_receipt_field":
        record["finance_issuer_approved"] = True
    else:
        record[damage] = "BAD"
    raw, journal = encode_and_journal(record)
    with pytest.raises((ValueError, KeyError)):
        handoff.candidate_from_receipt(
            receipt=record, receipt_bytes=raw, journal_bytes=journal)


@pytest.mark.parametrize("damage", [
    "no_ack", "three_stages", "wrong_ack_sha", "unreviewed_intent_scope",
    "selection_grant_in_intent", "financial_grant_in_intent",
    "bad_intent_schema", "wrong_intent_release",
])
def test_stale_or_foreign_journal_never_qualifies_source_only_selection(
        synthetic_complete_receipt, damage):
    receipt = synthetic_complete_receipt
    raw, journal = encode_and_journal(receipt)
    rows = journal.splitlines()
    if damage == "no_ack":
        journal = rows[0]
    elif damage == "three_stages":
        journal += b'\n{"stage":"UNKNOWN"}'
    elif damage == "wrong_ack_sha":
        ack = json.loads(rows[-1])
        ack["receipt_sha256"] = "f"*64
        journal = rows[0] + b"\n" + json.dumps(ack).encode()
    else:
        intent = json.loads(rows[0])
        if damage == "unreviewed_intent_scope":
            intent["paper_start_authorized"] = True
        elif damage == "selection_grant_in_intent":
            intent["selection_allowed"] = True
        elif damage == "financial_grant_in_intent":
            intent["financial_authority"] = True
        elif damage == "bad_intent_schema":
            intent["schema"] = "HISTORIC_R16"
        elif damage == "wrong_intent_release":
            intent["source_commit"] = "f"*40
        journal = json.dumps(intent,sort_keys=True).encode()+b"\n"+rows[-1]
    with pytest.raises(ValueError):
        handoff.candidate_from_receipt(
            receipt=receipt, receipt_bytes=raw, journal_bytes=journal)


def test_noncanonical_receipt_refused_even_when_dict_matches(
        synthetic_complete_receipt):
    receipt = synthetic_complete_receipt
    raw, journal = encode_and_journal(receipt)
    noncanonical = raw.replace(b'": ', b'":', 1)
    with pytest.raises(ValueError, match="NONCANONICAL"):
        handoff.candidate_from_receipt(
            receipt=receipt, receipt_bytes=noncanonical,
            journal_bytes=journal)


def test_genuine_native_selected_r16_waits_for_separate_r17_install():
    record = handoff.inspect()
    if "proposed_selection_record" in record:
        assert record["status"] == "INSTALLED_RECEIPT_PROPOSED_NOT_NATIVE_HANDLE_ACCEPTED"
        assert record["installed_original_handle_readback_accepted"] is False
        assert record["proposed_selection_record"]["selected"]["release"] == handoff.SOURCE
    else:
        assert record["status"] == "WAITING_FOR_SEPARATELY_APPROVED_R17_NATIVE_CODE_INSTALL"
    assert record["native_selected_predecessor"] == "R16"
    assert record["native_selected_head"] == handoff.R16_HEAD
    assert record["proposed_revision"] == 16
    assert record["selection_authorized"] is False
    assert record["native_selection_published"] is False
    assert record["financial_authority"] is False
    assert record["paper_start_authorized"] is False
    assert not (handoff.SELECTION_ROOT/"r0016.json").exists()


def test_partial_target_native_install_refused_without_proposal(
        monkeypatch, tmp_path):
    monkeypatch.setattr(handoff, "require_selected_r16", lambda: True)
    monkeypatch.setattr(handoff, "require_original_financial_roots_untouched",
                        lambda: True)
    monkeypatch.setattr(handoff, "SELECTION_ROOT", tmp_path)
    monkeypatch.setattr(handoff, "TARGET", tmp_path/"candidate")
    monkeypatch.setattr(handoff, "RECEIPT", tmp_path/"receipt.json")
    monkeypatch.setattr(handoff, "JOURNAL", tmp_path/"partial.journal")
    (tmp_path/"partial.journal").write_text("INCOMPLETE", encoding="utf-8")
    with pytest.raises(ValueError, match="PARTIAL_NATIVE_INSTALL"):
        handoff.inspect()
