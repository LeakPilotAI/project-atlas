"""Lost native windows cannot be replaced by a different Chrome target."""

import copy

import pytest

from tests.v6_browser_witness import verify_window_continuity


def observations():
    window = {"id": 123, "app": "Chrome"}
    stages = ("initial", "navigation_focus", "navigated", "rendered", "tab_closed")
    return window, [
        {
            "stage": stage,
            "window": dict(window),
            "error": None,
            "operator_stopped": False,
            "address_value": "127.0.0.1:12345/",
            "document_url": "http://127.0.0.1:12345/",
            "observed_ns": i + 1,
        }
        for i, stage in enumerate(stages)
    ]


def test_real_target_continuity_is_required_but_not_process_ownership():
    window, records = observations()
    assert verify_window_continuity(window, records)


@pytest.mark.parametrize(
    "fault",
    [
        "lost",
        "replacement",
        "wrong_app",
        "bool_id",
        "foreground_error",
        "operator_stop",
        "missing_url",
        "missing_document",
        "reordered",
        "stale",
        "missing_stage",
    ],
)
def test_window_loss_or_interruption_cannot_be_recovered_into_success(fault):
    window, records = observations()
    row = records[2]
    if fault == "lost":
        row["window"] = None
    if fault == "replacement":
        row["window"]["id"] = 456
    if fault == "wrong_app":
        row["window"]["app"] = "Other"
    if fault == "bool_id":
        row["window"]["id"] = True
    if fault == "foreground_error":
        row["error"] = "foreground window did not report a process id"
    if fault == "operator_stop":
        row["operator_stopped"] = True
    if fault == "missing_url":
        row["address_value"] = ""
    if fault == "missing_document":
        row["document_url"] = ""
    if fault == "reordered":
        records[2], records[3] = records[3], records[2]
    if fault == "stale":
        row["observed_ns"] = records[1]["observed_ns"]
    if fault == "missing_stage":
        records.pop()
    with pytest.raises(ValueError):
        verify_window_continuity(window, copy.deepcopy(records))
