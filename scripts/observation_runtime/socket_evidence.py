"""Read-only socket evidence decoding/cross-checks; grants no launch authority."""

import ctypes
import ipaddress
import os
import socket
import struct
import time

STATES = {
    "CLOSED": 1,
    "LISTENING": 2,
    "SYN_SENT": 3,
    "SYN_RECEIVED": 4,
    "ESTABLISHED": 5,
    "FIN_WAIT_1": 6,
    "FIN_WAIT_2": 7,
    "CLOSE_WAIT": 8,
    "CLOSING": 9,
    "LAST_ACK": 10,
    "TIME_WAIT": 11,
    "DELETE_TCB": 12,
}


def native_table(data, *, family, port):
    """SDK DWORD header + 24-byte IPv4 / 56-byte IPv6 OWNER_PID rows.

    Keep scoped row bytes before decoding; never persist unrelated endpoints.
    Ports are network byte order in the low WORD of the SDK DWORD.
    """
    stride = {4: 24, 6: 56}.get(family)
    if (
        stride is None
        or type(port) is not int
        or not 1 <= port <= 65535
        or len(data) < 4
    ):
        raise ValueError("NATIVE_TABLE_HEADER_OR_FAMILY")
    count = struct.unpack_from("<I", data)[0]
    if count > 65536 or len(data) < 4 + count * stride:
        raise ValueError("NATIVE_TABLE_TRUNCATED_OR_CAPACITY")
    rows, raw = [], []
    for index in range(count):
        entry = data[4 + index * stride : 4 + (index + 1) * stride]
        if family == 4:
            state, _local, lp, _remote, rp, pid = struct.unpack("<6I", entry)
            local, remote = (
                socket.inet_ntop(socket.AF_INET, entry[4:8]),
                socket.inet_ntop(socket.AF_INET, entry[12:16]),
            )
        else:
            la, ls, lp, ra, rs, rp, state, pid = struct.unpack("<16sII16sIIII", entry)
            local, remote = (
                socket.inet_ntop(socket.AF_INET6, la),
                socket.inet_ntop(socket.AF_INET6, ra),
            )
            if ls:
                local += "%" + str(socket.ntohl(ls))
            if rs:
                remote += "%" + str(socket.ntohl(rs))
        local_port = socket.ntohs(lp & 0xFFFF)
        if local_port != port:
            continue
        raw.append({"index": index, "row_hex": entry.hex(), "family": family})
        rows.append(
            {
                "protocol": "TCP",
                "family": family,
                "local_address": local,
                "local_port": local_port,
                "remote_address": remote,
                "remote_port": socket.ntohs(rp & 0xFFFF),
                "state": state,
                "owner_present": True,
                "owner_pid": pid,
            }
        )
    return {"table_count": count, "row_bytes": stride, "raw_rows": raw, "rows": rows}


def ip_helper(*, port):
    """Native Windows read only; no socket creation, closure or state mutation."""
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("EXACT_NATIVE_QUERY_PORT_REQUIRED")
    if os.name != "nt":
        raise OSError("WINDOWS_IP_HELPER_REQUIRED")
    get = ctypes.WinDLL("iphlpapi").GetExtendedTcpTable
    dword = ctypes.c_uint32
    get.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(dword),
        ctypes.c_int,
        dword,
        ctypes.c_int,
        dword,
    ]
    get.restype = dword
    result = {
        "started_ns": time.perf_counter_ns(),
        "calls": [],
        "tables": [],
        "error": None,
    }
    try:
        for family, af in ((4, socket.AF_INET), (6, socket.AF_INET6)):
            size = dword(0)
            code = get(None, ctypes.byref(size), False, af, 5, 0)  # OWNER_PID_ALL
            result["calls"].append({"family": family, "code": code, "size": size.value})
            if code != 122:
                raise OSError(code, "IP_HELPER_SIZE_QUERY")
            for _ in range(3):  # Bounded table growth, not a network retry.
                if not 4 <= size.value <= 8 * 1024**2:
                    raise ValueError("IP_HELPER_BUFFER_LIMIT")
                buffer = ctypes.create_string_buffer(size.value)
                code = get(buffer, ctypes.byref(size), False, af, 5, 0)
                result["calls"].append(
                    {"family": family, "code": code, "size": size.value}
                )
                if code != 122:
                    break
            if code:
                raise OSError(code, "IP_HELPER_ENUMERATION")
            result["tables"].append(
                native_table(buffer.raw[: size.value], family=family, port=port)
            )
    except (OSError, ValueError) as exc:
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
    result["finished_ns"] = time.perf_counter_ns()
    return result


