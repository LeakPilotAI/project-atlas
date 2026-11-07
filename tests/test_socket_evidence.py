"""Offline API/decoding/reconciliation fixtures; never opens a socket."""

import copy
import socket
import struct
from types import SimpleNamespace

import pytest

from scripts.observation_runtime import socket_evidence as evidence
from scripts.observation_runtime.socket_evidence import (
    cim_rows,
    endpoint,
    native_table,
    netstat_rows,
    reconcile,
)


def row(**changes):
    return {
        "protocol": "TCP",
        "family": 4,
        "local_address": "127.0.0.1",
        "local_port": 42005,
        "remote_address": "0.0.0.0",
        "remote_port": 0,
        "state": 2,
        "owner_pid": 1234,
        "owner_present": True,
        **changes,
    }


def native4(state=2, pid=1234, port=42005):
    return struct.pack("<I", 1) + struct.pack(
        "<I4sI4sII",
        state,
        socket.inet_aton("127.0.0.1"),
        socket.htons(port),
        socket.inet_aton("0.0.0.0"),
        0,
        pid,
    )


@pytest.mark.parametrize("state,pid", [(2, 1234), (0, 1234), (2, 0), (11, 0)])
def test_native_ipv4_raw_values_never_normalized_to_a_passing_state(state, pid):
    data = native4(state, pid)
    value = native_table(data, family=4, port=42005)
    assert value["rows"] == [row(state=state, owner_pid=pid)]
    assert bytes.fromhex(value["raw_rows"][0]["row_hex"]) == data[4:]


def test_native_ipv6_layout_and_network_order():
    data = struct.pack("<I", 1) + struct.pack(
        "<16sII16sIIII",
        socket.inet_pton(socket.AF_INET6, "::1"),
        0,
        socket.htons(42005),
        bytes(16),
        0,
        0,
        2,
        4321,
    )
    observed = native_table(data, family=6, port=42005)
    assert observed["row_bytes"] == 56
    assert observed["rows"] == [
        row(family=6, local_address="::1", remote_address="::", owner_pid=4321)
    ]


@pytest.mark.parametrize(
    "data", [b"", b"abc", struct.pack("<I", 999999), native4()[:-1]]
)
def test_native_truncated_or_corrupt_table_refuses(data):
    with pytest.raises(ValueError):
        native_table(data, family=4, port=42005)


def test_native_unrelated_port_is_not_copied_into_evidence():
    assert native_table(native4(port=42006), family=4, port=42005)["raw_rows"] == []


@pytest.mark.parametrize(
    "state,pid", [("LISTENING", 1234), ("LISTENING", 0), ("TIME_WAIT", 0)]
)
def test_netstat_exact_local_endpoint_and_owner_presence(state, pid):
    line = f"  TCP  127.0.0.1:42005  0.0.0.0:0  {state}  {pid}"
    observed = netstat_rows(line, port=42005)
    assert observed["raw_lines"] == [line]
    assert (
        observed["rows"][0]["owner_pid"] == pid
        and observed["rows"][0]["owner_present"] is True
    )


@pytest.mark.parametrize(
    "line",
    [
        "TCP 127.0.0.1:42005 0.0.0.0:0 LISTENING",
        "TCP 127.0.0.1:42005 0.0.0.0:0 UNKNOWN 1234",
        "TCP 127.0.0.1:42005 0.0.0.0:0 LISTENING -1",
    ],
)
def test_netstat_missing_owner_or_unsupported_state_refuses(line):
    with pytest.raises(ValueError):
        netstat_rows(line, port=42005)


def test_netstat_ipv6_and_local_versus_remote_port_identity():
    assert endpoint("[::1]:42005") == ("::1", 42005)
    assert (
        netstat_rows("TCP 127.0.0.1:42006 127.0.0.1:42005 ESTABLISHED 5", port=42005)[
            "rows"
        ]
        == []
    )
    assert (
        netstat_rows("TCP [::1]:42005 [::]:0 LISTENING 5", port=42005)["rows"][0][
            "family"
        ]
        == 6
    )


def bundle(rows=()):
    return [
        {
            "source": source,
            "query_address": "127.0.0.1",
            "query_port": 42005,
            "complete": True,
            "error": None,
            "started_ns": 100,
            "finished_ns": 200,
            "rows": copy.deepcopy(list(rows)),
        }
        for source in ("CIM", "IP_HELPER", "NETSTAT")
    ]


def assess(observed):
    return reconcile(observed, address="127.0.0.1", port=42005, after_ns=50, now_ns=300)


def test_listener_consensus_is_not_cleanup_acceptance():
    observed = assess(bundle([row()]))
    assert observed["agreed"] and not observed["cleanup_clear"]


def test_all_three_confirmed_disappearance_can_clear_sockets_only():
    assert assess(bundle())["cleanup_clear"]


@pytest.mark.parametrize("source", range(3))
@pytest.mark.parametrize(
    "change",
    [
        {"state": 0},
        {"owner_pid": None, "owner_present": False},
        {"owner_pid": 7777},
        {"local_address": "0.0.0.0"},
        {"remote_port": None},
    ],
)
def test_no_passing_reader_can_override_native_cim_owner_or_endpoint_conflict(
    source, change
):
    observed = bundle([row()])
    observed[source]["rows"][0].update(change)
    assert not assess(observed)["cleanup_clear"] and not assess(observed)["agreed"]


