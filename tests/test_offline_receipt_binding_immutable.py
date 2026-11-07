import json

import app.backtest.offline_receipt_binding as binding
from test_historical_evidence_contract import bundle


def test_binding_uses_captured_evidence(tmp_path, monkeypatch):
    dataset, manifest, receipt = bundle(tmp_path)

    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )

    original_audit = binding.audit_historical_availability_bytes
    observed = []

    def inspect_audit(
        dataset_bytes,
        manifest_bytes,
        *,
        receipt_bytes,
        **kwargs,
    ):
        observed.append(
            (
                dataset_bytes,
                manifest_bytes,
                receipt_bytes,
            )
        )

        return original_audit(
            dataset_bytes,
            manifest_bytes,
            receipt_bytes=receipt_bytes,
            **kwargs,
        )

    monkeypatch.setattr(
        binding,
        "audit_historical_availability_bytes",
        inspect_audit,
    )

    result = binding.bind_offline_receipt(
        dataset,
        manifest,
        receipt_path,
        expected_decision_at=receipt["decision_at"],
        expected_source_id=receipt["source_id"],
        expected_source_record_id=receipt["source_record_id"],
    )

    assert len(observed) == 1

    captured_dataset, captured_manifest, captured_receipt = (
        observed[0]
    )

    assert captured_dataset == dataset.read_bytes()
    assert captured_manifest == manifest.read_bytes()
    assert captured_receipt == receipt_path.read_bytes()

    assert isinstance(captured_dataset, bytes)
    assert isinstance(captured_manifest, bytes)
    assert isinstance(captured_receipt, bytes)

    assert result.classification == (
        "STRUCTURALLY_CONSISTENT_UNAUTHENTICATED"
    )
    assert result.integrity_verified is True
    assert result.historical_availability_authenticated is False
    assert result.predictive_skill_established is False
