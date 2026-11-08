import json

from app.backtest.historical_evidence_contract import (
    validate_historical_evidence,
    validate_historical_evidence_bytes,
)
from test_historical_evidence_contract import bundle


def test_byte_and_path_contract_agree(tmp_path):
    dataset, manifest, receipt = bundle(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    expected = {
        "expected_decision_at": receipt["decision_at"],
        "expected_source_id": receipt["source_id"],
        "expected_source_record_id": receipt["source_record_id"],
    }

    path_result = validate_historical_evidence(
        dataset, manifest, receipt_path, **expected
    )
    byte_result = validate_historical_evidence_bytes(
        dataset.read_bytes(),
        manifest.read_bytes(),
        receipt_path.read_bytes(),
        **expected,
    )

    assert byte_result == path_result
    assert byte_result.historical_availability_authenticated is False


def test_captured_receipt_identity_mismatch_refused(tmp_path):
    dataset, manifest, receipt = bundle(tmp_path)

    changed = dict(receipt)
    changed["source_record_id"] = "wrong-record"

    result = validate_historical_evidence_bytes(
        dataset.read_bytes(),
        manifest.read_bytes(),
        json.dumps(changed).encode(),
        expected_decision_at=receipt["decision_at"],
        expected_source_id=receipt["source_id"],
        expected_source_record_id=receipt["source_record_id"],
    )

    assert result.classification == "EVIDENCE_REFUSED"
    assert result.historical_availability_authenticated is False


def test_captured_receipt_duplicate_keys_refused(tmp_path):
    dataset, manifest, receipt = bundle(tmp_path)

    encoded = json.dumps(receipt)
    duplicate = encoded.replace(
        "{",
        '{"source_id":"duplicate",',
        1,
    )

    result = validate_historical_evidence_bytes(
        dataset.read_bytes(),
        manifest.read_bytes(),
        duplicate.encode(),
    )

    assert result.classification == "EVIDENCE_REFUSED"
    assert result.historical_availability_authenticated is False


def test_captured_receipt_nonfinite_extra_evidence_refused(tmp_path):
    dataset, manifest, receipt = bundle(tmp_path)
    encoded = json.dumps(receipt).replace("{", '{"extra_metric":NaN,', 1)
    result = validate_historical_evidence_bytes(
        dataset.read_bytes(), manifest.read_bytes(), encoded.encode()
    )
    assert result.classification == "EVIDENCE_REFUSED"
    assert result.historical_availability_authenticated is False
