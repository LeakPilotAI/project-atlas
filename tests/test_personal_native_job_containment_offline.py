"""Offline source contracts for the current selected R15 Windows Job lifecycle.

The older OwnedChild fixture retains handle/handshake checks, while the
actual suspended Job admission now lives in personal_native_job, its
Win32 adapter, and the R15 parked-owner creator. No native launch here.
"""
import inspect

from personal_native_compatibility_fixture import OwnedChild
from scripts.observation_runtime import atlas_r15_parked_writer_owner as parked
from scripts.observation_runtime.personal_native_job import launch_contained_child
from scripts.observation_runtime.personal_native_windows_api import WindowsJobAPI


def implementation():
    return inspect.getsource(OwnedChild)


def owner_source():
    return inspect.getsource(launch_contained_child)


def adapter_method(name):
    return inspect.getsource(getattr(WindowsJobAPI, name))


def test_job_object_creation_is_required():
    assert "api.create_job()" in owner_source()
    assert "CreateJobObjectW" in adapter_method("create_job")


def test_job_object_kills_owned_tree_on_close():
    owner = owner_source()
    assert "api.configure_kill_on_close(job)" in owner
    assert owner.index("api.configure_kill_on_close(job)") < owner.index(
        "api.create_suspended_child(command)")
    policy = adapter_method("configure_kill_on_close")
    assert "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" in policy
    assert "SetInformationJobObject" in policy


def test_child_is_created_suspended_before_assignment():
    owner = owner_source()
    assert "api.create_suspended_child(command)" in owner
    assert "api.assign_child(job, process)" in owner
    assert "api.resume_child(thread)" in owner
    assert (owner.index("api.create_suspended_child(command)")
            < owner.index("api.assign_child(job, process)")
            < owner.index("api.resume_child(thread)"))
    assert "AssignProcessToJobObject" in adapter_method("assign_child")
    assert "ResumeThread" in adapter_method("resume_child")
    # The actual selected R15 caller uses CreateProcessW explicitly suspended
    # and below normal priority, not a fallback Popen or shell-created worker.
    creator = inspect.getsource(parked.inspect)
    assert "CREATE_SUSPENDED|DETACHED_PROCESS|BELOW_NORMAL_PRIORITY_CLASS" in creator
    assert "CreateProcessW" in creator


def test_containment_failure_is_explicit():
    assert "NATIVE_JOB_CONTAINMENT_REQUIRED" in owner_source()
    assert "FailedAdmissionCleanup" in owner_source()
    assert "terminate_process" in inspect.getsource(
        __import__(
            "scripts.observation_runtime.personal_native_job",
            fromlist=["FailedAdmissionCleanup"]).FailedAdmissionCleanup.close)


def test_original_process_identity_checks_remain():
    source = implementation()
    assert "observe_handle" in source
    assert "observe_pid" in source
    assert "CHILD_HANDSHAKE" in source
    assert "NO_FOREIGN_TERMINATION" in source


def test_no_broad_process_killing():
    sources = (implementation(), owner_source(),
               adapter_method("create_job"), adapter_method("assign_child"),
               adapter_method("resume_child"))
    for source in sources:
        assert "taskkill" not in source
        assert "os.kill(" not in source
        assert "subprocess.run(" not in source
