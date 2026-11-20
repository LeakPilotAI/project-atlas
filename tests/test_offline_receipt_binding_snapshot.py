import json
import os
import shutil

import pytest

import app.backtest.offline_receipt_binding as binding
from test_historical_evidence_contract import bundle


def fixture_paths(tmp_path):
    source_dataset, manifest, receipt = bundle(tmp_path)

    # Never modify the shared source fixture.
    dataset = tmp_path / "dataset-copy.csv"
    shutil.copyfile(source_dataset, dataset)

    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    return dataset, manifest, receipt_path, receipt


def verify(paths, receipt):
    dataset, manifest, receipt_path = paths

    return binding.bind_offline_receipt(
        dataset,
        manifest,
        receipt_path,
        expected_decision_at=receipt["decision_at"],
        expected_source_id=receipt["source_id"],
        expected_source_record_id=receipt["source_record_id"],
    )


@pytest.mark.parametrize("changed_file", [
    "dataset",
    "manifest",
    "receipt",
])
def test_same_size_restored_timestamp_mutation_refused(
    tmp_path, monkeypatch, changed_file
):
    dataset, manifest, receipt_path, receipt = fixture_paths(tmp_path)

    targets = {
        "dataset": dataset,
        "manifest": manifest,
        "receipt": receipt_path,
    }
    target = targets[changed_file]

    original_audit = binding.audit_historical_availability_bytes
    intercepted = False

    def mutate_after_audit(*args, **kwargs):
        nonlocal intercepted

        result = original_audit(*args, **kwargs)
        assert result.classification == (
            "STRUCTURALLY_CONSISTENT_UNAUTHENTICATED"
        )

        before_stat = target.stat()
        original = target.read_bytes()
        assert original

        # Same length, different content.
        changed = bytearray(original)
        changed[0] ^= 1

        target.write_bytes(bytes(changed))
        os.utime(
            target,
            ns=(before_stat.st_atime_ns, before_stat.st_mtime_ns),
        )

        assert target.read_bytes() != original
        assert target.stat().st_size == before_stat.st_size
        assert target.stat().st_mtime_ns == before_stat.st_mtime_ns

        intercepted = True
        return result

    monkeypatch.setattr(
        binding,
        "audit_historical_availability_bytes",
        mutate_after_audit,
    )

    result = verify((dataset, manifest, receipt_path), receipt)

    assert intercepted
    assert result.classification == "EVIDENCE_REFUSED"
    assert result.integrity_verified is False
    assert result.historical_availability_authenticated is False
    assert result.predictive_skill_established is False


def test_unchanged_files_remain_structurally_consistent(tmp_path):
    dataset, manifest, receipt_path, receipt = fixture_paths(tmp_path)

    result = verify((dataset, manifest, receipt_path), receipt)

    assert result.classification == (
        "STRUCTURALLY_CONSISTENT_UNAUTHENTICATED"
    )
    assert result.integrity_verified is True
    assert result.historical_availability_authenticated is False
    assert result.predictive_skill_established is False
