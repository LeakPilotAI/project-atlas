import json

import app.backtest.offline_receipt_binding as binding
from test_historical_evidence_contract import bundle


def test_receipt_changed_during_capture_must_refuse(
    tmp_path, monkeypatch
):
    dataset, manifest, receipt = bundle(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    original_capture = binding.capture_evidence_snapshot
    mutation_triggered = False

    def controlled_capture(paths, **kwargs):
        nonlocal mutation_triggered

        captured = original_capture(paths, **kwargs)

        replacement = dict(receipt)
        replacement["source_record_id"] = "replaced-record"
        receipt_path.write_text(
            json.dumps(replacement),
            encoding="utf-8",
        )

        mutation_triggered = True
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

    assert mutation_triggered
    assert result.classification == "EVIDENCE_REFUSED"
    assert result.integrity_verified is False
    assert result.historical_availability_authenticated is False
    assert result.predictive_skill_established is False
