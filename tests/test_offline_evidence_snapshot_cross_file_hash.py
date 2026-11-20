import json

import app.backtest.offline_receipt_binding as binding
from test_historical_evidence_contract import bundle


def test_transient_valid_receipt_substitution_refused(
    tmp_path, monkeypatch
):
    dataset, manifest, receipt = bundle(tmp_path)

    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )

    original_bytes = receipt_path.read_bytes()
    original_capture = binding.capture_evidence_snapshot
    intercepted = False

    def controlled_capture(paths, **kwargs):
        nonlocal intercepted

        # Semantically valid receipt, but different bytes.
        replacement = dict(receipt)
        replacement["extra_untrusted_note"] = "transient"

        receipt_path.write_text(
            json.dumps(replacement),
            encoding="utf-8",
        )

        try:
            captured = original_capture(paths, **kwargs)
        finally:
            receipt_path.write_bytes(original_bytes)

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
    assert receipt_path.read_bytes() == original_bytes

    assert result.classification == "EVIDENCE_REFUSED"
    assert result.integrity_verified is False
    assert result.historical_availability_authenticated is False
    assert result.predictive_skill_established is False

    assert any(
        "Evidence changed during snapshot capture" in reason
        for reason in result.reasons
    )
