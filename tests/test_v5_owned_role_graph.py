"""Exercise actual installed-role admission/cleanup with synthetic observations."""

import copy
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.acceptance_harness_v5.ownership import Ownership
from scripts.installed_nonfinancial_launcher import CHILD
from scripts.observation_runtime.launch_ownership import OwnershipRefused

REPO = Path(__file__).resolve().parents[1]


def make(fault="none"):
    scope = json.loads(
        (
            REPO
            / "docs/QD_FINAL_INSTALLED_NONFINANCIAL_ACCEPTANCE_SCOPE_V5_2026-11-03.json"
        ).read_bytes()
    )
    py = scope["ownership"]["images"]["installed_python"]["path"]
    ps = scope["ownership"]["images"]["powershell"]["path"]
    console = scope["ownership"]["images"]["console"]["path"]
    binding = {
        "release": scope["application_release"],
        "head": "a" * 64,
        "support_sha256": scope["support_id"],
        "deployment_sha256": "b" * 64,
        "support_receipt_sha256": scope["support_receipt_sha256"],
        "native_root": scope["baseline"]["native_root"],
        "seconds": 120,
        "requests": 96,
    }
    entry = str(
        Path(scope["support_destination"])
        / "scripts/installed_nonfinancial_launcher.py"
    )
    command = (
        '"'
        + py
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
        + " --seconds 120 --requests 96"
    )

    def row(pid, parent, image, cmd):
        return {
            "pid": pid,
            "created": pid * 1000,
            "image": image.casefold(),
            "command_line": cmd,
            "parent_pid": parent,
            "file_id": (1, 2, 3),
            "sha256": "a" * 64,
        }

    rows = {
        1: row(30, 20, "c:/synthetic/python.exe", "worker"),
        2: row(40, 30, ps, "adapter"),
        3: row(50, 40, py, command),
        4: row(60, 50, py, subprocess.list2cmdline([py, "-I", "-B", "-c", CHILD])),
        5: row(70, 50, console, scope["ownership"]["console_command"]),
        6: row(80, 60, console, scope["ownership"]["console_command"]),
        7: row(90, 40, console, scope["ownership"]["console_command"]),
    }
    jobs = {v["pid"] for v in rows.values()}
    if fault == "command":
        rows[3]["command_line"] += " extra"
    elif fault == "image":
        rows[4]["image"] = "d:/unrelated/python.exe"
    elif fault == "parent":
        rows[4]["parent_pid"] = 40
    elif fault == "creation":
        rows[4]["created"] = 40000
    elif fault == "console_command":
        rows[5]["command_line"] += " extra"
    elif fault == "console_parent":
        rows[5]["parent_pid"] = 20
    elif fault == "console_predates_parent":
        rows[5]["created"] = 1
    elif fault == "unexpected_python":
        rows[8] = row(100, 30, py, "matching source text")
        jobs.add(100)
    elif fault == "duplicate_console":
        rows[8] = row(100, 50, console, scope["ownership"]["console_command"])
        jobs.add(100)
    elif fault == "missing_pid":
        jobs.remove(60)
    owner = object.__new__(Ownership)
    owner.scope = scope
    owner.parent = row(20, 10, ps, "outer-owner")
    owner.worker = copy.deepcopy(rows[1])
    owner.records = {
        "acceptance_worker": (1, copy.deepcopy(rows[1])),
        "control_center_adapter": (2, copy.deepcopy(rows[2])),
    }
    owner.owned_query_handles = []
    owner.host_roles = []
    owner.refused = False
    owner.raw = SimpleNamespace(
        observe=lambda h: copy.deepcopy(rows[h]), members=lambda: jobs.copy()
    )

    def check(value):
        assert value

    class Kernel:
        def DuplicateHandle(
            self, source, original, target, output, access, inherit, flags
        ):
            assert (source, original, access, inherit, flags) == (
                2,
                777,
                0x101000,
                False,
                0,
            )
            output._obj.value = 3
            return True

        def GetCurrentProcess(self):
            return 999

        def OpenProcess(self, access, inherit, pid):
            assert access == 0x101000 and not inherit
            return next(h for h, row in rows.items() if row["pid"] == pid)

        def CloseHandle(self, h):
            return True

    owner.k = Kernel()
    owner.native = SimpleNamespace(check=check)

    def verify():
        assert jobs == {v["pid"] for _, v in owner.records.values()}

    owner.verify = verify
    owner.export = verify
    ready = {
        "controller": {
            "pid": 50,
            "created": 50000,
            "image": py,
            "original_handle": 777,
        },
        "dashboard": {"pid": 60, "created": 60000, "image": py},
    }
    return owner, ready, binding, rows, jobs


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "command",
        "image",
        "parent",
        "creation",
        "console_command",
        "console_parent",
        "console_predates_parent",
        "unexpected_python",
        "duplicate_console",
        "missing_pid",
    ],
)
def test_real_role_assembly_accepts_only_exact_source_graph(fault):
    owner, ready, binding, _rows, _jobs = make(fault)
    if fault == "none":
        owner.ready(ready, binding)
        assert set(owner.records) == {
            "acceptance_worker",
            "control_center_adapter",
            "installed_controller",
            "installed_host",
            "console_50",
            "console_60",
            "console_40",
        }
        assert "console_40" not in owner.host_roles
        assert len(owner.owned_query_handles) == 5
    else:
        with pytest.raises((OwnershipRefused, AssertionError)):
            owner.ready(ready, binding)


