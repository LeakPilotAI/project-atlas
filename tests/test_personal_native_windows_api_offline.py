"""Offline tests for Windows Job Object API wrappers.

Uses fake kernel32 functions. Never invokes Windows process APIs.
"""

import pytest

from scripts.observation_runtime.personal_native_windows_api import (
    WindowsJobAPI,
)


class FakeKernel32:
    def __init__(self):
        self.calls = []
        self.assign_result = True
        self.resume_result = 1
        self.terminate_result = True

    def AssignProcessToJobObject(self, job, process):
        self.calls.append(("assign", job, process))
        return self.assign_result

    def ResumeThread(self, thread):
        self.calls.append(("resume", thread))
        return self.resume_result

    def TerminateJobObject(self, job, exit_code):
        self.calls.append(("terminate", job, exit_code))
        return self.terminate_result


@pytest.fixture
def api():
    # Bypass __init__ to avoid loading or calling real kernel32.
    instance = object.__new__(WindowsJobAPI)
    instance.kernel32 = FakeKernel32()
    return instance


def test_assign_calls_correct_api(api):
    api.assign_child(101, 202)
    assert api.kernel32.calls == [("assign", 101, 202)]


@pytest.mark.parametrize("job,process", [
    (0, 202),
    (101, 0),
    (None, 202),
    (101, None),
])
def test_assign_rejects_invalid_handles(api, job, process):
    with pytest.raises(RuntimeError, match="NATIVE_JOB_INVALID_HANDLE"):
        api.assign_child(job, process)
    assert api.kernel32.calls == []


def test_assign_failure_propagates(api):
    api.kernel32.assign_result = False
    with pytest.raises(OSError):
        api.assign_child(101, 202)


def test_resume_calls_correct_api(api):
    assert api.resume_child(303) == 1
    assert api.kernel32.calls == [("resume", 303)]


def test_resume_failure_propagates(api):
    api.kernel32.resume_result = 0xFFFFFFFF
    with pytest.raises(OSError):
        api.resume_child(303)


def test_resume_rejects_invalid_handle(api):
    with pytest.raises(RuntimeError, match="NATIVE_THREAD_INVALID_HANDLE"):
        api.resume_child(0)
    assert api.kernel32.calls == []


def test_terminate_calls_correct_api(api):
    api.terminate_job(404)
    assert api.kernel32.calls == [("terminate", 404, 1)]


def test_terminate_rejects_invalid_handle(api):
    with pytest.raises(RuntimeError, match="NATIVE_JOB_INVALID_HANDLE"):
        api.terminate_job(None)
    assert api.kernel32.calls == []


def test_terminate_failure_propagates(api):
    api.kernel32.terminate_result = False
    with pytest.raises(OSError):
        api.terminate_job(404)


def test_process_creation_remains_blocked(api):
    with pytest.raises(
        RuntimeError,
        match="NATIVE_CHILD_LAUNCH_BLOCKED_PENDING_V5_INTEGRATION",
    ):
        api.create_suspended_child(["python", "-V"])

    assert api.kernel32.calls == []
