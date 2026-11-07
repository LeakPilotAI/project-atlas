"""Stable socket lifetime evidence never replaces any TCP-table reader."""


def verify_stable_interval(before, after, observations):
    identity = ("pid", "created", "image", "socket", "family", "address", "port")
    if any(before.get(k) != after.get(k) for k in identity):
        raise ValueError("RETAINED_SOCKET_OR_NATIVE_PROCESS_CHANGED")
    if (
        before.get("family") != 4
        or before.get("address") != "127.0.0.1"
        or type(before.get("socket")) is not int
        or before["socket"] < 0
        or any(
            type(w.get("acceptconn")) is not int
            or w["acceptconn"] != 1
            or w.get("closed") is not False
            for w in (before, after)
        )
    ):
        raise ValueError("ACTUAL_CONTINUOUS_LISTEN_SOCKET_REQUIRED")
    if (
        type(observations) is not list
        or len(observations) != 3
        or {o.get("source") for o in observations} != {"CIM", "NETSTAT", "IP_HELPER"}
    ):
        raise ValueError("ALL_THREE_READERS_STILL_REQUIRED")
    for observation in observations:
        start, end = observation.get("started_ns"), observation.get("finished_ns")
        if (
            type(start) is not int
            or type(end) is not int
            or not before["observed_ns"] <= start <= end <= after["observed_ns"]
            or observation.get("query_port") != before["port"]
            or observation.get("query_address") != before["address"]
        ):
            raise ValueError("READER_OUTSIDE_STABLE_LISTENER_INTERVAL")
    return {
        "stable_socket_lifetime": True,
        "tcp_state_mapping_changed": False,
        "three_reader_gate_overridden": False,
        "browser_or_financial_authority": False,
    }
