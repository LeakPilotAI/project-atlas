"""Offline capture sequencing; no sockets, processes or installed-state access."""

import copy
import json

import pytest

from scripts.observation_runtime import installed_acceptance_capture as capture

PORT = 42005
NS = 10**9


def row(state=11, pid=0):
    return {
        "protocol": "TCP",
        "family": 4,
        "local_address": "127.0.0.1",
        "local_port": PORT,
        "remote_address": "127.0.0.1",
        "remote_port": 52000,
        "state": state,
        "owner_pid": pid,
        "owner_present": True,
    }


def rig(
    monkeypatch,
    rows=(),
    *,
    cim_error=None,
    native_error=None,
    netstat_error=False,
    non_helpers=0,
    roster_error=False,
    stale=False,
    omit_netstat=False,
    bad_cim=False,
):
    events = []
    native = {
        "started_ns": 11 * NS,
        "finished_ns": 12 * NS,
        "error": native_error,
        "tables": [{"rows": list(rows)}],
    }
    raw_cim = {
        "started_ticks": 13 * NS,
        "finished_ticks": 14 * NS,
        "frequency": NS,
        "rows": [],
        "error": cim_error,
    }
    for r in rows:
        values = {
            "LocalAddress": r["local_address"],
            "LocalPort": r["local_port"],
            "RemoteAddress": r["remote_address"],
            "RemotePort": r["remote_port"],
            "State": r["state"],
            "OwningProcess": r["owner_pid"],
        }
        raw_cim["rows"].append(
            {
                "direct_state": r["state"] + int(bad_cim),
                "direct_owner": r["owner_pid"],
                "properties": [{"name": k, "value": v} for k, v in values.items()],
            }
        )
    snapshot = {
        "schema": "QD_SOCKET_CLEANUP_CIM_V1",
        "protocol": "TCP",
        "query_port": PORT,
        "query_address": "127.0.0.1",
        "started_ticks": 17 * NS,
        "finished_ticks": 18 * NS,
        "frequency": NS,
        "rows": list(rows),
        "error": None,
        "non_helpers": non_helpers,
    }
    if stale:
        snapshot.update(started_ticks=11 * NS, finished_ticks=12 * NS)
    states = {0: "UNKNOWN", 2: "LISTENING", 11: "TIME_WAIT"}
    wire = (
        b""
        if omit_netstat
        else "".join(
            f" TCP 127.0.0.1:{PORT} 127.0.0.1:52000 {states[r['state']]} {r['owner_pid']}\r\n"
            for r in rows
        ).encode()
    )

    def native_read(**kwargs):
        assert kwargs == {"port": PORT}
        events.append("IP_HELPER")
        return copy.deepcopy(native)

    def run(command, label, maximum):
        assert maximum == 5
        if label.endswith("-cim"):
            events.append("CIM")
            return json.dumps(raw_cim).encode()
        if label.endswith("-netstat"):
            events.append("NETSTAT")
            if netstat_error:
                raise RuntimeError("DISPOSABLE_ENUMERATION_FAILURE")
            # Unrelated rows must never enter the scoped evidence artifact.
            return wire + b" TCP 127.0.0.1:99 0.0.0.0:0 LISTENING 123\r\n"
        events.append("PROCESS_ROSTER")
        assert "-OwnedAddress" in command and "-Cycle" not in command
        if roster_error:
            raise RuntimeError("DISPOSABLE_ROSTER_FAILURE")
        return json.dumps(snapshot).encode()

    monkeypatch.setattr(capture, "ip_helper", native_read)
    monkeypatch.setattr(capture.time, "perf_counter_ns", lambda: 19 * NS)
    return events, run


@pytest.mark.parametrize("rows", [[], [row()]])
def test_fresh_unanimous_absence_or_terminal_state_with_process_cut_last(
    tmp_path, monkeypatch, rows
):
    events, run = rig(monkeypatch, rows)
    result = capture.collect(
        repo=tmp_path,
        evidence=tmp_path,
        port=PORT,
        after_ns=10 * NS,
        label="cut",
        run=run,
    )
    assert events == ["IP_HELPER", "CIM", "NETSTAT", "PROCESS_ROSTER"]
    assert result["crosscheck"]["cleanup_clear"]
    assert result["socket_process"]["accepted"]
    assert json.loads((tmp_path / "cut-cleanup.json").read_text()) == json.loads(
        json.dumps(result)
    )
    assert b":99 " not in (tmp_path / "cut-netstat-raw.bin").read_bytes()


@pytest.mark.parametrize(
    "options",
    [
        {"rows": [row(state=2, pid=123)]},
        {"rows": [row(state=2, pid=0)]},
        {"rows": [row(state=0, pid=123)]},
        {"rows": [row()], "omit_netstat": True},
        {"rows": [row()], "bad_cim": True},
        {"cim_error": "CIM_UNAVAILABLE"},
        {"native_error": "IP_HELPER_UNAVAILABLE"},
        {"netstat_error": True},
        {"non_helpers": 1},
        {"stale": True},
    ],
)
def test_incomplete_ambiguous_stale_or_active_evidence_cannot_admit_next_cycle(
    tmp_path, monkeypatch, options
):
    events, run = rig(monkeypatch, **options)
    result = capture.collect(
        repo=tmp_path,
        evidence=tmp_path,
        port=PORT,
        after_ns=10 * NS,
        label="cut",
        run=run,
    )
    assert events == ["IP_HELPER", "CIM", "NETSTAT", "PROCESS_ROSTER"]
    assert not (
        result["crosscheck"]["cleanup_clear"] and result["socket_process"]["accepted"]
    )
    assert (tmp_path / "cut-ip-helper-raw.json").exists()


def test_roster_enumeration_exception_cannot_return_a_clear_result(
    tmp_path, monkeypatch
):
    events, run = rig(monkeypatch, roster_error=True)
    with pytest.raises(RuntimeError, match="DISPOSABLE_ROSTER_FAILURE"):
        capture.collect(
            repo=tmp_path,
            evidence=tmp_path,
            port=PORT,
            after_ns=10 * NS,
            label="cut",
            run=run,
        )
    assert events[-1] == "PROCESS_ROSTER"
    assert not (tmp_path / "cut-cleanup.json").exists()
