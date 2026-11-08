"""Guarded full-table observers and strict socket-then-process cleanup cuts.

No launches, API loads or queries on import. CIM and IP Helper call boundaries
are explicit; the netstat command must use an owned guarded query session.
Reader omission, State 0, unknown ownership and disagreement remain refusals.
Raw evidence is scoped before persistence; no unrelated command lines exported.
"""

import ctypes as C
import ipaddress
import socket
import struct
from ctypes import wintypes as W

from app.services.paper_financial_replay import digest
from scripts.observation_runtime.aip06_harness import SCOPE_HASH, need
from scripts.observation_runtime.aip06_windows_cim import filetime
from scripts.observation_runtime.socket_evidence import native_table, netstat_rows


class CimTables:
    def __init__(self, *, api, allocations, worker, clock_ns):
        self.api, self.allocations, self.worker, self.clock = (
            api,
            allocations,
            worker,
            clock_ns,
        )

    def read(self, *, namespace, query, fields, deadline_ns, maximum=65536):
        need(
            namespace in (r"ROOT\CIMV2", r"ROOT\StandardCimv2")
            and type(query) is str
            and query.startswith("SELECT ")
            and type(fields) is tuple
            and fields
            and type(maximum) is int
            and 1 <= maximum <= 65536,
            "EXACT_READONLY_CIM_TABLE_QUERY",
        )

        def collect():
            held, initialized, enabled = [], False, False

            def owned(name, create, release):
                ticket = self.allocations.reserve("table:" + name, "handle")
                obj = create()
                held.append((ticket, obj, release))
                return obj

            start = self.clock()
            try:
                self.api.initialize()
                initialized = True
                self.api.enable_cancellation()
                enabled = True
                loc = owned("locator", self.api.locator, self.api.release)
                ns = owned("namespace", lambda: self.api.bstr(namespace), self.api.free)
                service = owned(
                    "service", lambda: self.api.connect(loc, ns), self.api.release
                )
                lang = owned("language", lambda: self.api.bstr("WQL"), self.api.free)
                wql = owned("query", lambda: self.api.bstr(query), self.api.free)
                enum = owned(
                    "enumerator",
                    lambda: self.api.query(service, lang, wql),
                    self.api.release,
                )
                rows = []
                while True:
                    remaining = min(1000, (deadline_ns - self.clock()) // 10**6)
                    need(remaining > 0, "CIM_TABLE_DEADLINE")
                    ticket = self.allocations.reserve("table:row", "handle")
                    obj = self.api.next_row(enum, remaining)
                    if obj is None:
                        self.allocations.release(
                            ticket
                        )  # Authoritative empty result; no COM pointer allocated.
                        break
                    try:
                        need(len(rows) < maximum, "CIM_TABLE_CAPACITY")
                        rows.append({f: self.api.property(obj, f) for f in fields})
                    finally:
                        self.api.release(obj)
                        self.allocations.release(ticket)
                need(start <= self.clock() < deadline_ns, "CIM_TABLE_STALE")
                return {
                    "rows": rows,
                    "complete": True,
                    "started_ns": start,
                    "finished_ns": self.clock(),
                    "error": None,
                }
            finally:
                for ticket, obj, release in reversed(held):
                    release(obj)
                    self.allocations.release(ticket)
                if enabled:
                    self.api.disable_cancellation()
                if initialized:
                    self.api.uninitialize()

        return self.worker.run(collect, deadline_ns=deadline_ns, cancel=self.api.cancel)


class TcpTables:
    def __init__(self, dll, *, worker, clock_ns):
        self.get, self.worker, self.clock = dll.GetExtendedTcpTable, worker, clock_ns
        self.get.argtypes = [
            C.c_void_p,
            C.POINTER(W.DWORD),
            W.BOOL,
            W.ULONG,
            C.c_int,
            W.ULONG,
        ]
        self.get.restype = W.DWORD

    def read(self, *, deadline_ns):
        def collect():
            start, rows = self.clock(), []
            for family, af in ((4, socket.AF_INET), (6, socket.AF_INET6)):
                size = W.DWORD()
                need(
                    self.get(None, C.byref(size), False, af, 5, 0) == 122,
                    "IP_HELPER_SIZE_QUERY_INCOMPLETE",
                )
                for _ in range(3):
                    need(
                        self.clock() < deadline_ns and 4 <= size.value <= 8 * 1024**2,
                        "IP_HELPER_CAPACITY_OR_DEADLINE",
                    )
                    raw = C.create_string_buffer(size.value)
                    code = self.get(raw, C.byref(size), False, af, 5, 0)
                    if code != 122:
                        break
                need(
                    code == 0 and 4 <= size.value <= len(raw),
                    "IP_HELPER_TABLE_INCOMPLETE",
                )
                count = struct.unpack_from("<I", raw.raw)[0]
                stride = 24 if family == 4 else 56
                need(
                    count <= 65536 and 4 + count * stride <= size.value,
                    "IP_HELPER_TABLE_TRUNCATED",
                )
                for i in range(count):
                    row = raw.raw[4 + i * stride : 4 + (i + 1) * stride]
                    offset = 8 if family == 4 else 20
                    port = socket.ntohs(
                        struct.unpack_from("<I", row, offset)[0] & 0xFFFF
                    )
                    need(port > 0, "IP_HELPER_UNSUPPORTED_ZERO_LOCAL_PORT")
                    rows += native_table(
                        struct.pack("<I", 1) + row, family=family, port=port
                    )["rows"]
            need(self.clock() < deadline_ns, "IP_HELPER_TABLE_DEADLINE")
            return {
                "rows": rows,
                "complete": True,
                "error": None,
                "started_ns": start,
                "finished_ns": self.clock(),
            }

        return self.worker.run(collect, deadline_ns=deadline_ns)


class GuardedNetstat:
    def __init__(self, guard, argv):
        self.guard, self.argv = guard, tuple(argv)

    def read(self, *, deadline_ns):
        # Exact query source/image/creation/Job/readback checks belong to the
        # existing guarded query path. No subprocess.run/Popen fallback.
        start = self.guard.clock()
        need(start < deadline_ns, "NETSTAT_QUERY_DEADLINE")
        result = self.guard.query(
            self.argv, timeout=min(1, (deadline_ns - start) / 10**9)
        )
        need(
            type(result) is dict
            and set(result) == {"exit_code", "stdout", "stderr", "identity", "closed"}
            and result["exit_code"] == 0
            and result["closed"] is True
            and result["stderr"] == ""
            and type(result["stdout"]) is str
            and len(result["stdout"].encode()) <= 1024**2
            and self.guard.clock() < deadline_ns,
            "NETSTAT_OWNED_QUERY_READBACK_INCOMPLETE",
        )
        text = result["stdout"]
        ports = set()
        for line in text.splitlines():
            bits = line.split()
            if bits and bits[0] == "TCP":
                from scripts.observation_runtime.socket_evidence import endpoint

                need(len(bits) >= 2, "NETSTAT_TRUNCATED_ROW")
                ports.add(endpoint(bits[1])[1])
        rows = []
        for port in sorted(ports):
            need(port > 0, "NETSTAT_UNSUPPORTED_ZERO_PORT")
            rows.extend(netstat_rows(text, port=port)["rows"])
        return {
            "rows": rows,
            "complete": True,
            "error": None,
            "started_ns": start,
            "finished_ns": self.guard.clock(),
        }


class CimSockets:
    FIELDS = (
        "LocalAddress",
        "LocalPort",
        "RemoteAddress",
        "RemotePort",
        "State",
        "OwningProcess",
    )

    def __init__(self, tables):
        self.tables = tables

    def read(self, *, deadline_ns):
        value = self.tables.read(
            namespace=r"ROOT\StandardCimv2",
            query="SELECT " + ",".join(self.FIELDS) + " FROM MSFT_NetTCPConnection",
            fields=self.FIELDS,
            deadline_ns=deadline_ns,
        )
        value["rows"] = [
            {
                "protocol": "TCP",
                "family": ipaddress.ip_address(r["LocalAddress"]).version,
                "local_address": r["LocalAddress"],
                "local_port": r["LocalPort"],
                "remote_address": r["RemoteAddress"],
                "remote_port": r["RemotePort"],
                "state": r["State"],
                "owner_present": r["OwningProcess"] is not None,
                "owner_pid": r["OwningProcess"],
            }
            for r in value["rows"]
        ]
        return value


class ThreeReaderCleanup:
    def __init__(self, *, readers, port, output, clock_ns, endpoints=()):
        need(
            set(readers) == {"CIM", "IP_HELPER", "NETSTAT"},
            "THREE_CONCRETE_SOCKET_READERS_REQUIRED",
        )
        self.readers, self.port, self.output, self.clock = (
            readers,
            port,
            output,
            clock_ns,
        )
        self.endpoints = tuple(endpoints)
        self.failed = False

    def collect(self, *, deadline_ns, started_ns):
        need(
            not self.failed and started_ns <= self.clock() < deadline_ns,
            "SOCKET_CLEANUP_CURRENT_WINDOW",
        )
        self.failed = True
        owned = {r["native"]["pid"] for r in self.port.aggregate.rows.values()}
        cuts, canonical = {}, []
        for name, provider in self.readers.items():
            raw = provider.read(deadline_ns=deadline_ns)
            need(
                type(raw) is dict
                and raw.get("complete") is True
                and raw.get("error") is None
                and type(raw.get("rows")) is list
                and len(raw["rows"]) <= 65536
                and started_ns
                <= raw["started_ns"]
                <= raw["finished_ns"]
                <= self.clock()
                < deadline_ns,
                "SOCKET_READER_INCOMPLETE:" + name,
            )
            scoped = []
            for r in raw["rows"]:
                need(
                    r.get("protocol") == "TCP"
                    and r.get("owner_present") is True
                    and type(r.get("owner_pid")) is int
                    and 0 <= r["owner_pid"] <= 0xFFFFFFFF,
                    "SOCKET_OWNER_ENUMERATION_UNAVAILABLE",
                )
                local, remote = (
                    ipaddress.ip_address(r["local_address"]),
                    ipaddress.ip_address(r["remote_address"]),
                )
                need(
                    r["family"] == local.version == remote.version
                    and type(r["state"]) is int
                    and type(r["local_port"]) is int
                    and 1 <= r["local_port"] <= 65535
                    and type(r["remote_port"]) is int
                    and 0 <= r["remote_port"] <= 65535,
                    "SOCKET_ENDPOINT_OR_FAMILY_CONFLICT",
                )
                relevant = (
                    r["owner_pid"] in owned
                    or (str(local), r["local_port"]) in self.endpoints
                )
                # Unknown owner with an active/unsupported state cannot prove
                # absence of an owned resource. PID-0 TIME_WAIT stays terminal.
                if r["owner_pid"] == 0 and r["state"] not in (1, 11):
                    raise ValueError("AMBIGUOUS_PID_ZERO_OR_STATE_ZERO")
                if relevant:
                    need(1 <= r["state"] <= 12, "SOCKET_STATE_ZERO_OR_UNSUPPORTED")
                    scoped.append(
                        (
                            local.version,
                            str(local),
                            r["local_port"],
                            str(remote),
                            r["remote_port"],
                            r["state"],
                            r["owner_pid"],
                        )
                    )
            scoped.sort()
            need(len(scoped) == len(set(scoped)), "SOCKET_DUPLICATE_ENUMERATION")
            canonical.append(scoped)
            self.output.append(
                {
                    "schema": "AIP06_SCOPED_SOCKET_READER_V1",
                    "reader": name,
                    "started_ns": raw["started_ns"],
                    "finished_ns": raw["finished_ns"],
                    "rows": scoped,
                }
            )
            need(
                all(r[5] in (1, 11) for r in scoped), "OWNED_SOCKET_OR_LISTENER_REMAINS"
            )
            cuts[name] = {
                "complete": True,
                "owned_endpoints": [],
                "unknown": False,
                "started_ns": raw["started_ns"],
                "finished_ns": raw["finished_ns"],
            }
        need(
            canonical[0] == canonical[1] == canonical[2],
            "THREE_READER_SOCKET_DISAGREEMENT",
        )
        now = self.clock()
        need(
            now < deadline_ns
            and all(now - r["started_ns"] <= 2 * 10**9 for r in cuts.values()),
            "SOCKET_EVIDENCE_FRESHNESS",
        )
        self.failed = False
        return {"scope": SCOPE_HASH, "at_ns": now, "readers": cuts}


class StrictProcessCleanup:
    FIELDS = (
        "ProcessId",
        "ParentProcessId",
        "CreationDate",
        "ExecutablePath",
        "CommandLine",
    )

    def __init__(self, *, port, tables, output, clock_ns):
        self.port, self.tables, self.output, self.clock = port, tables, output, clock_ns

    def collect(self, *, after_ns, deadline_ns):
        start = self.clock()
        need(
            after_ns <= start < deadline_ns and self.port.aggregate is not None,
            "STRICT_PROCESS_AFTER_SOCKET_CUT",
        )
        aggregate = self.port.aggregate
        usage = aggregate.observe()
        pids = {aggregate.controller["pid"]} | set(aggregate.rows)
        # The native/ledger limit is eight concurrently owned processes, not
        # eight historical births across all three Stop samples and queries.
        # Preserve the old bounded eight-identity query size and the SAME
        # absolute Stop deadline; never omit old PID/birth observations.
        from scripts.observation_runtime.aip06_harness import LIMITS
        need(len(usage['members']) <= LIMITS['processes']
             and len(pids) <= LIMITS['entries'], "STRICT_PROCESS_DECLARED_CAPACITY")
        cuts, merged = [], {}
        ordered = sorted(pids)
        for offset in range(0,len(ordered),LIMITS['processes']):
            predicate = " OR ".join(f"ProcessId={p} OR ParentProcessId={p}"
                                     for p in ordered[offset:offset+LIMITS['processes']])
            cut = self.tables.read(namespace=r"ROOT\CIMV2",
                query="SELECT " + ",".join(self.FIELDS) + " FROM Win32_Process WHERE " + predicate,
                fields=self.FIELDS,deadline_ns=deadline_ns,maximum=64)
            need(cut['complete'] is True and cut['error'] is None and type(cut['rows']) is list
                 and len(cut['rows']) <= 64 and start <= cut['started_ns'] <= cut['finished_ns']
                 <= self.clock() < deadline_ns,'STRICT_PROCESS_ENUMERATION_INCOMPLETE')
            seen_cut = set()
            for row in cut['rows']:
                pid = row['ProcessId']
                need(type(pid) is int and pid > 4 and pid not in seen_cut,
                     'STRICT_PROCESS_DUPLICATE_OR_INVALID_PID')
                seen_cut.add(pid)
                need(pid not in merged or merged[pid] == row,'STRICT_PROCESS_CONFLICTING_FRESH_CUTS')
                merged[pid] = row
            cuts.append(cut)
        raw = {'complete':True,'error':None,'rows':list(merged.values()),
               'started_ns':start,'finished_ns':self.clock(),'source_cuts':cuts}
        need(
            raw["complete"] is True
            and raw["error"] is None
            and type(raw["rows"]) is list
            and len(raw["rows"]) <= 64
            and start
            <= raw["started_ns"]
            <= raw["finished_ns"]
            <= self.clock()
            < deadline_ns,
            "STRICT_PROCESS_ENUMERATION_INCOMPLETE",
        )
        survivors = []
        controller_seen, seen = False, set()
        for row in raw["rows"]:
            need(
                type(row["ProcessId"]) is int
                and row["ProcessId"] > 4
                and row["ProcessId"] not in seen,
                "STRICT_PROCESS_DUPLICATE_OR_INVALID_PID",
            )
            seen.add(row["ProcessId"])
            if row["ProcessId"] == aggregate.controller["pid"]:
                need(
                    filetime(row["CreationDate"]) // 10
                    == aggregate.controller["created"] // 10
                    and row["CommandLine"] == aggregate.controller["command_line"]
                    and row["ExecutablePath"].casefold()
                    == aggregate.controller["image"].casefold()
                    and row["ParentProcessId"] == aggregate.controller["parent_pid"],
                    "STRICT_CONTROLLER_BIRTH_OR_COMMAND",
                )
                controller_seen = True
                continue
            survivors.append(
                {"pid": row["ProcessId"], "created": filetime(row["CreationDate"])}
            )
        for s in self.port.sessions:
            need(
                s.closed
                and s.binding is not None
                and s.binding.finished
                and self.port.resources_closed(s, s.keys + tuple(s.permit["slots"])),
                "STRICT_RETAINED_PROCESS_OR_HANDLE_NOT_RELEASED",
            )
        need(
            controller_seen
            and usage["members"] == [aggregate.controller["pid"]]
            and not survivors
            and aggregate.observe()["members"] == [aggregate.controller["pid"]]
            and self.clock() < deadline_ns,
            "STRICT_PROCESS_SURVIVOR_OR_JOB_LEAK",
        )
        result = {
            "scope": SCOPE_HASH,
            "started_ns": start,
            "at_ns": self.clock(),
            "survivors": [],
            "unknown": False,
        }
        self.output.append(
            {
                "schema": "AIP06_STRICT_PROCESS_CUT_V1",
                "cut": result,
                "aggregate": usage,
                "source": digest(raw),
            }
        )
        return result
