from pathlib import Path

from app.backtest.offline_receipt_binding import bind_offline_receipt


def test_missing_expected_decision_refused(tmp_path):
    result = bind_offline_receipt(
        tmp_path / "data.csv",
        tmp_path / "manifest.json",
        tmp_path / "receipt.json",
        expected_decision_at="",
        expected_source_id="source",
        expected_source_record_id="record",
    )
    assert result.classification == "EVIDENCE_REFUSED"
    assert result.historical_availability_authenticated is False


def test_missing_source_identity_refused(tmp_path):
    result = bind_offline_receipt(
        tmp_path / "data.csv",
        tmp_path / "manifest.json",
        tmp_path / "receipt.json",
        expected_decision_at="2026-01-01T00:00:00Z",
        expected_source_id="",
        expected_source_record_id="record",
    )
    assert result.classification == "EVIDENCE_REFUSED"


def test_missing_record_identity_refused(tmp_path):
    result = bind_offline_receipt(
        tmp_path / "data.csv",
        tmp_path / "manifest.json",
        tmp_path / "receipt.json",
        expected_decision_at="2026-01-01T00:00:00Z",
        expected_source_id="source",
        expected_source_record_id="",
    )
    assert result.classification == "EVIDENCE_REFUSED"


def test_missing_files_refused(tmp_path):
    result = bind_offline_receipt(
        tmp_path / "missing.csv",
        tmp_path / "missing.manifest.json",
        tmp_path / "missing.receipt.json",
        expected_decision_at="2026-01-01T00:00:00Z",
        expected_source_id="source",
        expected_source_record_id="record",
    )
    assert result.classification in (
        "INTEGRITY_REFUSED",
        "EVIDENCE_REFUSED",
    )
    assert result.integrity_verified is False
    assert result.historical_availability_authenticated is False
    assert result.predictive_skill_established is False


def test_non_path_inputs_refused(tmp_path):
    result = bind_offline_receipt(
        "data.csv",
        tmp_path / "manifest.json",
        tmp_path / "receipt.json",
        expected_decision_at="2026-01-01T00:00:00Z",
        expected_source_id="source",
        expected_source_record_id="record",
    )
    assert result.classification == "EVIDENCE_REFUSED"
