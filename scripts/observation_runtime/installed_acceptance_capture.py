"""Read-only capture assembly for the explicitly approved acceptance harness."""

import json
import re
import time
from pathlib import Path

from scripts.observation_runtime.installed_acceptance_cleanup import socket_cleanup
from scripts.observation_runtime.socket_evidence import (
    cim_rows,
    ip_helper,
    netstat_rows,
    reconcile,
)


def collect(*, repo, evidence, port, after_ns, label, run):
    repo, evidence = Path(repo), Path(evidence)
    ps = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    frames = []
    for source in ("IP_HELPER", "CIM", "NETSTAT"):
        before = time.perf_counter_ns()
        frame = {
            "source": source,
            "query_address": "127.0.0.1",
            "query_port": port,
            "complete": False,
            "error": None,
            "rows": [],
            "started_ns": before,
        }
        try:
            if source == "IP_HELPER":
                raw = ip_helper(port=port)
                (evidence / (label + "-ip-helper-raw.json")).write_text(
                    json.dumps(raw, indent=2)
                )
                frame.update(
                    started_ns=raw["started_ns"], finished_ns=raw["finished_ns"]
                )
                if raw["error"] is not None:
                    raise ValueError("IP_HELPER_QUERY_FAILED")
                frame["rows"] = [
                    row for table in raw["tables"] for row in table["rows"]
                ]
            elif source == "CIM":
                data = run(
                    [
                        ps,
                        "-NoProfile",
                        "-NonInteractive",
                        "-File",
                        str(repo / "scripts/windows/Atlas-Socket-Raw-Crosscheck.ps1"),
                        "-Port",
                        str(port),
                    ],
                    label + "-cim",
                    5,
                )
                (evidence / (label + "-cim-raw.json")).write_bytes(data)
                raw = json.loads(data)
                frame.update(
                    started_ns=raw["started_ticks"] * 10**9 // raw["frequency"],
                    finished_ns=raw["finished_ticks"] * 10**9 // raw["frequency"],
                )
                frame["rows"] = cim_rows(raw)
            else:
                data = run(
                    [r"C:\Windows\System32\netstat.exe", "-ano", "-p", "TCP"],
                    label + "-netstat",
                    5,
                )
                scoped = []
                for line in data.splitlines(keepends=True):
                    match = re.match(rb"^\s*TCP\s+(\S+)\s+", line)
                    if (
                        match
                        and match.group(1).rsplit(b":", 1)[-1] == str(port).encode()
                    ):
                        scoped.append(line)
                raw = b"".join(scoped)
                (evidence / (label + "-netstat-raw.bin")).write_bytes(raw)
                frame["rows"] = netstat_rows(raw.decode("ascii"), port=port)["rows"]
                frame["finished_ns"] = time.perf_counter_ns()
            frame["complete"] = True
        except (ValueError, KeyError, TypeError, OSError, RuntimeError) as exc:
            frame["error"] = {"type": type(exc).__name__, "message": str(exc)}
            frame.setdefault("finished_ns", time.perf_counter_ns())
        frames.append(frame)
    # Refresh the stricter process/CIM cut last. Do not extend either age limit.
    data = run(
        [
            ps,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(repo / "scripts/windows/Atlas-Acceptance-Resource-Audit.ps1"),
            "-OwnedPort",
            str(port),
            "-OwnedAddress",
            "127.0.0.1",
        ],
        label + "-roster",
        5,
    )
    (evidence / (label + "-roster-raw.json")).write_bytes(data)
    snapshot = json.loads(data)
    now = time.perf_counter_ns()
    result = {
        "observations": frames,
        "snapshot": snapshot,
        "finished_ns": now,
        "crosscheck": reconcile(
            frames, address="127.0.0.1", port=port, after_ns=after_ns, now_ns=now
        ),
        "socket_process": socket_cleanup(
            snapshot, address="127.0.0.1", port=port, stopped_ns=after_ns, now_ns=now
        ),
    }
    (evidence / (label + "-cleanup.json")).write_text(json.dumps(result, indent=2))
    return result