def endpoint(text):
    address, separator, raw_port = text.rpartition(":")
    if not separator or not raw_port.isascii() or not raw_port.isdecimal():
        raise ValueError("NETSTAT_ENDPOINT_FORMAT")
    address = str(ipaddress.ip_address(address.strip("[]")))
    port = int(raw_port)
    if not 0 <= port <= 65535:
        raise ValueError("NETSTAT_PORT_RANGE")
    return address, port


def netstat_rows(text, *, port):
    """Parse only scoped TCP rows; unknown/localized states remain errors."""
    raw, rows = [], []
    for line in text.splitlines():
        fields = line.split()
        if not fields or fields[0] != "TCP":
            continue
        if len(fields) < 2:
            raise ValueError("NETSTAT_TRUNCATED_TCP_ROW")
        local, lp = endpoint(fields[1])
        if lp != port:
            continue
        raw.append(line)
        if len(fields) != 5:
            raise ValueError("NETSTAT_SCOPED_ROW_INCOMPLETE")
        remote, rp = endpoint(fields[2])
        if (
            fields[3] not in STATES
            or not fields[4].isascii()
            or not fields[4].isdecimal()
        ):
            raise ValueError("NETSTAT_STATE_OR_OWNER_UNVERIFIED")
        pid = int(fields[4])
        if pid > 0xFFFFFFFF:
            raise ValueError("NETSTAT_OWNER_RANGE")
        rows.append(
            {
                "protocol": "TCP",
                "family": ipaddress.ip_address(local).version,
                "local_address": local,
                "local_port": lp,
                "remote_address": remote,
                "remote_port": rp,
                "state": STATES[fields[3]],
                "owner_present": True,
                "owner_pid": pid,
            }
        )
    return {"raw_lines": raw, "rows": rows}


def cim_rows(raw):
    """Preserve direct-versus-explicit-property differences as a refusal."""
    if raw.get("error") is not None or type(raw.get("rows")) is not list:
        raise ValueError("CIM_ENUMERATION_FAILED")
    result = []
    required = {
        "LocalAddress",
        "LocalPort",
        "RemoteAddress",
        "RemotePort",
        "State",
        "OwningProcess",
    }
    for row in raw["rows"]:
        properties = row["properties"]
        if {p["name"] for p in properties} != required or len(properties) != 6:
            raise ValueError("CIM_PROPERTIES_MISSING_OR_DUPLICATE")
        values = {p["name"]: p["value"] for p in properties}
        if (
            type(row["direct_state"]) is not type(values["State"])
            or type(row["direct_owner"]) is not type(values["OwningProcess"])
            or row["direct_state"] != values["State"]
            or row["direct_owner"] != values["OwningProcess"]
        ):
            raise ValueError("CIM_DIRECT_AND_EXPLICIT_PROPERTY_DISAGREEMENT")
        result.append(
            {
                "protocol": "TCP",
                "family": ipaddress.ip_address(values["LocalAddress"]).version,
                "local_address": values["LocalAddress"],
                "local_port": values["LocalPort"],
                "remote_address": values["RemoteAddress"],
                "remote_port": values["RemotePort"],
                "state": values["State"],
                "owner_present": values["OwningProcess"] is not None,
                "owner_pid": values["OwningProcess"],
            }
        )
    return result