@pytest.mark.parametrize(
    "bad_role", ["installed_host", "console_50", "console_60", None]
)
def test_host_retirement_requires_exact_signalled_exit_and_preserves_adapter_console(
    bad_role,
):
    owner, ready, binding, rows, jobs = make()
    owner.ready(ready, binding)

    def lifecycle(handle):
        row = rows[handle]
        role = next(k for k, (h, _) in owner.records.items() if h == handle)
        return {
            "pid": row["pid"],
            "created": row["created"],
            "exited": role != bad_role,
            "exit_code": 109 if role.startswith("console_") else 0,
        }

    owner.raw.lifecycle = lifecycle
    for role in owner.host_roles:
        jobs.remove(owner.records[role][1]["pid"])
    if bad_role is not None:
        with pytest.raises(OwnershipRefused):
            owner.retire_hosts()
        assert "installed_host" in owner.records
    else:
        owner.retire_hosts()
        assert set(owner.records) == {
            "acceptance_worker",
            "control_center_adapter",
            "console_40",
        }
        jobs.remove(40)
        jobs.remove(90)
        owner.controller_closed()
        assert set(owner.records) == {"acceptance_worker"} and jobs == {30}


@pytest.mark.parametrize(
    "fault", ["none", "changed_parent", "changed_worker", "extra_process"]
)
def test_cleanup_only_proof_never_clears_failed_acceptance_latch(monkeypatch, fault):
    owner, _, _, rows, jobs = make()
    owner.parent_handle = 10
    owner.worker_handle = 1
    rows[10] = copy.deepcopy(owner.parent)
    jobs.clear()
    jobs.add(30)
    owner.refused = True
    if fault == "changed_parent":
        rows[10]["created"] += 10
    elif fault == "changed_worker":
        rows[1]["created"] += 10
    elif fault == "extra_process":
        jobs.add(99)
    monkeypatch.setenv("ATLAS_AUTH_HELPER_CLAIMS", "")
    monkeypatch.setenv("ATLAS_V5_RICH_CLAIMS", "")
    if fault == "none":
        owner.cleanup_claims()
        assert owner.refused
        assert {
            v["pid"]
            for v in json.loads(__import__("os").environ["ATLAS_AUTH_HELPER_CLAIMS"])
        } == {20, 30}
    else:
        with pytest.raises(OwnershipRefused):
            owner.cleanup_claims()
