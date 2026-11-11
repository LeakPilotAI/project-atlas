"""R16 source-only selection handoff, from actual R15 native-chain predecessor.

Synthetic 10,549-file receipt is never installed or published. These tests
assert row-proposal eligibility only; native installed verifier + explicit
operator selection authorization remain separate requirements.
"""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from scripts import atlas_r16_selection_handoff as handoff
from scripts import release_selection as selector
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    RECEIPT as R15_RECEIPT, selected_code,
)
from scripts.observation_runtime.atlas_r16_code_install_plan_preflight import (
    SOURCE_COMMIT, ARCHIVE_SHA, INVENTORY_SHA, TARGET, RECEIPT,
)


@pytest.fixture(scope="module")
def baseline():
    prior = json.loads(R15_RECEIPT.read_text(encoding="utf-8-sig"))
    assert len(prior["files"]) == 10526
    assert len(prior["directories"]) == 912
    current = copy.deepcopy(prior)
    current.update(
        source_commit=SOURCE_COMMIT, archive_sha256=ARCHIVE_SHA,
        inventory_sha256=INVENTORY_SHA, release_path=str(TARGET),
    )
    for i in range(23):
        current["files"].append({
            "path": f"scripts/observation_runtime/SYNTHETIC_R16_{i}.py",
            "bytes": 0,
            "sha256": hashlib.sha256(b"").hexdigest(),
            "id": [9999, 99999, i + 1],
        })
    for field, suffix in {
        "executable": "python/python.exe", "base": "python/python.exe",
        "prefix": "python", "base_prefix": "python",
        "stdlib": "python/Lib",
    }.items():
        current["layout"][field] = str(TARGET / suffix)
    current["artifact_digest"] = hashlib.sha256(json.dumps(
        current["files"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return current


def make_journal(receipt):
    raw = json.dumps(receipt, sort_keys=True, allow_nan=False).encode()
    first = {
        "schema": "ATLAS_R16_UNSELECTED_CODE_INSTALL_INTENT_V1",
        "source_commit": SOURCE_COMMIT,
        "archive_sha256": ARCHIVE_SHA,
        "target": str(TARGET),
        "selection_allowed": False, "financial_authority": False,
        "provider_access": False, "startup_authorized": False,
    }
    final = {
        "stage": "UNSELECTED_CODE_INSTALL_VERIFIED",
        "receipt_sha256": hashlib.sha256(raw).hexdigest(),
    }
    return raw, (
        json.dumps(first, sort_keys=True).encode() + b"\n"
        + json.dumps(final, sort_keys=True).encode() + b"\n"
    )


def pure(receipt, *, journal=None, raw=None):
    actual, original = make_journal(receipt)
    return handoff.candidate_from_receipt(
        receipt=receipt, receipt_bytes=actual if raw is None else raw,
        journal_bytes=original if journal is None else journal,
    )


def test_real_native_r15_predecessor_and_waiting_r16_is_read_only():
    prior = selected_code()
    assert prior["revision"] == 14
    result = handoff.inspect()
    assert result["schema"] == "ATLAS_R16_CODE_SELECTION_HANDOFF_V1"
    assert result["status"] == "WAITING_FOR_SEPARATELY_APPROVED_R16_CODE_ONLY_NATIVE_INSTALL"
    assert result["expected_revision"] == 15
    assert result["selected_predecessor_head"] == prior["selected_native_head"]
    assert result["selected_predecessor_record_sha256"] == (
        prior["selected_native_record_sha256"])
    assert result["new_selection_record_proposed"] is False
    assert result["new_selection_record_written"] is False
    assert result["selection_authorized"] is False
    assert result["financial_authority"] is False
    assert result["paper_start_authorized"] is False
    assert result["live_orders_authorized"] is False
    assert not TARGET.exists() and not RECEIPT.exists()
    assert not (handoff.SELECTION_ROOT / "r0015.json").exists()


def test_complete_synthetic_native_receipt_only_proposes_deterministic_r0015(baseline):
    row = pure(baseline)
    assert row["revision"] == 15
    assert row["schema"] == "QD_RELEASE_SELECTION_RECEIPT_V1"
    assert row["action"] == "SELECT"
    assert row["previous"] == handoff.SELECTED_HEAD
    assert row["selected"]["release"] == SOURCE_COMMIT
    assert row["selected"]["root"] == str(TARGET)
    assert row["selected"]["receipt"] == str(RECEIPT)
    assert row["selected"]["artifact_digest"] == baseline["artifact_digest"]
    assert len(row["operation"]) == 32
    assert row == pure(baseline)
    assert selector.digest(row) == selector.digest(pure(baseline))
    assert row["restores"] is None
    # Validating a synthetic row never makes it accepted native selection.
    assert not (handoff.SELECTION_ROOT / "r0015.json").exists()


@pytest.mark.parametrize("change", [
    "source_commit", "release_path", "archive_sha256", "inventory_sha256",
    "selected", "financial_effects", "provider_connections",
    "operational_acceptance", "stage", "schema", "artifact_digest",
    "remove_one_file", "extra_file", "duplicate_path", "duplicate_file_id",
    "relative_escape", "backslash_path", "nonfinite_bytes",
    "remove_directory", "duplicate_directory", "directory_alias",
    "layout_executable", "layout_python_version", "layout_python_bits",
    "extra_financial_grant",
])
def test_modified_unselected_native_receipt_refused(baseline, change):
    receipt = copy.deepcopy(baseline)
    if change in ("source_commit", "release_path", "archive_sha256",
                  "inventory_sha256", "stage", "schema", "artifact_digest"):
        receipt[change] = "SYNTHETIC_TAMPERING"
    elif change in ("selected", "financial_effects", "provider_connections",
                    "operational_acceptance"):
        receipt[change] = True
    elif change == "remove_one_file":
        receipt["files"].pop()
    elif change == "extra_file":
        receipt["files"].append(copy.deepcopy(receipt["files"][-1]))
    elif change == "duplicate_path":
        receipt["files"][1]["path"] = receipt["files"][0]["path"]
    elif change == "duplicate_file_id":
        receipt["files"][1]["id"] = receipt["files"][0]["id"][:]
    elif change == "relative_escape":
        receipt["files"][0]["path"] = "../foreign"
    elif change == "backslash_path":
        receipt["files"][0]["path"] = r"..\foreign"
    elif change == "nonfinite_bytes":
        receipt["files"][0]["bytes"] = -1
    elif change == "remove_directory":
        receipt["directories"].pop()
    elif change == "duplicate_directory":
        receipt["directories"][1]["path"] = receipt["directories"][0]["path"]
    elif change == "directory_alias":
        receipt["directories"][1]["id"] = receipt["directories"][0]["id"][:]
    elif change == "layout_executable":
        receipt["layout"]["executable"] = r"D:\FOREIGN\python.exe"
    elif change == "layout_python_version":
        receipt["layout"]["version"] = [3, 11]
    elif change == "layout_python_bits":
        receipt["layout"]["bits"] = 32
    elif change == "extra_financial_grant":
        receipt["paper_start_authorized"] = True
    with pytest.raises((ValueError, TypeError)):
        pure(receipt)


@pytest.mark.parametrize("bad", [
    b"", b"{}",
    b'{"stage":"UNSELECTED_CODE_INSTALL_VERIFIED"}',
    b'{"x":1}\n{"y":2}\n{"z":3}',
])
def test_incomplete_or_extra_two_stage_ack_refuses(baseline, bad):
    with pytest.raises((ValueError, TypeError)):
        pure(baseline, journal=bad)


def test_wrong_release_intent_or_ack_digest_refuses(baseline):
    raw, original = make_journal(baseline)
    first, second = original.splitlines()
    intent = json.loads(first)
    intent["selection_allowed"] = True
    forged = json.dumps(intent, sort_keys=True).encode() + b"\n" + second
    with pytest.raises(ValueError, match="R16_SELECTION_CREATE_ONLY_INTENT_SCOPE_CHANGED"):
        pure(baseline, journal=forged)
    ack = json.loads(second)
    ack["receipt_sha256"] = "0" * 64
    forged = first + b"\n" + json.dumps(ack).encode()
    with pytest.raises(ValueError, match="SELECTION_INSTALL_ACK_REQUIRED"):
        pure(baseline, journal=forged)


def test_noncanonical_and_duplicate_receipt_json_refuses(baseline):
    raw, _ = make_journal(baseline)
    with pytest.raises(ValueError, match="R16_SELECTION_EXACT_CANONICAL_RECEIPT_REQUIRED"):
        pure(baseline, raw=raw + b" ")
    duplicate = raw.replace(b'"schema": ', b'"schema": "DUPLICATE", "schema": ', 1)
    with pytest.raises(ValueError, match="R16_SELECTION_EXACT_CANONICAL_RECEIPT_REQUIRED"):
        pure(baseline, raw=duplicate)


def test_partial_install_namespace_never_becomes_proposed_selection(tmp_path, monkeypatch):
    from scripts import atlas_r16_selection_handoff as handoff
    target = tmp_path / "release"
    receipt = tmp_path / "install.json"
    journal = receipt.with_suffix(".pending.jsonl")
    monkeypatch.setattr(handoff, "TARGET", target)
    monkeypatch.setattr(handoff, "RECEIPT", receipt)
    monkeypatch.setattr(handoff, "JOURNAL", journal)
    target.mkdir()
    with pytest.raises(ValueError, match="R16_SELECTION_PARTIAL_NATIVE_INSTALL_PRESERVE_NO_RETRY"):
        handoff.inspect()
    target.rmdir()
    journal.write_text("partial-intent", encoding="utf-8")
    with pytest.raises(ValueError, match="R16_SELECTION_PARTIAL_NATIVE_INSTALL_PRESERVE_NO_RETRY"):
        handoff.inspect()


def test_selected_record_replay_namespace_already_attempted_cannot_retry(tmp_path, monkeypatch):
    root = tmp_path / "selection"
    root.mkdir()
    monkeypatch.setattr(handoff, "SELECTION_ROOT", root)
    (root / "r0015.pending").write_text("PENDING", encoding="utf-8")
    with pytest.raises(ValueError, match="R16_SELECTION_ALREADY_ATTEMPTED_DO_NOT_RETRY"):
        handoff.inspect()


def test_missing_receipt_or_nonregular_path_never_trusted(tmp_path):
    path = tmp_path / "empty.json"
    with pytest.raises(ValueError, match="R16_SELECTION_EXACT_EXISTING_REGULAR_RECEIPT_REQUIRED"):
        handoff._strict_small(path, max_bytes=8192)
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="R16_SELECTION_EXACT_EXISTING_REGULAR_RECEIPT_REQUIRED"):
        handoff._strict_small(path, max_bytes=8192)
    path.write_text('{"fake":1}', encoding="utf-8")
    assert handoff._strict_small(path, max_bytes=8192) == b'{"fake":1}'
