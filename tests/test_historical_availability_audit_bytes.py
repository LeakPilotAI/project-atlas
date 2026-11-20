import json

from app.backtest.historical_availability_audit import (
    audit_historical_availability,
    audit_historical_availability_bytes,
)
from test_historical_evidence_contract import bundle


def test_byte_and_path_audit_classification_agree(tmp_path):
    dataset, manifest, receipt = bundle(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    kwargs = {
        "expected_decision_at": receipt["decision_at"],
        "expected_source_id": receipt["source_id"],
        "expected_source_record_id": receipt["source_record_id"],
    }

    path_result = audit_historical_availability(
        dataset, manifest, receipt=receipt_path, **kwargs
    )

    byte_result = audit_historical_availability_bytes(
        dataset.read_bytes(),
        manifest.read_bytes(),
        receipt_bytes=receipt_path.read_bytes(),
        **kwargs,
    )

    assert byte_result.classification == path_result.classification
    assert byte_result.integrity_verified == path_result.integrity_verified
    assert byte_result.reasons == path_result.reasons
    assert byte_result.historical_availability_authenticated is False


def test_byte_audit_rejects_dataset_tampering(tmp_path):
    dataset, manifest, receipt = bundle(tmp_path)

    result = audit_historical_availability_bytes(
        dataset.read_bytes() + b"tampered",
        manifest.read_bytes(),
        receipt_bytes=json.dumps(receipt).encode(),
        expected_decision_at=receipt["decision_at"],
    )

    assert result.classification == "INTEGRITY_REFUSED"
    assert result.integrity_verified is False
    assert result.historical_availability_authenticated is False


def test_byte_audit_requires_external_decision_time(tmp_path):
    dataset, manifest, receipt = bundle(tmp_path)

    result = audit_historical_availability_bytes(
        dataset.read_bytes(),
        manifest.read_bytes(),
        receipt_bytes=json.dumps(receipt).encode(),
    )

    assert result.classification == "EVIDENCE_REFUSED"
    assert result.historical_availability_authenticated is False


def test_byte_audit_without_receipt_remains_unauthenticated(tmp_path):
    dataset, manifest, receipt = bundle(tmp_path)

    result = audit_historical_availability_bytes(
        dataset.read_bytes(),
        manifest.read_bytes(),
    )

    assert result.classification == "CLAIMED_HISTORICAL_AVAILABILITY"
    assert result.historical_availability_authenticated is False
