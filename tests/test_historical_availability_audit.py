import json
from dataclasses import asdict

from app.backtest.historical_availability_audit import audit_historical_availability
from app.backtest.manifest import build_manifest, write_manifest
from test_backtest_manifest import FIXTURE


def make_bundle(tmp_path):
    manifest = build_manifest(
        FIXTURE,
        candles_source="candles",
        funding_source="funding",
        oi_source="oi",
        rolling_volume_source="volume",
        htf_context_source="htf",
        pit_aligned=True,
    )
    path = write_manifest(manifest, tmp_path / "manifest.json")
    return FIXTURE, path


def test_verified_bytes_do_not_imply_historical_authentication(tmp_path):
    dataset, manifest = make_bundle(tmp_path)
    result = audit_historical_availability(dataset, manifest)

    assert result.integrity_verified is True
    assert result.historical_availability_authenticated is False
    assert result.classification == "CLAIMED_HISTORICAL_AVAILABILITY"


def test_tampered_manifest_refused(tmp_path):
    dataset, manifest = make_bundle(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["symbol"] = "ETH"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    result = audit_historical_availability(dataset, manifest)

    assert result.integrity_verified is False
    assert result.historical_availability_authenticated is False
    assert result.classification == "INTEGRITY_REFUSED"


def test_missing_dataset_refused(tmp_path):
    _, manifest = make_bundle(tmp_path)
    result = audit_historical_availability(tmp_path / "missing.csv", manifest)

    assert result.classification == "INTEGRITY_REFUSED"
    assert result.integrity_verified is False


def test_missing_manifest_refused(tmp_path):
    result = audit_historical_availability(FIXTURE, tmp_path / "missing.json")

    assert result.classification == "INTEGRITY_REFUSED"
    assert result.historical_availability_authenticated is False


def test_audit_result_is_explicit_and_serializable(tmp_path):
    dataset, manifest = make_bundle(tmp_path)
    result = audit_historical_availability(dataset, manifest)
    payload = json.loads(json.dumps(asdict(result)))

    assert payload["historical_availability_authenticated"] is False
    assert payload["integrity_verified"] is True
    assert payload["reasons"]


def test_receipt_decision_time_enforcement(tmp_path):
    from app.backtest.historical_evidence_contract import validate_historical_evidence

    dataset, manifest = make_bundle(tmp_path)
    identity = json.loads(manifest.read_text(encoding="utf-8"))
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
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    accepted = audit_historical_availability(
        dataset, manifest,
        receipt=path,
        expected_decision_at="2026-01-01T00:02:00Z",
    )
    assert accepted.integrity_verified is True
    assert accepted.historical_availability_authenticated is False
    assert accepted.classification == "STRUCTURALLY_CONSISTENT_UNAUTHENTICATED"

    refused = audit_historical_availability(
        dataset, manifest,
        receipt=path,
        expected_decision_at="2026-01-01T00:00:00Z",
    )
    assert refused.classification == "EVIDENCE_REFUSED"
    assert refused.historical_availability_authenticated is False


def test_receipt_requires_external_decision_time(tmp_path):
    dataset, manifest = make_bundle(tmp_path)
    result = audit_historical_availability(
        dataset, manifest,
        receipt=tmp_path / "receipt.json",
    )
    assert result.classification == "EVIDENCE_REFUSED"
    assert result.historical_availability_authenticated is False
