"""Read-only retained Job evidence. Capture never admits a role by itself."""

import subprocess

from scripts.observation_runtime.launch_ownership import require


def inspect_adapter_job(owner, process, command):
    """Keep query handles alive through classification and native exit readback."""
    before = owner.raw.members()
    retained = {}
    packet = {
        "domain": "DISPOSABLE_JOB_ATTRIBUTION_ONLY",
        "native_members_before": sorted(before),
        "expected_roles": {role: row for role, (_, row) in owner.records.items()},
        "original_parent": owner.parent,
        "launch_command": subprocess.list2cmdline(command),
        "original_launch_pid": process.pid,
        "records": [],
        "admitted": False,
    }
    try:
        for pid in sorted(before):
            existing = [
                (role, h)
                for role, (h, row) in owner.records.items()
                if row["pid"] == pid
            ]
            if existing:
                require(len(existing) == 1, "ATTRIBUTION_DUPLICATE_ROLE")
                role, handle = existing[0]
                provenance = "ORIGINAL_RETAINED_LAUNCH_HANDLE"
            else:
                role = "UNCLAIMED"
                handle = owner.k.OpenProcess(0x101000, False, pid)
                owner.native.check(handle)
                retained[pid] = handle
                provenance = "RETAINED_QUERY_HANDLE_FROM_COMPLETE_NATIVE_JOB"
            row = owner.raw.observe(handle)
            require(row["pid"] == pid, "ATTRIBUTION_HANDLE_PID_MISMATCH")
            packet["records"].append(
                {
                    "declared_role": role,
                    "handle_provenance": provenance,
                    "retained_handle": int(handle),
                    "native": row,
                    "lifecycle": owner.raw.lifecycle(handle),
                }
            )
        packet["native_members_after"] = sorted(owner.raw.members())
        require(
            packet["native_members_after"] == packet["native_members_before"],
            "ATTRIBUTION_JOB_CHANGED_DURING_CAPTURE",
        )
        packet["stable_complete_native_job"] = True
        return packet, retained
    except Exception:
        for h in retained.values():
            owner.native.check(owner.k.CloseHandle(h))
        raise


def verify_disposable_adapter_candidate(
    packet, worker, adapter, command, console_pin, console_command
):
    """Exact existing optional-console contract, NOT a new generic allowlist."""
    require(
        packet.get("domain") == "DISPOSABLE_JOB_ATTRIBUTION_ONLY"
        and packet.get("stable_complete_native_job") is True,
        "COMPLETE_STABLE_ATTRIBUTION_REQUIRED",
    )
    rows = [record["native"] for record in packet["records"]]
    require(len({row["pid"] for row in rows}) == len(rows), "ATTRIBUTION_DUPLICATE_PID")
    require(
        {row["pid"] for row in rows}
        == set(packet["native_members_before"])
        == set(packet["native_members_after"]),
        "ATTRIBUTION_MEMBER_SET_MISMATCH",
    )
    by_pid = {row["pid"]: row for row in rows}
    require(
        by_pid.get(worker["pid"]) == worker and by_pid.get(adapter["pid"]) == adapter,
        "ORIGINAL_WORKER_ADAPTER_OBSERVATIONS_REQUIRED",
    )
    require(
        adapter["parent_pid"] == worker["pid"]
        and adapter["created"] >= worker["created"]
        and adapter["command_line"] == subprocess.list2cmdline(command),
        "EXACT_ORIGINAL_ADAPTER_LAUNCH_REQUIRED",
    )
    for record in packet["records"]:
        row = record["native"]
        require(
            type(record["retained_handle"]) is int and record["retained_handle"] > 0,
            "ATTRIBUTION_RETAINED_HANDLE_REQUIRED",
        )
        require(
            record["lifecycle"]
            == {
                "pid": row["pid"],
                "created": row["created"],
                "exited": False,
                "exit_code": 259,
            },
            "LIVE_ATTRIBUTION_LIFECYCLE_REQUIRED",
        )
        if row["pid"] in (worker["pid"], adapter["pid"]):
            require(
                record["handle_provenance"] == "ORIGINAL_RETAINED_LAUNCH_HANDLE",
                "ORIGINAL_HANDLE_PROVENANCE_REQUIRED",
            )
    extra = [row for row in rows if row["pid"] not in (worker["pid"], adapter["pid"])]
    require(len(extra) <= 1, "UNAPPROVED_ADDITIONAL_JOB_MEMBERS")
    if not extra:
        return {"topology": "DIRECT_ADAPTER", "console_pid": None}
    row = extra[0]
    record = next(
        record for record in packet["records"] if record["native"]["pid"] == row["pid"]
    )
    require(
        record["handle_provenance"] == "RETAINED_QUERY_HANDLE_FROM_COMPLETE_NATIVE_JOB",
        "RETAINED_CONSOLE_QUERY_HANDLE_REQUIRED",
    )
    require(
        (row["image"], row["file_id"], row["sha256"]) == console_pin,
        "PINNED_CONSOLE_EXECUTABLE_REQUIRED",
    )
    require(
        row["command_line"] == console_command
        and row["parent_pid"] == adapter["pid"]
        and row["created"] >= adapter["created"],
        "EXACT_CONSOLE_COMMAND_PARENT_LIFETIME_REQUIRED",
    )
    return {
        "topology": "DIRECT_ADAPTER_WITH_VERIFIED_WINDOWS_CONSOLE",
        "console_pid": row["pid"],
    }


