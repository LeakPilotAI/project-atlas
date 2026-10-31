import json
import shutil

from app.backtest.offline_receipt_binding import bind_offline_receipt
from test_historical_evidence_contract import bundle


def setup_receipt(tmp_path):
    dataset, manifest, receipt = bundle(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return dataset, manifest, receipt_path, receipt


def verify(dataset, manifest, receipt_path, expected):
    return bind_offline_receipt(
        dataset,
        manifest,
        receipt_path,
        expected_decision_at=expected["decision_at"],
        expected_source_id=expected["source_id"],
        expected_source_record_id=expected["source_record_id"],
    )


def assert_no_authority(result):
    assert result.historical_availability_authenticated is False
    assert result.predictive_skill_established is False


def test_valid_fixture_is_structural_only(tmp_path):
    dataset, manifest, path, expected = setup_receipt(tmp_path)
    result = verify(dataset, manifest, path, expected)
    assert result.classification == "STRUCTURALLY_CONSISTENT_UNAUTHENTICATED"
    assert result.integrity_verified is True
    assert_no_authority(result)


def test_external_decision_mismatch_refused(tmp_path):
    dataset, manifest, path, expected = setup_receipt(tmp_path)
    expected["decision_at"] = "2026-01-01T00:03:00Z"
    result = verify(dataset, manifest, path, expected)
    assert result.classification == "EVIDENCE_REFUSED"
    assert_no_authority(result)


def test_external_source_and_record_mismatches_refused(tmp_path):
    dataset, manifest, path, expected = setup_receipt(tmp_path)
    for field in ("source_id", "source_record_id"):
        changed = dict(expected)
        changed[field] = "different-external-identity"
        result = verify(dataset, manifest, path, changed)
        assert result.classification == "EVIDENCE_REFUSED"
        assert_no_authority(result)


def test_dataset_tampering_refused(tmp_path):
    dataset, manifest, path, expected = setup_receipt(tmp_path)
    copied = tmp_path / "dataset-copy.csv"
    shutil.copyfile(dataset, copied)
    copied.write_bytes(copied.read_bytes() + b"\nTAMPERED\n")

    result = verify(copied, manifest, path, expected)
    assert result.classification == "INTEGRITY_REFUSED"
    assert result.integrity_verified is False
    assert_no_authority(result)


def test_manifest_tampering_refused(tmp_path):
    dataset, manifest, path, expected = setup_receipt(tmp_path)
    changed = json.loads(manifest.read_text(encoding="utf-8"))
    changed["dataset_sha256"] = "0" * 64
    manifest.write_text(json.dumps(changed), encoding="utf-8")

    result = verify(dataset, manifest, path, expected)
    assert result.classification == "INTEGRITY_REFUSED"
    assert result.integrity_verified is False
    assert_no_authority(result)


def test_duplicate_receipt_keys_refused(tmp_path):
    dataset, manifest, path, expected = setup_receipt(tmp_path)
    content = path.read_text(encoding="utf-8")
    content = content.replace(
        '"schema_version": 1',
        '"schema_version": 1, "schema_version": 1',
        1,
    )
    path.write_text(content, encoding="utf-8")

    result = verify(dataset, manifest, path, expected)
    assert result.classification == "EVIDENCE_REFUSED"
    assert_no_authority(result)


def test_future_observation_refused(tmp_path):
    dataset, manifest, path, expected = setup_receipt(tmp_path)
    changed = json.loads(path.read_text(encoding="utf-8"))
    changed["observed_at"] = "2026-01-01T00:04:00Z"
    path.write_text(json.dumps(changed), encoding="utf-8")

    result = verify(dataset, manifest, path, expected)
    assert result.classification == "EVIDENCE_REFUSED"
    assert_no_authority(result)


def test_replaced_receipt_requires_fresh_verification(tmp_path):
    dataset, manifest, path, expected = setup_receipt(tmp_path)

    first = verify(dataset, manifest, path, expected)
    assert first.classification == "STRUCTURALLY_CONSISTENT_UNAUTHENTICATED"

    changed = json.loads(path.read_text(encoding="utf-8"))
    changed["source_record_id"] = "replaced-record"
    path.write_text(json.dumps(changed), encoding="utf-8")

    second = verify(dataset, manifest, path, expected)
    assert second.classification == "EVIDENCE_REFUSED"
    assert_no_authority(second)

    path.unlink()
    third = verify(dataset, manifest, path, expected)
    assert third.classification == "EVIDENCE_REFUSED"
    assert_no_authority(third)
