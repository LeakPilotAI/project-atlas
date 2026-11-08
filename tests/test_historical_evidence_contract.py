import json
from dataclasses import asdict

import pytest

from app.backtest.historical_evidence_contract import validate_historical_evidence
from app.backtest.manifest import build_manifest, write_manifest
from test_backtest_manifest import FIXTURE


def bundle(tmp_path):
    manifest = build_manifest(
        FIXTURE,
        candles_source="candles",
        funding_source="funding",
        oi_source="oi",
        rolling_volume_source="volume",
        htf_context_source="htf",
        pit_aligned=True,
    )
    manifest_path = write_manifest(manifest, tmp_path / "manifest.json")
    identity = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt = {
        "schema_version": 1,
        "dataset_sha256": identity["dataset_sha256"],
        "manifest_id": identity["manifest_id"],
        "source_id": "fixture:untrusted",
        "source_record_id": "record-001",
        "published_at": "2026-01-01T00:00:00Z",
        "observed_at": "2026-01-01T00:01:00Z",
        "decision_at": "2026-01-01T00:02:00Z",
    }
    return FIXTURE, manifest_path, receipt


def evaluate(tmp_path, receipt):
    dataset, manifest, _ = bundle(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return validate_historical_evidence(dataset, manifest, receipt_path)


def test_consistent_receipt_remains_unauthenticated(tmp_path):
    dataset, manifest, receipt = bundle(tmp_path)
    result = evaluate(tmp_path, receipt)
    assert result.accepted_structurally is True
    assert result.historical_availability_authenticated is False
    assert result.classification == "STRUCTURALLY_CONSISTENT_UNAUTHENTICATED"
    assert asdict(result)["reasons"]


@pytest.mark.parametrize("field,value", [
    ("source_id", ""),
    ("source_record_id", None),
    ("published_at", "not-a-time"),
    ("observed_at", "2026-01-01T00:03:00Z"),
    ("published_at", "2026-01-01T00:04:00Z"),
    ("schema_version", True),
    ("manifest_id", "wrong"),
    ("dataset_sha256", "0" * 64),
])
def test_bad_receipts_fail_closed(tmp_path, field, value):
    _, _, receipt = bundle(tmp_path)
    receipt[field] = value
    result = evaluate(tmp_path, receipt)
    assert result.accepted_structurally is False
    assert result.historical_availability_authenticated is False
    assert result.classification == "EVIDENCE_REFUSED"


def test_missing_receipt_refused(tmp_path):
    dataset, manifest, _ = bundle(tmp_path)
    result = validate_historical_evidence(dataset, manifest, tmp_path / "missing.json")
    assert result.classification == "EVIDENCE_REFUSED"


def test_non_object_receipt_refused(tmp_path):
    result = evaluate(tmp_path, [])
    assert result.classification == "EVIDENCE_REFUSED"


def test_expected_decision_mismatch_refused(tmp_path):
    dataset, manifest, receipt = bundle(tmp_path)
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    result = validate_historical_evidence(
        dataset, manifest, path,
        expected_decision_at="2026-01-01T00:03:00Z",
    )
    assert result.classification == "EVIDENCE_REFUSED"


def test_expected_source_mismatch_refused(tmp_path):
    dataset, manifest, receipt = bundle(tmp_path)
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    result = validate_historical_evidence(
        dataset, manifest, path,
        expected_source_id="independent:archive",
    )
    assert result.classification == "EVIDENCE_REFUSED"


def test_expected_record_mismatch_refused(tmp_path):
    dataset, manifest, receipt = bundle(tmp_path)
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    result = validate_historical_evidence(
        dataset, manifest, path,
        expected_source_record_id="different-record",
    )
    assert result.classification == "EVIDENCE_REFUSED"


def test_duplicate_json_keys_refused(tmp_path):
    dataset, manifest, receipt = bundle(tmp_path)
    text = json.dumps(receipt)
    text = text.replace(
        '"schema_version": 1',
        '"schema_version": 1, "schema_version": 2',
        1,
    )
    path = tmp_path / "receipt.json"
    path.write_text(text, encoding="utf-8")

    result = validate_historical_evidence(dataset, manifest, path)
    assert result.classification == "EVIDENCE_REFUSED"


def test_exact_decision_boundary_allowed_structurally(tmp_path):
    dataset, manifest, receipt = bundle(tmp_path)
    receipt["observed_at"] = receipt["decision_at"]
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    result = validate_historical_evidence(
        dataset, manifest, path,
        expected_decision_at=receipt["decision_at"],
        expected_source_id=receipt["source_id"],
        expected_source_record_id=receipt["source_record_id"],
    )
    assert result.accepted_structurally is True
    assert result.historical_availability_authenticated is False