def admit_disposable_adapter_console(owner, packet, handles, command):
    """Only the prospectively proven direct console role; no PID adoption."""
    require(
        owner.scope.get("domain") == "DISPOSABLE_INTEGRATED_ONLY",
        "DISPOSABLE_ADAPTER_ONLY",
    )
    require(
        type(owner.scope["ownership"].get("direct_adapter_console_exit_code")) is int
        and owner.scope["ownership"]["direct_adapter_console_exit_code"] == 0,
        "EXPLICIT_DIRECT_CONSOLE_TERMINAL_REQUIRED",
    )
    adapter = owner.records["control_center_adapter"][1]
    spec = owner.scope["ownership"]["images"]["console"]
    candidate = verify_disposable_adapter_candidate(
        packet,
        owner.worker,
        adapter,
        command,
        (spec["path"].casefold(), tuple(spec["id"]), spec["sha256"]),
        owner.scope["ownership"]["console_command"],
    )
    pid = candidate["console_pid"]
    if pid is not None:
        require(pid in handles, "ORIGINAL_ATTRIBUTION_HANDLE_REQUIRED")
        row = next(
            record["native"]
            for record in packet["records"]
            if record["native"]["pid"] == pid
        )
        require(
            owner.raw.observe(handles[pid]) == row,
            "CONSOLE_IDENTITY_CHANGED_BEFORE_ADMISSION",
        )
        role = "console_" + str(adapter["pid"])
        require(role not in owner.records, "DUPLICATE_ADAPTER_CONSOLE_ROLE")
        owner.records[role] = (handles[pid], row)
        owner.owned_query_handles.append(handles.pop(pid))
    owner.verify()
    return candidate


def retire_disposable_adapter(owner):
    """Called inside the original <=8-second final Stop/drain timing."""
    require(
        owner.scope.get("domain") == "DISPOSABLE_INTEGRATED_ONLY",
        "DISPOSABLE_ADAPTER_ONLY",
    )
    _, adapter = owner.records["control_center_adapter"]
    role = "console_" + str(adapter["pid"])
    if role in owner.records:
        h, row = owner.records[role]
        require(
            owner.k.WaitForSingleObject(h, 500) == 0, "DIRECT_CONSOLE_EXIT_UNRESOLVED"
        )
        require(
            owner.raw.lifecycle(h)
            == {
                "pid": row["pid"],
                "created": row["created"],
                "exited": True,
                "exit_code": 0,
            },
            "DIRECT_CONSOLE_TERMINAL_IDENTITY_REQUIRED",
        )
        owner.native.check(owner.k.CloseHandle(h))
        owner.owned_query_handles.remove(h)
        owner.records.pop(role)
    owner.records.pop("control_center_adapter")
    # AcceptanceController already verified/closed the original launch handle.
    owner.export()
