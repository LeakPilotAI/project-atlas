"""Offline adversarial retained-launch tests. No native APIs/processes."""

import copy
from dataclasses import replace

import pytest

from scripts.observation_runtime.launch_ownership import (
    LaunchRequest,
    OwnershipRefused,
    RetainedLaunchBinding,
)


def row(pid, parent, image="d:/synthetic/python.exe", created=None):
    return {
        "pid": pid,
        "created": created or pid * 1000,
        "image": image,
        "file_id": (1, 2, 3),
        "sha256": "a" * 64,
        "command_line": "exact command",
        "parent_pid": parent,
    }


class Fake:
    def __init__(self, redirect=False):
        self.rows = {
            "parent": row(10, 8),
            "launch": row(20, 10),
            "runtime": row(30, 20, "d:/synthetic/base.exe"),
        }
        self.pids = {20, 30} if redirect else {20}
        self.exit_codes = {}

    def observe(self, h):
        if h not in self.rows or h in self.exit_codes:
            raise OwnershipRefused("HANDLE_OR_LIFETIME_UNAVAILABLE")
        return copy.deepcopy(self.rows[h])

    def members(self):
        return self.pids.copy()

    def lifecycle(self, h):
        value = self.rows[h]
        return {
            "pid": value["pid"],
            "created": value["created"],
            "exited": h in self.exit_codes,
            "exit_code": self.exit_codes.get(h, 259),
        }


def setup(redirect=False):
    api = Fake(redirect)
    pin = lambda v: tuple(v[k] for k in ("image", "file_id", "sha256"))
    req = LaunchRequest(
        "acceptance_supervisor",
        "b" * 32,
        "one_redirector" if redirect else "direct",
        pin(api.rows["launch"]),
        pin(api.rows["runtime"] if redirect else api.rows["launch"]),
        "exact command",
        "exact command",
    )
    ready = {"pid": 30 if redirect else 20, "nonce": req.nonce, "role": req.role}
    return api, req, ready


@pytest.mark.parametrize("redirect", [False, True])
def test_direct_or_explicit_redirector_capability_lives_until_verified_exit(redirect):
    api, req, ready = setup(redirect)
    bound = RetainedLaunchBinding(api, req, "parent", "launch")
    runtime = "runtime" if redirect else "launch"
    claims = bound.bind_runtime(runtime, ready)
    assert {v["pid"] for v in claims} == api.pids
    assert bound.verify() == claims
    api.exit_codes = {"launch": 0, runtime: 0}
    api.pids.clear()
    assert bound.verify_exit() == {
        "normal_exit": True,
        "job_empty": True,
        "handles_still_retained": True,
        "operational_startup_authorized": False,
    }
    with pytest.raises(OwnershipRefused):
        bound.verify()


@pytest.mark.parametrize(
    "fault",
    [
        "parent_handle",
        "launch_handle",
        "command",
        "image",
        "file_id",
        "hash",
        "parent_pid",
        "parent_time",
        "missing_ancestry",
        "pid_type",
        "created_type",
        "missing_image",
        "image_id_missing",
        "forbidden_role",
        "topology",
        "nonce",
        "null_command",
    ],
)
def test_launch_admission_refuses_missing_or_conflicting_evidence(fault):
    api, req, _ = setup()
    parent, launch = "parent", "launch"
    if fault == "parent_handle":
        parent = None
    elif fault == "launch_handle":
        launch = None
    elif fault == "command":
        api.rows["launch"]["command_line"] = "different"
    elif fault == "image":
        api.rows["launch"]["image"] = "d:/foreign/python.exe"
    elif fault == "file_id":
        api.rows["launch"]["file_id"] = (1, 2, 4)
    elif fault == "hash":
        api.rows["launch"]["sha256"] = "c" * 64
    elif fault == "parent_pid":
        api.rows["launch"]["parent_pid"] = 99
    elif fault == "parent_time":
        api.rows["parent"]["created"] = 30000
    elif fault == "missing_ancestry":
        del api.rows["launch"]["parent_pid"]
    elif fault == "pid_type":
        api.rows["launch"]["pid"] = [20]
    elif fault == "created_type":
        api.rows["launch"]["created"] = True
    elif fault == "missing_image":
        del api.rows["launch"]["image"]
    elif fault == "image_id_missing":
        api.rows["launch"]["file_id"] = None
    elif fault == "forbidden_role":
        req = replace(req, role="any_python")
    elif fault == "topology":
        req = replace(req, topology="discover_any_child")
    elif fault == "nonce":
        req = replace(req, nonce="")
    elif fault == "null_command":
        req = replace(req, launch_command="x\0y")
    with pytest.raises(OwnershipRefused):
        RetainedLaunchBinding(api, req, parent, launch)


