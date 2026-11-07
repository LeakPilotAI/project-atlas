import copy

import pytest

from tests.v6_http_diagnostic import verify_http_diagnostic_listener


def packet():
    row = {
        "protocol": "TCP",
        "family": 4,
        "local_address": "127.0.0.1",
        "local_port": 45678,
        "remote_address": "0.0.0.0",
        "remote_port": 0,
        "state": 2,
        "owner_present": True,
        "owner_pid": 123,
    }
    return {
        "observations": [
            {
                "source": s,
                "query_address": "127.0.0.1",
                "query_port": 45678,
                "started_ns": 100,
                "finished_ns": 200,
                "complete": True,
                "error": None,
                "rows": [copy.deepcopy(row)],
            }
            for s in ("CIM", "NETSTAT", "IP_HELPER")
        ],
        "crosscheck": {"cleanup_clear": False},
    }


def test_unsupported_cim_does_not_become_accepted_cleanup_or_browser_authority():
    p = packet()
    p["observations"][0]["rows"][0]["state"] = 0
    result = verify_http_diagnostic_listener(
        p, port=45678, pid=123, after_ns=1, now_ns=300
    )
    assert result["owned_fixture_http_get_only"]
    assert (
        not result["three_reader_acceptance"]
        and not result["financial_or_browser_authority"]
    )


@pytest.mark.parametrize(
    "fault",
    [
        "owner",
        "state_zero",
        "address",
        "port",
        "error",
        "stale",
        "missing",
        "duplicate",
    ],
)
def test_missing_or_contradictory_native_listener_refuses(fault):
    p = packet()
    frame = p["observations"][1]
    if fault == "owner":
        frame["rows"][0]["owner_pid"] = 456
    if fault == "state_zero":
        frame["rows"][0]["state"] = 0
    if fault == "address":
        frame["rows"][0]["local_address"] = "0.0.0.0"
    if fault == "port":
        frame["rows"][0]["local_port"] += 1
    if fault == "error":
        frame["error"] = "query failed"
    if fault == "stale":
        frame["started_ns"] = 0
    if fault == "missing":
        p["observations"].pop()
    if fault == "duplicate":
        p["observations"][2]["source"] = "NETSTAT"
    with pytest.raises(ValueError):
        verify_http_diagnostic_listener(p, port=45678, pid=123, after_ns=1, now_ns=300)
