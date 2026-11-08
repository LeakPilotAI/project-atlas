import json
from uuid import uuid4

import pytest
from app.core.fixture_lifecycle_receipt import parse_fixture_receipt


@pytest.mark.parametrize("damage", [None, "duplicate", "missing", "version", "run", "process", "stale", "authority"])
def test_strict_receipts_never_grant_authority(damage):
    run = str(uuid4())
    process = {"pid": 123, "created_at": "fixture", "executable": "fixture", "command": "fixture"}
    row = {"schema": "ATLAS_FIXTURE_LIFECYCLE_RECEIPT_V1", "run_id": run, "process": process.copy(),
           "observed_at": 100, "expires_at": 105, "outcome": "COMPLETE_FIXTURE_ONLY", "production_authorized": False}
    if damage == "missing":
        row.pop("outcome")
    elif damage == "version":
        row["schema"] = "V2"
    elif damage == "run":
        row["run_id"] = str(uuid4())
    elif damage == "process":
        row["process"]["created_at"] = "reused"
    elif damage == "stale":
        row["expires_at"] = 101
    elif damage == "authority":
        row["production_authorized"] = True
    raw = json.dumps(row)
    if damage == "duplicate":
        raw = raw[:-1] + ',"run_id":"duplicate"}'
    if damage:
        with pytest.raises(ValueError):
            parse_fixture_receipt(raw, expected_run=run, expected_process=process, now=102)
    else:
        assert parse_fixture_receipt(raw, expected_run=run, expected_process=process, now=102)["production_authorized"] is False


def test_artifact_receipt_binding_refuses_changed_report():
    import hashlib

    from app.core.fixture_lifecycle_receipt import verify_fixture_report_binding
    run = str(uuid4())
    process = {"pid": 123, "created_at": "fixture", "executable": "fixture", "command": "fixture"}
    raw = json.dumps({"schema": "ATLAS_FIXTURE_LIFECYCLE_RECEIPT_V1", "run_id": run, "process": process,
                      "observed_at": 100, "expires_at": 105, "outcome": "INCOMPLETE", "production_authorized": False})
    args = {"expected_run": run, "expected_process": process, "now": 102,
            "expected_inventory_sha256": hashlib.sha256(b"inventory").hexdigest(),
            "expected_report_sha256": hashlib.sha256(b"report").hexdigest(),
            "inventory_bytes": b"inventory", "report_bytes": b"report"}
    assert verify_fixture_report_binding(raw, **args)["production_authorized"] is False
    with pytest.raises(ValueError):
        verify_fixture_report_binding(raw, **{**args, "report_bytes": b"changed"})
