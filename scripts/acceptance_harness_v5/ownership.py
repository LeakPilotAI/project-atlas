"""V5 outer-owner handoff and complete retained role roster.

Only called inside an explicitly approved future session. Never discovers an
owner by a command match. Native handles are duplicated from the original
PowerShell CreateProcess owner while the worker is suspended.
"""

import ctypes as C
import hashlib
import json
import os
import subprocess
import time
from ctypes import wintypes as W
from pathlib import Path

from scripts.observation_runtime.launch_ownership import (
    LaunchRequest,
    RetainedLaunchBinding,
    require,
)
from scripts.observation_runtime.launch_ownership_windows import (
    FileInfo,
    NativeQueries,
    WindowsLaunchObserver,
)


class PinnedImage:
    def __init__(self, native, spec):
        self.native, self.handle = native, None
        path = Path(spec["path"]).absolute()
        require(
            all(
                not p.is_symlink() and not p.is_junction()
                for p in (path, *path.parents)
            ),
            "V5_IMAGE_REPARSE",
        )
        h = native.k.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x80, None)
        require(h not in (None, C.c_void_p(-1).value), "V5_IMAGE_READ_LEASE")
        self.handle = h
        try:
            info = FileInfo()
            native.check(native.k.GetFileInformationByHandle(h, C.byref(info)))
            system = Path(os.environ["SystemRoot"])
            linked = {
                str(system / "System32/conhost.exe").casefold(),
                str(
                    system / "System32/WindowsPowerShell/v1.0/powershell.exe"
                ).casefold(),
                str(system / "System32/netstat.exe").casefold(),
            }
            require(
                not info.attrs & 0x400
                and info.links >= 1
                and (info.links == 1 or str(path).casefold() in linked),
                "V5_IMAGE_NAMESPACE",
            )
            self.pin = (
                str(path).casefold(),
                (info.volume, info.index_hi, info.index_lo),
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
            require(
                self.pin
                == (spec["path"].casefold(), tuple(spec["id"]), spec["sha256"]),
                "V5_IMAGE_PIN_DRIFT",
            )
        except Exception:
            self.close()
            raise

    def close(self):
        if self.handle is not None:
            self.native.check(self.native.k.CloseHandle(self.handle))
            self.handle = None


class RoleView:
    """Return one binding's members only AFTER verifying the entire Job."""

    def __init__(self, owner):
        self.owner = owner

    def observe(self, h):
        return self.owner.raw.observe(h)

    def lifecycle(self, h):
        return self.owner.raw.lifecycle(h)

    def members(self):
        self.owner.verify_native()
        return {self.owner.worker["pid"]}


class SessionObserver(WindowsLaunchObserver):
    """Only the original parent owns the Job handle (kill-on-close stays valid)."""

    def members(self):
        owner = self.session
        owner.sequence += 1
        seq = owner.sequence
        started = time.perf_counter_ns()
        name = f"job-{seq:06d}"
        request = {
            "seq": seq,
            "nonce": owner.session_nonce,
            "scope_sha256": owner.session_scope,
            "started_ns": started,
        }
        pending = owner.root / (name + ".request.writing")
        with pending.open("x") as stream:
            json.dump(request, stream)
        pending.rename(owner.root / (name + ".request.json"))
        response = owner.root / (name + ".response.json")
        until = time.perf_counter() + 2
        while not response.exists():
            require(time.perf_counter() < until, "V5_OWNER_JOB_QUERY_TIMEOUT")
            require(
                self.native.k.WaitForSingleObject(owner.parent_handle, 0) == 258,
                "V5_OWNER_PARENT_EXITED",
            )
            time.sleep(0.005)
        require(
            not response.is_symlink()
            and not response.is_junction()
            and response.stat().st_nlink == 1,
            "V5_JOB_REPLY_ALIAS",
        )
        data = json.loads(response.read_bytes())
        now = time.perf_counter_ns()
        require(
            type(data) is dict
            and set(data) == {"seq", "nonce", "scope_sha256", "pids", "collected_ns"}
            and type(data["seq"]) is int
            and type(data["collected_ns"]) is int
            and data["seq"] == seq
            and data["nonce"] == owner.session_nonce
            and data["scope_sha256"] == owner.session_scope
            and type(data["pids"]) is list
            and len(data["pids"]) <= 64
            and all(type(pid) is int and pid > 4 for pid in data["pids"])
            and len(set(data["pids"])) == len(data["pids"])
            and started <= data["collected_ns"] <= now
            and now - data["collected_ns"] <= 500_000_000,
            "V5_INCOMPLETE_OR_STALE_NATIVE_JOB_REPLY",
        )
        require(
            self.native.k.WaitForSingleObject(owner.parent_handle, 0) == 258,
            "V5_OWNER_PARENT_LOST_AFTER_QUERY",
        )
        return set(data["pids"])


class Ownership:
    def __init__(self, root, scope):
        self.root, self.scope = Path(root), scope
        self.native = NativeQueries()
        self.k = self.native.k
        self.k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        self.k.OpenProcess.restype = W.HANDLE
        self.k.DuplicateHandle.argtypes = [
            W.HANDLE,
            W.HANDLE,
            W.HANDLE,
            C.POINTER(W.HANDLE),
            W.DWORD,
            W.BOOL,
            W.DWORD,
        ]
        self.k.DuplicateHandle.restype = W.BOOL
        self.k.GetCurrentProcess.restype = W.HANDLE
        self.images = {}
        self.records = {}
        self.owned_query_handles = []
        self.refused = False
        self.closed = False
        self.host_roles = []
        receipt = json.loads((self.root / "outer-launch.json").read_bytes())
        claim = json.loads((self.root / "single-use-claim.json").read_bytes())
        require(
            receipt["nonce"] == claim["nonce"]
            and receipt["scope_sha256"] == claim["scope_sha256"]
            and receipt["checkpoint"] == claim["approved_checkpoint"]
            and receipt["role"] == "acceptance_worker",
            "V5_OUTER_SESSION_MISMATCH",
        )
        self.parent_handle = receipt["parent_handle"]
        self.worker_handle = receipt["launch_handle"]
        self.session_nonce = claim["nonce"]
        self.session_scope = claim["scope_sha256"]
        self.sequence = 0
        for h in (self.parent_handle, self.worker_handle):
            require(type(h) is int and h > 0, "V5_ORIGINAL_HANDLE_REQUIRED")
        for spec in [
            *scope["ownership"]["images"].values(),
            *scope["ownership"]["diagnostic_images"].values(),
        ]:
            image = PinnedImage(self.native, spec)
            self.images[image.pin[0]] = image
        self.raw = SessionObserver(
            self.native,
            None,
            self.images,
            self.root / "temp",
            deadline_ns=claim["deadline_ns"],
            query_creation_flags=subprocess.CREATE_NO_WINDOW,
        )
        self.raw.session = self
        self.parent = self.raw.observe(self.parent_handle)
        self.worker = self.raw.observe(self.worker_handle)
        require(
            self.worker["pid"] == os.getpid()
            and self.worker["pid"] == receipt["pid"]
            and self.worker["created"] == receipt["created"]
            and self.parent["pid"] == receipt["parent_pid"]
            and self.parent["created"] == receipt["parent_created"]
            and self.parent["command_line"] == receipt["parent_command"],
            "V5_OUTER_PARENT_OR_LAUNCH_MISMATCH",
        )
        self.records["acceptance_worker"] = (self.worker_handle, self.worker)
        pin = self.images[
            scope["ownership"]["images"]["observer"]["path"].casefold()
        ].pin
        request = LaunchRequest(
            "acceptance_worker",
            claim["nonce"],
            "direct",
            pin,
            pin,
            receipt["command"],
            receipt["command"],
        )
        self.binding = RetainedLaunchBinding(
            RoleView(self), request, self.parent_handle, self.worker_handle
        )
        self.binding.bind_runtime(
            self.worker_handle,
            {"pid": os.getpid(), "nonce": claim["nonce"], "role": "acceptance_worker"},
        )
        self.export()

    def verify_native(self):
        require(not self.closed and not self.refused, "V5_OWNERSHIP_LATCHED")
        try:
            require(
                self.native.native(self.parent_handle)
                == tuple(self.parent[k] for k in ("pid", "created", "image"))
                and self.k.WaitForSingleObject(self.parent_handle, 0) == 258,
                "V5_PARENT_LOST",
            )
            for handle, row in self.records.values():
                require(
                    self.native.native(handle)
                    == tuple(row[k] for k in ("pid", "created", "image"))
                    and self.k.WaitForSingleObject(handle, 0) == 258,
                    "V5_ROLE_LIFETIME_CHANGED",
                )
            require(
                self.raw.members() == {row["pid"] for _, row in self.records.values()},
                "V5_INCOMPLETE_OR_UNEXPECTED_JOB_ROSTER",
            )
        except Exception:
            self.refused = True
            raise

    def verify(self):
        self.binding.verify()
        for handle, row in self.records.values():
            require(
                self.raw.observe(handle) == row, "V5_ROLE_COMMAND_OR_ANCESTRY_CHANGED"
            )
        self.verify_native()
        return self.export()

    def export(self):
        self.verify_native()
        rows = [
            {
                k: row[k]
                for k in ("pid", "created", "image", "command_line", "parent_pid")
            }
            for row in [self.parent, *[v for _, v in self.records.values()]]
        ]
        # The unchanged strict CIM guard still receives its exact scalar schema;
        # V5 scripts independently compare the richer command/parent evidence.
        os.environ["ATLAS_AUTH_HELPER_CLAIMS"] = json.dumps(
            [{k: v[k] for k in ("pid", "created", "image")} for v in rows]
        )
        os.environ["ATLAS_V5_RICH_CLAIMS"] = json.dumps(rows)
        return rows

    def register(self, role, handle, image, command, parent_pid, *, owned=False):
        require(role not in self.records, "V5_DUPLICATE_ROLE")
        row = self.raw.observe(handle)
        require(
            all(row["pid"] != other["pid"] for _, other in self.records.values()),
            "V5_DUPLICATE_PROCESS_ROLE",
        )
        parents = [
            v
            for v in [self.parent, *[v for _, v in self.records.values()]]
            if v["pid"] == parent_pid
        ]
        require(
            row["image"] == image.casefold()
            and row["command_line"] == command
            and row["parent_pid"] == parent_pid,
            "V5_ROLE_IMAGE_COMMAND_PARENT_MISMATCH",
        )
        require(
            len(parents) == 1 and row["created"] >= parents[0]["created"],
            "V5_ROLE_PARENT_LIFETIME",
        )
        self.records[role] = (handle, row)
        if owned:
            self.owned_query_handles.append(handle)
        return row

    def controller(self, process, command):
        self.register(
            "control_center_adapter",
            int(process._handle),
            command[0],
            subprocess.list2cmdline(command),
            os.getpid(),
        )
        # The authorized nonfinancial Open is now STARTING, not admitted.
        # Full Job admission occurs only after independently verified READY.

    def ready(self, ready, binding):
        from scripts.installed_nonfinancial_launcher import CHILD

        app = self.scope["application"]["root"]
        python = str(Path(app) / "python/python.exe")
        support = self.scope["support_destination"]
        entry = str(Path(support) / "scripts/installed_nonfinancial_launcher.py")
        # Exact command emitted by the already frozen installed PS adapter.
        command = (
            '"'
            + python
            + '" -I -B "'
            + entry
            + '" --execute-approved-nonfinancial --release '
            + binding["release"]
            + " --expected-head "
            + binding["head"]
            + " --support-sha256 "
            + binding["support_sha256"]
            + " --deployment-sha256 "
            + binding["deployment_sha256"]
            + " --support-receipt-sha256 "
            + binding["support_receipt_sha256"]
            + " --native-root "
            + " ".join(map(str, binding["native_root"]))
            + " --seconds "
            + str(binding["seconds"])
            + " --requests "
            + str(binding["requests"])
        )
        controller_pid = self.records["control_center_adapter"][1]["pid"]
        primary = ready["controller"]
        host = ready["dashboard"]
        for role, claim, cmd, parent in [
            ("installed_controller", primary, command, controller_pid),
            (
                "installed_host",
                host,
                subprocess.list2cmdline([python, "-I", "-B", "-c", CHILD]),
                primary["pid"],
            ),
        ]:
            require(
                type(claim["pid"]) is int and claim["pid"] in self.raw.members(),
                "V5_READY_NOT_IN_OWNED_JOB",
            )
            if role == "installed_controller":
                h = W.HANDLE()
                self.native.check(
                    self.k.DuplicateHandle(
                        self.records["control_center_adapter"][0],
                        claim["original_handle"],
                        self.k.GetCurrentProcess(),
                        C.byref(h),
                        0x101000,
                        False,
                        0,
                    )
                )
                h = h.value
            else:
                h = self.k.OpenProcess(0x101000, False, claim["pid"])
                self.native.check(h)
            # Retain before reading; failed verification never permits adoption.
            self.owned_query_handles.append(h)
            row = self.register(role, h, python, cmd, parent)
            require(
                row["created"] == claim["created"]
                and row["image"] == claim["image"].casefold(),
                "V5_READY_NATIVE_IDENTITY_MISMATCH",
            )
            self.host_roles.append(role)
        # Only the explicitly pinned Windows console role, parented by one of
        # the verified installed roles, may be an additional member. No Python
        # executable or command substring is an ownership exemption.
        remaining = self.raw.members() - {
            row["pid"] for _, row in self.records.values()
        }
        console = self.scope["ownership"]["images"]["console"]["path"]
        for pid in sorted(remaining):
            h = self.k.OpenProcess(0x101000, False, pid)
            self.native.check(h)
            self.owned_query_handles.append(h)
            observed = self.raw.observe(h)
            parents = {
                self.records[k][1]["pid"]: self.records[k][1]
                for k in self.records
                if k
                in ("installed_controller", "installed_host", "control_center_adapter")
            }
            require(
                observed["image"] == console.casefold()
                and observed["parent_pid"] in parents
                and observed["created"] >= parents[observed["parent_pid"]]["created"]
                and observed["command_line"]
                == self.scope["ownership"]["console_command"],
                "V5_UNAPPROVED_READY_DESCENDANT",
            )
            role = "console_" + str(observed["parent_pid"])
            require(role not in self.records, "V5_DUPLICATE_CONSOLE_FOR_PARENT")
            self.records[role] = (h, observed)
            if (
                observed["parent_pid"]
                != self.records["control_center_adapter"][1]["pid"]
            ):
                self.host_roles.append(role)
        self.verify()

    def retire_hosts(self):
        for role in self.host_roles:
            h, row = self.records[role]
            code = 109 if role.startswith("console_") else 0
            require(
                self.raw.lifecycle(h)
                == {
                    "pid": row["pid"],
                    "created": row["created"],
                    "exited": True,
                    "exit_code": code,
                },
                "V5_STOPPED_ROLE_NOT_VERIFIABLY_EXITED",
            )
        for role in self.host_roles:
            h, _ = self.records.pop(role)
            self.native.check(self.k.CloseHandle(h))
            self.owned_query_handles.remove(h)
        self.host_roles = []
        self.export()

    def controller_closed(self):
        _, row = self.records.pop("control_center_adapter")
        console = "console_" + str(row["pid"])
        if console in self.records:
            h, node = self.records[console]
            require(
                self.raw.lifecycle(h)
                == {
                    "pid": node["pid"],
                    "created": node["created"],
                    "exited": True,
                    "exit_code": 109,
                },
                "V5_ADAPTER_CONSOLE_NOT_EXITED",
            )
            self.records.pop(console)
            self.native.check(self.k.CloseHandle(h))
            self.owned_query_handles.remove(h)
        # AcceptanceController already verified exit and closed its ORIGINAL
        # handle. It is never reopened by PID to manufacture a clean result.
        self.export()

    def cleanup_controller(self):
        adapter = self.records.pop("control_center_adapter", None)
        if adapter is not None:
            console = "console_" + str(adapter[1]["pid"])
            if console in self.records:
                self.host_roles.append(console)
        for role in self.host_roles:
            h, row = self.records[role]
            native = self.raw.lifecycle(h)
            require(
                native["pid"] == row["pid"]
                and native["created"] == row["created"]
                and native["exited"],
                "V5_CLEANUP_ROLE_NOT_REAPED",
            )
        self.records = {
            k: v for k, v in self.records.items() if k not in self.host_roles
        }
        self.host_roles = []

    def cleanup_claims(self):
        """Separate cleanup check; never clears the failed acceptance latch."""
        require(
            self.raw.observe(self.parent_handle) == self.parent
            and self.raw.observe(self.worker_handle) == self.worker
            and self.raw.members() == {self.worker["pid"]},
            "V5_CLEANUP_OWNERSHIP_NOT_ESTABLISHED",
        )
        rows = [self.parent, self.worker]
        os.environ["ATLAS_AUTH_HELPER_CLAIMS"] = json.dumps(
            [{k: v[k] for k in ("pid", "created", "image")} for v in rows]
        )
        os.environ["ATLAS_V5_RICH_CLAIMS"] = json.dumps(
            [
                {
                    k: v[k]
                    for k in ("pid", "created", "image", "command_line", "parent_pid")
                }
                for v in rows
            ]
        )

    def close(self):
        errors = []
        for h in list(self.owned_query_handles):
            try:
                self.native.check(self.k.CloseHandle(h))
                self.owned_query_handles.remove(h)
            except OSError as exc:
                errors.append(str(exc))
        for image in self.images.values():
            try:
                image.close()
            except OSError as exc:
                errors.append(str(exc))
        for name in ("parent_handle", "worker_handle"):
            h = getattr(self, name, None)
            if h:
                try:
                    self.native.check(self.k.CloseHandle(h))
                    setattr(self, name, None)
                except OSError as exc:
                    errors.append(str(exc))
        self.closed = not errors
        require(not errors, "V5_HANDLE_CLEANUP_INCOMPLETE:" + repr(errors))
