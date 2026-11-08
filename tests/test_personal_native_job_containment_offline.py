"""Offline source contracts for V5 Windows child containment.

No native fixture, subprocess, or Windows Job Object is created here.
"""

import inspect

from personal_native_compatibility_fixture import OwnedChild


def implementation():
    return inspect.getsource(OwnedChild)


def test_job_object_creation_is_required():
    source = implementation()
    assert "CreateJobObject" in source


def test_job_object_kills_owned_tree_on_close():
    source = implementation()
    assert "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" in source
    assert "SetInformationJobObject" in source


def test_child_is_created_suspended_before_assignment():
    source = implementation()
    assert "CREATE_SUSPENDED" in source
    assert "AssignProcessToJobObject" in source
    assert "ResumeThread" in source

    assert (
        source.index("AssignProcessToJobObject")
        < source.index("ResumeThread")
    )


def test_containment_failure_is_explicit():
    source = implementation()
    assert "NATIVE_JOB_CONTAINMENT_REQUIRED" in source


def test_original_process_identity_checks_remain():
    source = implementation()
    assert "observe_handle" in source
    assert "observe_pid" in source
    assert "CHILD_HANDSHAKE" in source
    assert "NO_FOREIGN_TERMINATION" in source


def test_no_broad_process_killing():
    source = implementation()
    assert "taskkill" not in source
    assert "os.kill(" not in source
    assert "subprocess.run(" not in source