@pytest.mark.parametrize(
    "fault",
    [
        "missing_handle",
        "unexpected_child",
        "missing_launch",
        "missing_runtime",
        "image",
        "command",
        "parent",
        "created_before_parent",
        "nonce",
        "role",
        "ready_pid",
        "parent_reused",
        "launch_reused",
        "unknown_handle",
        "wrong_topology",
    ],
)
def test_runtime_binding_requires_exact_retained_chain_and_roster(fault):
    api, req, ready = setup(True)
    bound = RetainedLaunchBinding(api, req, "parent", "launch")
    handle = "runtime"
    if fault == "missing_handle":
        handle = None
    elif fault == "unexpected_child":
        api.pids.add(99)
    elif fault == "missing_launch":
        api.pids.remove(20)
    elif fault == "missing_runtime":
        api.pids.remove(30)
    elif fault == "image":
        api.rows[handle]["image"] = "d:/other.exe"
    elif fault == "command":
        api.rows[handle]["command_line"] = "wrong"
    elif fault == "parent":
        api.rows[handle]["parent_pid"] = 10
    elif fault == "created_before_parent":
        api.rows[handle]["created"] = 15000
    elif fault == "nonce":
        ready["nonce"] = "c" * 32
    elif fault == "role":
        ready["role"] = "unexpected_child"
    elif fault == "ready_pid":
        ready["pid"] = 77
    elif fault == "parent_reused":
        api.rows["parent"]["created"] += 10
    elif fault == "launch_reused":
        api.rows["launch"]["created"] += 10
    elif fault == "unknown_handle":
        handle = "json_pid_is_not_a_handle"
    elif fault == "wrong_topology":
        handle = "launch"
    with pytest.raises(OwnershipRefused):
        bound.bind_runtime(handle, ready)
    # A failed observation latches refusal; no later correction retrofits pass.
    api, _, _ = setup(True)
    with pytest.raises(OwnershipRefused):
        bound.verify()


@pytest.mark.parametrize(
    "fault",
    [
        "parent_lost",
        "runtime_lost",
        "launch_lost",
        "parent_reuse",
        "runtime_reuse",
        "command_changed",
        "new_child",
        "exit_early",
        "bad_exit",
        "job_retained",
        "exit_pid_reuse",
    ],
)
def test_active_and_exit_checks_refuse_stale_or_orphaned_lifetimes(fault):
    api, req, ready = setup(True)
    bound = RetainedLaunchBinding(api, req, "parent", "launch")
    bound.bind_runtime("runtime", ready)
    if fault == "parent_lost":
        del api.rows["parent"]
    elif fault == "runtime_lost":
        del api.rows["runtime"]
    elif fault == "launch_lost":
        del api.rows["launch"]
    elif fault == "parent_reuse":
        api.rows["parent"]["created"] += 10
    elif fault == "runtime_reuse":
        api.rows["runtime"]["created"] += 10
    elif fault == "command_changed":
        api.rows["runtime"]["command_line"] += " changed"
    elif fault == "new_child":
        api.pids.add(99)
    elif fault == "exit_early":
        api.exit_codes["runtime"] = 0
    else:
        api.exit_codes = {"launch": 0, "runtime": 0}
        api.pids.clear()
        if fault == "bad_exit":
            api.exit_codes["runtime"] = 1
        elif fault == "job_retained":
            api.pids.add(99)
        elif fault == "exit_pid_reuse":
            api.rows["runtime"]["created"] += 10
        with pytest.raises(OwnershipRefused):
            bound.verify_exit()
        return
    with pytest.raises((OwnershipRefused, KeyError)):
        bound.verify()


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "missing_handle",
        "image",
        "file_id",
        "hash",
        "command",
        "parent",
        "parent_lifetime",
        "extra_process",
        "missing_member",
        "reused_auxiliary",
        "auxiliary_exits_early",
        "auxiliary_exit_code",
        "unrequested_auxiliary",
    ],
)
def test_explicit_auxiliary_has_no_name_or_parent_only_exemption(fault):
    api, req, ready = setup(True)
    api.rows["aux"] = row(40, 30, "c:/synthetic/windows/conhost.exe")
    api.rows["aux"]["command_line"] = "exact auxiliary command"
    pin = tuple(api.rows["aux"][k] for k in ("image", "file_id", "sha256"))
    req = replace(
        req,
        auxiliary_image=pin,
        auxiliary_command="exact auxiliary command",
        auxiliary_exit_code=109,
    )
    api.pids.add(40)
    bound = RetainedLaunchBinding(api, req, "parent", "launch")
    if fault == "unrequested_auxiliary":
        req = replace(
            req, auxiliary_image=None, auxiliary_command=None, auxiliary_exit_code=None
        )
        bound = RetainedLaunchBinding(api, req, "parent", "launch")
    elif fault == "image":
        api.rows["aux"]["image"] = "c:/foreign/conhost.exe"
    elif fault == "file_id":
        api.rows["aux"]["file_id"] = (1, 2, 7)
    elif fault == "hash":
        api.rows["aux"]["sha256"] = "c" * 64
    elif fault == "command":
        api.rows["aux"]["command_line"] += " changed"
    elif fault == "parent":
        api.rows["aux"]["parent_pid"] = 20
    elif fault == "parent_lifetime":
        api.rows["aux"]["created"] = 25000
    elif fault == "extra_process":
        api.pids.add(50)
    elif fault == "missing_member":
        api.pids.remove(40)
    handle = None if fault == "missing_handle" else "aux"
    if fault not in {
        "none",
        "reused_auxiliary",
        "auxiliary_exits_early",
        "auxiliary_exit_code",
    }:
        with pytest.raises(OwnershipRefused):
            bound.bind_runtime("runtime", ready, handle)
        return
    claims = bound.bind_runtime("runtime", ready, handle)
    assert {v["pid"] for v in claims} == {20, 30, 40}
    if fault == "reused_auxiliary":
        api.rows["aux"]["created"] += 10
        with pytest.raises(OwnershipRefused):
            bound.verify()
    elif fault == "auxiliary_exits_early":
        api.exit_codes["aux"] = 0
        with pytest.raises(OwnershipRefused):
            bound.verify()
    else:
        api.exit_codes = {
            "launch": 0,
            "runtime": 0,
            "aux": 1 if fault == "auxiliary_exit_code" else 109,
        }
        api.pids.clear()
        if fault == "auxiliary_exit_code":
            with pytest.raises(OwnershipRefused):
                bound.verify_exit()
        else:
            assert bound.verify_exit()["normal_exit"]


