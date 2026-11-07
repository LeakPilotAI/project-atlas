"""Strict observation receipt parsing, never operational authorization."""
import json
from uuid import UUID


def parse_fixture_receipt(raw, *, expected_run, expected_process, now):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate receipt field")
            result[key] = value
        return result
    if type(raw) is not str or len(raw.encode()) > 16384:
        raise ValueError("Bounded receipt text required")
    receipt = json.loads(raw, object_pairs_hook=pairs,
                         parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite receipt")))
    if type(receipt) is not dict or set(receipt) != {"schema", "run_id", "process", "observed_at", "expires_at", "outcome", "production_authorized"}:
        raise ValueError("Exact receipt schema required")
    if receipt["schema"] != "ATLAS_FIXTURE_LIFECYCLE_RECEIPT_V1" or receipt["production_authorized"] is not False:
        raise ValueError("Unsupported receipt authority/version")
    UUID(expected_run)
    if receipt["run_id"] != expected_run:
        raise ValueError("Run identity mismatch")
    process = receipt["process"]
    if (type(process) is not dict or set(process) != {"pid", "created_at", "executable", "command"}
            or type(process["pid"]) is not int or process["pid"] <= 4
            or any(type(process[key]) is not str or not process[key] for key in ("created_at", "executable", "command"))
            or process != expected_process):
        raise ValueError("Process evidence mismatch")
    start, end = receipt["observed_at"], receipt["expires_at"]
    if any(type(value) is not int for value in (start, end, now)) or not 0 < end - start <= 5 or not start <= now < end:
        raise ValueError("Stale or contradictory receipt clock")
    if receipt["outcome"] not in ("COMPLETE_FIXTURE_ONLY", "INCOMPLETE", "UNKNOWN"):
        raise ValueError("Unsupported receipt outcome")
    return receipt


def verify_fixture_report_binding(raw, *, expected_run, expected_process, now,
                                  expected_inventory_sha256, expected_report_sha256,
                                  inventory_bytes, report_bytes):
    """Verify expected artifact bytes alongside observation, not authority."""
    import hashlib

    receipt = parse_fixture_receipt(raw, expected_run=expected_run, expected_process=expected_process, now=now)
    for data, expected in ((inventory_bytes, expected_inventory_sha256), (report_bytes, expected_report_sha256)):
        if type(data) is not bytes or type(expected) is not str or hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("Fixture artifact binding mismatch")
    return {"receipt": receipt, "inventory_sha256": expected_inventory_sha256,
            "report_sha256": expected_report_sha256, "production_authorized": False}