def test_pid_zero_listener_remains_blocked_even_with_unanimous_reporting():
    observed = assess(bundle([row(owner_pid=0)]))
    assert (
        observed["agreed"]
        and not observed["cleanup_clear"]
        and "LISTENER_REMAINS_PID_ZERO" in observed["reasons"]
    )


def test_process_exit_is_not_proof_of_socket_disappearance():
    assert not assess(bundle([row(state=5, owner_pid=0)]))["cleanup_clear"]
    assert assess(bundle([row(state=11, owner_pid=0)]))["cleanup_clear"]


@pytest.mark.parametrize(
    "change",
    [
        {"error": "API122"},
        {"complete": False},
        {"started_ns": 1},
        {"finished_ns": 500},
        {"rows": None},
    ],
)
def test_stale_partial_or_failed_enumeration_never_becomes_empty_success(change):
    observed = bundle()
    observed[1].update(change)
    assert not assess(observed)["cleanup_clear"]


def test_different_families_are_not_silently_the_same_endpoint():
    observed = bundle([row()])
    observed[1]["rows"] = [row(family=6, local_address="::1", remote_address="::")]
    assert not assess(observed)["agreed"]


def test_state_transition_disagreement_remains_unresolved():
    observed = bundle([row(state=11, owner_pid=0)])
    observed[2]["rows"] = []
    assert not assess(observed)["cleanup_clear"]


def raw_cim(state=2, pid=1234):
    values = {
        "LocalAddress": "127.0.0.1",
        "LocalPort": 42005,
        "RemoteAddress": "0.0.0.0",
        "RemotePort": 0,
        "State": state,
        "OwningProcess": pid,
    }
    return {
        "error": None,
        "rows": [
            {
                "direct_state": state,
                "direct_owner": pid,
                "properties": [{"name": k, "value": v} for k, v in values.items()],
            }
        ],
    }


@pytest.mark.parametrize("state,pid", [(0, 1234), (2, 0), (2, None)])
def test_cim_raw_zero_and_missing_owner_preserved(state, pid):
    observed = cim_rows(raw_cim(state, pid))[0]
    assert (
        observed["state"] == state
        and observed["owner_pid"] == pid
        and observed["owner_present"] is (pid is not None)
    )


def test_cim_adapter_and_explicit_property_disagreement_is_visible():
    observed = raw_cim()
    observed["rows"][0]["direct_state"] = 0
    with pytest.raises(ValueError, match="DISAGREEMENT"):
        cim_rows(observed)


@pytest.mark.parametrize("source", range(3))
def test_all_sources_must_be_fresh_and_explicitly_complete(source):
    observed = bundle()
    observed[source].pop("error")
    assert not assess(observed)["cleanup_clear"]
    observed = bundle()
    observed[source]["started_ns"] = 1
    assert not assess(observed)["cleanup_clear"]


def test_same_listener_remote_fields_are_not_used_as_a_false_difference():
    observed = bundle([row()])
    observed[1]["rows"][0]["remote_address"] = "127.0.0.1"
    observed[1]["rows"][0]["remote_port"] = 50000
    result = assess(observed)
    assert result["agreed"] and not result["cleanup_clear"]


@pytest.mark.parametrize(
    "field,value", [("source", "CIM"), ("query_port", 42006), ("query_address", "::1")]
)
def test_source_substitution_or_query_binding_changes_refuse(field, value):
    observed = bundle()
    observed[1][field] = value
    assert not assess(observed)["cleanup_clear"]


def test_complete_but_stale_consensus_does_not_authorize_clearance():
    observed = bundle()
    assert not reconcile(
        observed, address="127.0.0.1", port=42005, after_ns=50, now_ns=11 * 10**9
    )["cleanup_clear"]


def test_unknown_state_never_becomes_valid_even_when_every_reader_reports_it():
    result = assess(bundle([row(state=0)]))
    assert not result["agreed"] and not result["cleanup_clear"]


def test_native_wrong_family_and_capacity_have_no_zero_fallback():
    with pytest.raises(ValueError):
        native_table(native4(), family=5, port=42005)
    with pytest.raises(ValueError):
        native_table(native4(), family=4, port=True)


@pytest.mark.parametrize("mode", ["success", "api_error", "bad_size", "growth_limit"])
def test_native_api_errors_sizes_and_bounded_growth_are_retained(monkeypatch, mode):
    class Get:
        def __call__(self, buffer, size, ordered, af, table_class, reserved):
            assert table_class == 5 and reserved == 0 and not ordered
            if buffer is None:
                size._obj.value = 9 * 1024**2 if mode == "bad_size" else 64
                return 122
            if mode == "api_error":
                return 5
            if mode == "growth_limit":
                return 122
            data = native4(state=0) if af == socket.AF_INET else struct.pack("<I", 0)
            evidence.ctypes.memmove(buffer, data, len(data))
            size._obj.value = len(data)
            return 0

    monkeypatch.setattr(evidence, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(
        evidence.ctypes,
        "WinDLL",
        lambda *a: SimpleNamespace(GetExtendedTcpTable=Get()),
        raising=False,
    )
    observed = evidence.ip_helper(port=42005)
    if mode == "success":
        assert (
            observed["error"] is None and observed["tables"][0]["rows"][0]["state"] == 0
        )
        assert [call["code"] for call in observed["calls"]] == [122, 0, 122, 0]
    else:
        assert observed["error"] is not None
        if mode == "api_error":
            assert observed["calls"][-1]["code"] == 5
        if mode == "growth_limit":
            assert len(observed["calls"]) == 4
