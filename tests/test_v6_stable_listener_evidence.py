import copy

import pytest

from scripts.observation_runtime.socket_evidence import reconcile
from tests.v6_stable_listener_evidence import verify_stable_interval


def fixture():
    before = {
        "pid": 123,
        "created": 123456,
        "image": "c:/source/python.exe",
        "socket": 42,
        "family": 4,
        "address": "127.0.0.1",
        "port": 45678,
        "acceptconn": 1,
        "closed": False,
        "observed_ns": 100,
    }
    after = dict(before, observed_ns=500)
    rows = [
        {
            "source": s,
            "started_ns": 200,
            "finished_ns": 300,
            "query_port": 45678,
            "query_address": "127.0.0.1",
        }
        for s in ("CIM", "NETSTAT", "IP_HELPER")
    ]
    return before, after, rows


def test_stable_native_socket_does_not_reclassify_unknown_table_states():
    result = verify_stable_interval(*fixture())
    assert result["stable_socket_lifetime"]
    assert (
        not result["tcp_state_mapping_changed"]
        and not result["three_reader_gate_overridden"]
    )


@pytest.mark.parametrize(
    "fault",
    [
        "pid_reuse",
        "handle",
        "port",
        "family",
        "address",
        "not_listening",
        "bool_listen",
        "closed",
        "early_reader",
        "late_reader",
        "missing_reader",
    ],
)
def test_changed_socket_or_uncovered_interval_refuses(fault):
    before, after, rows = copy.deepcopy(fixture())
    if fault == "pid_reuse":
        after["created"] += 1
    if fault == "handle":
        after["socket"] += 1
    if fault == "port":
        after["port"] += 1
    if fault == "family":
        before["family"] = after["family"] = 6
    if fault == "address":
        before["address"] = after["address"] = "0.0.0.0"
    if fault == "not_listening":
        after["acceptconn"] = 0
    if fault == "bool_listen":
        after["acceptconn"] = True
    if fault == "closed":
        after["closed"] = True
    if fault == "early_reader":
        rows[0]["started_ns"] = 99
    if fault == "late_reader":
        rows[0]["finished_ns"] = 501
    if fault == "missing_reader":
        rows.pop()
    with pytest.raises(ValueError):
        verify_stable_interval(before, after, rows)


@pytest.mark.parametrize("fault", ["both_native_zero", "cim_zero", "netstat_omits"])
def test_socket_listen_proof_never_overrides_reader_refusal(fault):
    before, after, observations = fixture()
    for observation in observations:
        observation.update(
            complete=True,
            error=None,
            rows=[
                {
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
            ],
        )
    observations[0]["rows"][0]["state"] = 0 if fault != "netstat_omits" else 2
    if fault == "both_native_zero":
        observations[2]["rows"][0]["state"] = 0
    if fault != "cim_zero":
        observations[1]["rows"] = []
    assert verify_stable_interval(before, after, observations)["stable_socket_lifetime"]
    actual = reconcile(
        observations, address="127.0.0.1", port=45678, after_ns=100, now_ns=500
    )
    assert not actual["agreed"] and not actual["cleanup_clear"]