@pytest.mark.parametrize(
    "fault",
    ["direct_aux", "missing_aux_pin", "missing_aux_command", "unbound_aux_command"],
)
def test_auxiliary_declaration_is_explicit(fault):
    _, req, _ = setup(fault != "direct_aux")
    if fault == "unbound_aux_command":
        req = replace(req, auxiliary_command="unbound")
    elif fault == "missing_aux_pin":
        req = replace(req, auxiliary_image=("missing",))
    elif fault == "missing_aux_command":
        req = replace(req, auxiliary_image=req.runtime_image)
    else:
        req = replace(req, auxiliary_image=req.runtime_image, auxiliary_command="aux")
    with pytest.raises(OwnershipRefused):
        req.validate()


@pytest.mark.parametrize(
    "system_linked,links,allowed",
    [(False, 1, True), (False, 2, False), (True, 2, True), (True, 0, False)],
)
def test_readonly_image_lease_keeps_project_and_system_link_rules_distinct(
    tmp_path, monkeypatch, system_linked, links, allowed
):
    from scripts.observation_runtime.launch_ownership_windows import ImageLease

    monkeypatch.setenv("SystemRoot", str(tmp_path))
    path = tmp_path / "System32/conhost.exe"
    path.parent.mkdir()
    path.write_bytes(b"synthetic image bytes only")

    class FileAPI:
        def __init__(self):
            self.k = self
            self.closed = []

        def CreateFileW(self, path, access, share, security, creation, flags, template):
            assert access == 0x80000000 and share == 1 and creation == 3
            return 17

        def GetFileInformationByHandle(self, handle, pointer):
            value = pointer._obj
            value.links = links
            value.volume = 1
            value.index_lo = 2
            return True

        def CloseHandle(self, handle):
            self.closed.append(handle)
            return True

        def check(self, value):
            assert value

    api = FileAPI()
    if allowed:
        lease = ImageLease(api, path, linked_windows_console=system_linked)
        assert lease.pin[1] == (1, 0, 2)
        lease.close()
    else:
        with pytest.raises(OwnershipRefused):
            ImageLease(api, path, linked_windows_console=system_linked)
    assert api.closed == [17]
    with pytest.raises(OwnershipRefused):
        ImageLease(api, tmp_path / "foreign.exe", linked_windows_console=True)
