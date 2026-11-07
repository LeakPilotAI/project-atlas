import json

import app.backtest.offline_receipt_binding as binding
from test_historical_evidence_contract import bundle


def test_transient_cross_file_change_requires_refusal(
    tmp_path, monkeypatch
):
    dataset, manifest, receipt = bundle(tmp_path)

    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )

    original_receipt = receipt_path.read_bytes()
    original_capture = binding.capture_evidence_snapshot
    intercepted = False

    def controlled_capture(paths, **kwargs):
        nonlocal intercepted

        # Capture a different receipt while leaving the original
        # restored before the binding performs its final hash check.
        changed = dict(receipt)
        changed["source_record_id"] = "transient-record"

        receipt_path.write_text(
            json.dumps(changed),
            encoding="utf-8",
        )

        try:
            captured = original_capture(paths, **kwargs)
        finally:
            receipt_path.write_bytes(original_receipt)

        intercepted = True
        return captured

    monkeypatch.setattr(
        binding,
        "capture_evidence_snapshot",
        controlled_capture,
    )

    result = binding.bind_offline_receipt(
        dataset,
        manifest,
        receipt_path,
        expected_decision_at=receipt["decision_at"],
        expected_source_id=receipt["source_id"],
        expected_source_record_id=receipt["source_record_id"],
    )

    assert intercepted
    assert result.classification == "EVIDENCE_REFUSED"
    assert result.historical_availability_authenticated is False
    assert result.predictive_skill_established is False
