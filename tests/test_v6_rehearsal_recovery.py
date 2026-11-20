"""Prospective ownership and browser evidence; no operational authority."""

import copy
import subprocess

import pytest

from scripts.observation_runtime.launch_ownership import OwnershipRefused
from tests.v6_browser_witness import verify_disposable_browser_witness
from tests.v6_job_attribution import verify_disposable_adapter_candidate


def attribution():
    def row(pid, parent, image, command):
        return {
            "pid": pid,
            "parent_pid": parent,
            "created": pid * 1000,
            "image": image,
            "file_id": (1, 2, pid),
            "sha256": "a" * 64,
            "command_line": command,
        }

    command = ["c:\\source\\python.exe", "-I", "fixture.py"]
    worker = row(10, 9, "c:\\source\\python.exe", "worker")
    adapter = row(20, 10, "c:\\source\\python.exe", subprocess.list2cmdline(command))
    console = row(30, 20, "c:\\windows\\system32\\conhost.exe", "EXACT-CONSOLE")
    records = [
        {
            "native": r,
            "retained_handle": r["pid"],
            "handle_provenance": "RETAINED_QUERY_HANDLE_FROM_COMPLETE_NATIVE_JOB"
            if r is console
            else "ORIGINAL_RETAINED_LAUNCH_HANDLE",
            "lifecycle": {
                "pid": r["pid"],
                "created": r["created"],
                "exited": False,
                "exit_code": 259,
            },
        }
        for r in (worker, adapter, console)
    ]
    packet = {
        "domain": "DISPOSABLE_JOB_ATTRIBUTION_ONLY",
        "stable_complete_native_job": True,
        "native_members_before": [10, 20, 30],
        "native_members_after": [10, 20, 30],
        "records": records,
    }
    return (
        packet,
        worker,
        adapter,
        command,
        (console["image"], console["file_id"], console["sha256"]),
    )


def test_complete_retained_three_member_direct_chain():
    p, w, a, c, pin = attribution()
    assert (
        verify_disposable_adapter_candidate(p, w, a, c, pin, "EXACT-CONSOLE")[
            "console_pid"
        ]
        == 30
    )


@pytest.mark.parametrize(
    "fault",
    [
        "missing_handle",
        "bool_handle",
        "original_handle_missing",
        "parent",
        "command",
        "image",
        "hash",
        "file_id",
        "predates_parent",
        "extra_python",
        "missing_member",
        "unstable",
        "exited",
        "reused_pid",
        "duplicate",
    ],
)
def test_unauthorized_or_incomplete_third_member_refuses(fault):
    p, w, a, c, pin = attribution()
    record = p["records"][2]
    row = record["native"]
    if fault == "missing_handle":
        record["retained_handle"] = 0
    if fault == "bool_handle":
        record["retained_handle"] = True
    if fault == "original_handle_missing":
        p["records"][1]["handle_provenance"] = "PID_ONLY"
    if fault == "parent":
        row["parent_pid"] = 10
    if fault == "command":
        row["command_line"] += " extra"
    if fault == "image":
        row["image"] = "c:\\source\\python.exe"
    if fault == "hash":
        row["sha256"] = "b" * 64
    if fault == "file_id":
        row["file_id"] = (9, 9, 9)
    if fault == "predates_parent":
        row["created"] = 1
    if fault == "extra_python":
        row["image"] = "c:\\source\\python.exe"
        row["command_line"] = a["command_line"]
    if fault == "missing_member":
        p["native_members_before"].append(40)
        p["native_members_after"].append(40)
    if fault == "unstable":
        p["stable_complete_native_job"] = False
    if fault == "exited":
        record["lifecycle"]["exited"] = True
    if fault == "reused_pid":
        record["lifecycle"]["created"] += 1
    if fault == "duplicate":
        p["records"].append(copy.deepcopy(record))
    with pytest.raises(OwnershipRefused):
        verify_disposable_adapter_candidate(p, w, a, c, pin, "EXACT-CONSOLE")


def browser():
    ticket = {
        "schema": "QD_BROWSER_HANDOFF_V3",
        "domain": "DISPOSABLE",
        "cycle": 1,
        "nonce": "a" * 32,
        "host_id": "b" * 32,
        "head": "f" * 64,
        "image": "c:\\source\\python.exe",
        "release": "SYNTHETIC_FIXTURE",
        "url": "http://127.0.0.1:42123/",
        "ready_ns": 10**9,
        "deadline_ns": 46 * 10**9,
    }
    observed = {
        "address_value": "127.0.0.1:42123",
        "document_url": ticket["url"],
        "body": f"ATLAS HARNESS V3 DISPOSABLE FIXTURE Cycle 1 {ticket['host_id']} Selected PAPER account: UNAVAILABLE NO PROVIDERS. NO TRADING. synthetic test evidence",
        "test_tab_closed": True,
    }
    return ticket, observed


def test_both_native_url_and_rendered_fixture_required():
    ticket, obs = browser()
    assert all(verify_disposable_browser_witness(ticket, **obs).values())


@pytest.mark.parametrize(
    "field,value",
    [
        ("address_value", ""),
        ("document_url", ""),
        ("document_url", "http://127.0.0.1:42124/"),
        ("document_url", "https://127.0.0.1:42123/"),
        ("address_value", "example.com"),
        ("body", "unseen page"),
        ("test_tab_closed", False),
        ("test_tab_closed", 1),
    ],
)
def test_missing_conflicting_or_unseen_browser_evidence_refuses(field, value):
    ticket, obs = browser()
    obs[field] = value
    with pytest.raises(ValueError):
        verify_disposable_browser_witness(ticket, **obs)
