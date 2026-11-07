import json

import app.backtest.offline_receipt_binding as binding
from test_historical_evidence_contract import bundle


def test_original_receipt_restoration_does_not_contaminate_snapshot(
    tmp_path, monkeypatch
):
    dataset, manifest, receipt = bundle(tmp_path)
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    original_bytes = path.read_bytes()
    original_audit = binding.audit_historical_availability_bytes
    intercepted = False

    def controlled_audit(*args, **kwargs):
        nonlocal intercepted

        replacement = dict(receipt)
        replacement["source_record_id"] = "temporary-record"

        path.write_text(json.dumps(replacement), encoding="utf-8")

        try:
            result = original_audit(*args, **kwargs)
        finally:
            path.write_bytes(original_bytes)

        intercepted = True
        assert path.read_bytes() == original_bytes
        return result

    monkeypatch.setattr(
        binding,
        "audit_historical_availability_bytes",
        controlled_audit,
    )

    result = binding.bind_offline_receipt(
        dataset,
        manifest,
        path,
        expected_decision_at=receipt["decision_at"],
        expected_source_id=receipt["source_id"],
        expected_source_record_id=receipt["source_record_id"],
    )

    assert intercepted
    assert result.classification == (
        "STRUCTURALLY_CONSISTENT_UNAUTHENTICATED"
    )
    assert result.integrity_verified is True
    assert result.historical_availability_authenticated is False
    assert result.predictive_skill_established is False
