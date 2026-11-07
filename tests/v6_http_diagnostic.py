"""Read-only HTTP probe readiness; never substitutes for three-reader cleanup."""


def verify_http_diagnostic_listener(packet, *, port, pid, after_ns, now_ns):
    if (
        type(port) is not int
        or type(pid) is not int
        or not 0 < port < 65536
        or pid <= 4
    ):
        raise ValueError("EXACT_DIAGNOSTIC_ENDPOINT_OWNER_REQUIRED")
    frames = packet.get("observations")
    if (
        type(frames) is not list
        or len(frames) != 3
        or {r.get("source") for r in frames} != {"CIM", "NETSTAT", "IP_HELPER"}
    ):
        raise ValueError("COMPLETE_RAW_DIAGNOSTIC_REQUIRED")
    # CIM's unsupported State 0 remains a recorded refusal. Two independent
    # native observations authorize only a harmless GET to this owned fixture.
    for source in ("NETSTAT", "IP_HELPER"):
        frame = next(r for r in frames if r["source"] == source)
        start, end = frame.get("started_ns"), frame.get("finished_ns")
        if (
            frame.get("complete") is not True
            or frame.get("error") is not None
            or frame.get("query_address") != "127.0.0.1"
            or frame.get("query_port") != port
            or type(start) is not int
            or type(end) is not int
            or not after_ns <= start <= end <= now_ns
            or now_ns - start > 10**10
            or end - start > 5 * 10**9
        ):
            raise ValueError("INDEPENDENT_LISTENER_OBSERVATION_REQUIRED")
        rows = frame.get("rows")
        if type(rows) is not list or len(rows) != 1:
            raise ValueError("EXACT_SINGLE_OWNED_LISTENER_REQUIRED")
        row = rows[0]
        expected = {
            "protocol": "TCP",
            "family": 4,
            "local_address": "127.0.0.1",
            "local_port": port,
            "remote_address": "0.0.0.0",
            "remote_port": 0,
            "state": 2,
            "owner_present": True,
            "owner_pid": pid,
        }
        if row != expected:
            raise ValueError("NATIVE_LISTENER_ENDPOINT_STATE_OR_OWNER_MISMATCH")
    return {
        "owned_fixture_http_get_only": True,
        "native_ip_helper_and_netstat_listening": True,
        "three_reader_acceptance": packet.get("crosscheck", {}).get("cleanup_clear")
        is True,
        "financial_or_browser_authority": False,
    }