def reconcile(observations, *, address, port, after_ns, now_ns=None):
    """Unanimous usable evidence only. No source wins by merely passing.

    This is an observation result, not process-ownership or startup authority.
    A listener's remote fields have no TCP identity meaning; preserve raw fields
    but compare its local identity, state and owner. Other states compare both
    endpoints. Unknown state/owner/query/age always refuses clearance.
    """
    now_ns = time.perf_counter_ns() if now_ns is None else now_ns
    result = {"agreed": False, "cleanup_clear": False, "reasons": [], "rows": {}}
    try:
        target = ipaddress.ip_address(address)
        if not target.is_loopback or type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("EXACT_LOOPBACK_TARGET_REQUIRED")
        if (
            type(after_ns) is not int
            or type(now_ns) is not int
            or not 0 < after_ns <= now_ns
        ):
            raise ValueError("MONOTONIC_BOUNDARY_REQUIRED")
        if (
            type(observations) is not list
            or len(observations) != 3
            or {o["source"] for o in observations} != {"CIM", "IP_HELPER", "NETSTAT"}
        ):
            raise ValueError("THREE_DISTINCT_SOURCES_REQUIRED")
        cuts = []
        for observed in observations:
            required = {
                "source",
                "error",
                "complete",
                "query_port",
                "query_address",
                "started_ns",
                "finished_ns",
                "rows",
            }
            if (
                not required <= observed.keys()
                or observed.get("error") is not None
                or observed.get("complete") is not True
                or type(observed.get("query_port")) is not int
                or observed.get("query_port") != port
                or observed.get("query_address") != address
            ):
                raise ValueError("SOURCE_ENUMERATION_INCOMPLETE")
            start, end = observed["started_ns"], observed["finished_ns"]
            if (
                type(start) is not int
                or type(end) is not int
                or not after_ns <= start <= end <= now_ns
                or now_ns - start > 10 * 10**9
                or end - start > 5 * 10**9
            ):
                raise ValueError("SOURCE_OBSERVATION_STALE_OR_PREBOUNDARY")
            if type(observed["rows"]) is not list or len(observed["rows"]) > 1024:
                raise ValueError("SOURCE_ROW_TYPE_OR_CAPACITY")
            canonical = []
            for row in observed["rows"]:
                local, remote = (
                    ipaddress.ip_address(row["local_address"]),
                    ipaddress.ip_address(row["remote_address"]),
                )
                if (
                    row["protocol"] != "TCP"
                    or row["family"] != local.version
                    or remote.version != local.version
                    or type(row["local_port"]) is not int
                    or row["local_port"] != port
                    or type(row["remote_port"]) is not int
                    or not 0 <= row["remote_port"] <= 65535
                    or type(row["state"]) is not int
                    or not 1 <= row["state"] <= 12
                    or row["owner_present"] is not True
                    or type(row["owner_pid"]) is not int
                    or not 0 <= row["owner_pid"] <= 0xFFFFFFFF
                ):
                    raise ValueError("SOURCE_STATE_OWNER_OR_ENDPOINT_UNVERIFIED")
                overlap = local == target or (
                    local.version == target.version and local.is_unspecified
                )
                overlap |= (
                    local.version == 6
                    and target.version == 4
                    and (local.is_unspecified or local.ipv4_mapped == target)
                )
                if overlap:
                    canonical.append(
                        (
                            local.version,
                            str(local),
                            port,
                            row["state"],
                            row["owner_pid"],
                            "" if row["state"] == 2 else str(remote),
                            0 if row["state"] == 2 else row["remote_port"],
                        )
                    )
            if len(canonical) != len(set(canonical)):
                raise ValueError("DUPLICATE_SOURCE_ROWS")
            canonical.sort()
            result["rows"][observed["source"]] = canonical
            cuts.append(canonical)
        if cuts[0] != cuts[1] or cuts[0] != cuts[2]:
            raise ValueError("CROSS_SOURCE_DISAGREEMENT")
        result["agreed"] = True
        for row in cuts[0]:
            if row[3] == 2:
                result["reasons"].append(
                    "LISTENER_REMAINS_PID_ZERO" if row[4] == 0 else "LISTENER_REMAINS"
                )
            elif row[3] not in (1, 11):
                result["reasons"].append("ACTIVE_SOCKET_REMAINS")
        result["cleanup_clear"] = not result["reasons"]
    except (ValueError, KeyError, TypeError) as exc:
        result["reasons"].append(str(exc))
    return result
