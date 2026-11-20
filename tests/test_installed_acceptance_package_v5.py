"""V5 integration regressions. Operational files are never written or launched."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.acceptance_harness_v5.ownership import RoleView, SessionObserver
from scripts.observation_runtime.installed_acceptance_package_v5 import (
    CONTRACT,
    validate_scope,
)
from scripts.observation_runtime.launch_ownership import OwnershipRefused

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "scripts/acceptance_harness_v5"
SCOPE = (
    REPO / "docs/QD_FINAL_INSTALLED_NONFINANCIAL_ACCEPTANCE_SCOPE_V5_2026-11-03.json"
)


def test_exact_package_reuses_frozen_application_and_reviewed_deadlines():
    scope = json.loads(SCOPE.read_bytes())
    assert validate_scope(scope) == scope
    assert scope["baseline"]["revision"] == 6 and scope["baseline"]["selected"] is None
    assert scope["cycle_limits"]["browser_acknowledgement_seconds"] == 45
    assert scope["cycle_limits"]["complete_stop_seconds"] == 8
    assert scope["ownership"]["contract"] == CONTRACT
    assert scope["approval_status"] == "NOT_AUTHORIZED_FRESH_SINGLE_USE_GRANT_REQUIRED"


@pytest.mark.parametrize(
    "field,value",
    [
        ("worker_topology", "ADOPT_ANY_PYTHON_CHILD"),
        ("outer_owner", "PID_ONLY"),
        ("parent_and_launch_handles", "OPEN_BY_PID_AFTER_EXIT"),
        ("job_handle", "DUPLICATE_INTO_WORKER"),
        ("role_validation", "COMMAND_SUBSTRING"),
        ("query_reply_maximum_age_ms", 501),
        ("query_reply_timeout_seconds", 3),
        ("failed_observation", "RETRY_UNTIL_GREEN"),
        ("console_terminal_code", 1),
        ("unknown_processes", "IGNORE_CONHOST"),
    ],
)
def test_loosened_ownership_contract_refuses(field, value):
    scope = json.loads(SCOPE.read_bytes())
    scope["ownership"]["contract"][field] = value
    with pytest.raises(ValueError):
        validate_scope(scope)


@pytest.mark.parametrize(
    "fault",
    [
        "scope_root",
        "public_path",
        "extra_writer",
        "entry_budget",
        "bytes",
        "seconds",
        "browser",
        "stop",
        "image_path",
        "image_id",
        "image_sha",
        "wrong_shape",
        "extra_image",
        "auto_authorize",
    ],
)
def test_foreign_or_incomplete_package_refuses(fault):
    scope = json.loads(SCOPE.read_bytes())
    if fault == "scope_root":
        scope["evidence_root"] = r"D:\AtlasRuntime"
    elif fault == "public_path":
        scope["public_scope_document"] = "foreign.json"
    elif fault == "extra_writer":
        scope["allowed_mutations"].append(r"D:\AtlasRuntime\financial\new")
    elif fault == "entry_budget":
        scope["limits"]["entries"] = 8193
    elif fault == "bytes":
        scope["limits"]["accounted_bytes"] += 1
    elif fault == "seconds":
        scope["limits"]["seconds"] = 601
    elif fault == "browser":
        scope["cycle_limits"]["browser_acknowledgement_seconds"] = 46
    elif fault == "stop":
        scope["cycle_limits"]["complete_stop_seconds"] = 9
    elif fault == "image_path":
        scope["ownership"]["images"]["observer"]["path"] = "foreign.exe"
    elif fault == "image_id":
        scope["ownership"]["images"]["observer"]["id"] = [True, 0, 1]
    elif fault == "image_sha":
        scope["ownership"]["images"]["observer"]["sha256"] = "bad"
    elif fault == "wrong_shape":
        scope["ownership"]["images"]["observer"].pop("id")
    elif fault == "extra_image":
        scope["ownership"]["images"]["unapproved"] = {}
    elif fault == "auto_authorize":
        scope["approval_status"] = "AUTHORIZED"
    with pytest.raises(ValueError):
        validate_scope(scope)


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "stale",
        "wrong_nonce",
        "wrong_scope",
        "wrong_sequence",
        "boolean_sequence",
        "boolean_time",
        "missing",
        "duplicate",
        "bad_pid",
        "missing_pids",
        "extra_field",
        "parent_gone",
    ],
)
def test_native_job_reply_cannot_substitute_silence_or_stale_claim(
    tmp_path, monkeypatch, fault
):
    parent = 7
    worker = 11
    owner = SimpleNamespace(
        sequence=0,
        session_nonce="a" * 32,
        session_scope="b" * 64,
        root=tmp_path,
        parent_handle=parent,
    )
    native = SimpleNamespace(
        k=SimpleNamespace(
            WaitForSingleObject=lambda *_: 0 if fault == "parent_gone" else 258
        )
    )
    observer = object.__new__(SessionObserver)
    observer.session = owner
    observer.native = native
    original = Path.exists

    def exists(path):
        if path.name == "job-000001.response.json" and not original(path):
            packet = json.loads((tmp_path / "job-000001.request.json").read_bytes())
            data = {
                "seq": packet["seq"],
                "nonce": packet["nonce"],
                "scope_sha256": packet["scope_sha256"],
                "pids": [worker],
                "collected_ns": time.perf_counter_ns(),
            }
            if fault == "stale":
                data["collected_ns"] -= 1_000_000_000
            elif fault == "wrong_nonce":
                data["nonce"] = "c" * 32
            elif fault == "wrong_scope":
                data["scope_sha256"] = "c" * 64
            elif fault == "wrong_sequence":
                data["seq"] = 2
            elif fault == "boolean_sequence":
                data["seq"] = True
            elif fault == "boolean_time":
                data["collected_ns"] = True
            elif fault == "missing":
                data.pop("seq")
            elif fault == "duplicate":
                data["pids"] = [worker, worker]
            elif fault == "bad_pid":
                data["pids"] = [False]
            elif fault == "missing_pids":
                data["pids"] = None
            elif fault == "extra_field":
                data["accepted"] = True
            path.write_text(json.dumps(data))
        return original(path)

    monkeypatch.setattr(Path, "exists", exists)
    if fault == "none":
        assert observer.members() == {worker}
    else:
        with pytest.raises((OwnershipRefused, KeyError)):
            observer.members()


def test_role_view_never_hides_an_unverified_job_member():
    calls = []
    owner = SimpleNamespace(
        worker={"pid": 11}, verify_native=lambda: calls.append("complete"), raw=None
    )
    assert RoleView(owner).members() == {11} and calls == ["complete"]

    def refuse():
        raise OwnershipRefused("UNEXPECTED_REAL_JOB_MEMBER")

    owner.verify_native = refuse
    with pytest.raises(OwnershipRefused):
        RoleView(owner).members()


def test_new_worker_keeps_v4_sequencing_implementation_and_rollback():
    source = (SOURCE / "worker.py").read_text()
    assert (
        "from scripts.observation_runtime.installed_acceptance_sequence import"
        in source
    )
    assert "PreselectionCut" in source and "run_cycle" in source
    assert source.index("ownership.verify()") < source.index(
        "boundary = time.perf_counter_ns()"
    )
    assert "ownership.ready(" in source and "ownership.retire_hosts()" in source
    assert "ownership.controller_closed()" in source
    assert "ownership.cleanup_claims()" in source and "known-head-rollback" in source
    assert "V5_OWNERSHIP_HANDLE_CLEANUP" in source
    old = (REPO / "scripts/acceptance_harness_v3/worker.py").read_text()
    for marker in (
        "/dashboard/perps",
        "/quality_dips.html",
        "all_probe_peer_eof_and_client_handles_closed",
        "cycle == 2",
        "receipt_pin",
        "release-select",
    ):
        assert marker.replace("cycle == 2", "cycle==2") in old
        assert marker in source


def test_source_manifest_and_copies_are_exact_without_claim_or_execution():
    import hashlib

    scope = json.loads(SCOPE.read_bytes())
    root = Path(scope["evidence_root"])
    raw = (root / "source-manifest.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == scope["source_manifest_sha256"]
    manifest = json.loads(raw)
    assert len(manifest["files"]) == scope["source_files"]
    for row in manifest["files"]:
        value = (REPO / row["path"]).read_bytes()
        assert (
            len(value) == row["bytes"]
            and hashlib.sha256(value).hexdigest() == row["sha256"]
        )
    for name in (
        "supervise.ps1",
        "worker.py",
        "ownership.py",
        "gate.py",
        "metadata_preflight.ps1",
        "resource_audit.ps1",
    ):
        assert (root / name).read_bytes() == (SOURCE / name).read_bytes()
    assert not any(
        (root / name).exists()
        for name in (
            "single-use-claim.json",
            "outer-launch.json",
            "supervisor-result.json",
            "worker-result.json",
            "temp",
        )
    )


@pytest.mark.parametrize(
    "name",
    ["worker.py", "native_preflight.py", "clock_preflight.py", "restore_known_head.py"],
)
def test_entries_default_refuse_before_native_or_file_effects(name):
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("ATLAS_AUTH_", "ATLAS_V5_"))
    }
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(SOURCE / name)],
        env=env,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0 and (
        b"NO_NATIVE_ACTION" in result.stderr
        or b"NO_LIVE_EXPLICITLY_APPROVED" in result.stderr
    )


def test_powershell_entry_parses_and_default_refuses_without_native_effect():
    ps = (
        Path(os.environ["SystemRoot"])
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    result = subprocess.run(
        [
            str(ps),
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(SOURCE / "supervise.ps1"),
        ],
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert (
        result.returncode != 0
        and b"FRESH_EXPLICIT_V5_APPROVAL_REQUIRED_NO_NATIVE_ACTION" in result.stderr
    )


def test_original_handles_survive_job_assignment_failure_for_exact_cleanup():
    source = (SOURCE / "supervise.ps1").read_text()
    creation = source.split("function New-OwnedSuspended", 1)[1].split(
        "function Account-Scope", 1
    )[0]
    # Regression: a failed assignment must not lose the only original handle
    # to a suspended process that has not yet entered the owned Job.
    assert creation.index("$script:hp=") < creation.index("AssignProcessToJobObject")
    assert creation.index("$script:ht=") < creation.index("AssignProcessToJobObject")
    assert "-not $assigned" in source and "TerminateProcess($hp,76)" in source
    assert "TerminateProcess($workerId" not in source


def test_scope_verifier_uses_retained_contained_launch_before_worker_handoff():
    source = (SOURCE / "supervise.ps1").read_text()
    assert "$verifier=New-OwnedSuspended $python $verifyCommand" in source
    assert source.index("$verifier=New-OwnedSuspended") < source.index(
        "$launch=New-OwnedSuspended"
    )
    assert "(Creation $hp) -ne $verifier.created" in source
    assert "(Active-JobCount) -ne 0" in source
    assert source.index("$result.scope_verifier=") < source.index(
        "Create-Json 'outer-launch.json'"
    )


def test_disposable_proof_calls_actual_creation_function_without_operational_body():
    source = (REPO / "tests/run_v5_outer_owner_probe.ps1").read_text()
    assert "$launch=New-OwnedSuspended $python $command" in source
    assert "$end=$source.IndexOf('function Account-Scope')" in source
    assert "-approved-installed-worker" not in source
    assert "--disposable-native-owner-probe" in source
