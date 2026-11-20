"""Offline behavioral contracts for V5 Windows Job containment.

The helper is not implemented yet. These tests define its required API.
No real Windows processes or Job Objects are created.
"""

import pytest


class FakeWindowsAPI:
    def __init__(self, fail=None):
        self.fail = fail
        self.events = []
        self.handles = set()

    def record(self, operation):
        self.events.append(operation)
        if self.fail == operation:
            raise RuntimeError(operation)

    def create_job(self):
        self.record("create_job")
        self.handles.add("job")
        return "job"

    def configure_kill_on_close(self, job):
        self.record("configure_job")

    def create_suspended_child(self, command):
        self.record("create_suspended_child")
        self.handles.update(("process", "thread"))
        return "process", "thread"

    def assign_child(self, job, process):
        self.record("assign_child")

    def resume_child(self, thread):
        self.record("resume_child")

    def terminate_process(self, process):
        self.record("terminate_process")

    def terminate_job(self, job):
        self.record("terminate_job")

    def close_handle(self, handle):
        self.events.append("close_" + handle)
        self.handles.discard(handle)


def launch(api):
    from scripts.observation_runtime.personal_native_job import (
        launch_contained_child,
    )
    return launch_contained_child(api, ["python", "-B", "child.py"])


def test_successful_containment_order():
    api = FakeWindowsAPI()
    result = launch(api)
    assert result is not None
    assert api.events[:5] == [
        "create_job",
        "configure_job",
        "create_suspended_child",
        "assign_child",
        "resume_child",
    ]


@pytest.mark.parametrize(
    "failure",
    [
        "create_job",
        "configure_job",
        "create_suspended_child",
        "assign_child",
        "resume_child",
    ],
)
def test_failure_is_explicit(failure):
    api = FakeWindowsAPI(fail=failure)
    with pytest.raises(RuntimeError, match="NATIVE_JOB_CONTAINMENT_REQUIRED"):
        launch(api)


@pytest.mark.parametrize(
    "failure",
    [
        "configure_job",
        "create_suspended_child",
        "assign_child",
        "resume_child",
    ],
)
def test_failure_closes_owned_handles(failure):
    api = FakeWindowsAPI(fail=failure)
    with pytest.raises(RuntimeError, match="NATIVE_JOB_CONTAINMENT_REQUIRED"):
        launch(api)
    assert not api.handles


def test_assignment_failure_never_resumes_child():
    api = FakeWindowsAPI(fail="assign_child")
    with pytest.raises(RuntimeError, match="NATIVE_JOB_CONTAINMENT_REQUIRED"):
        launch(api)
    assert "resume_child" not in api.events


def test_configuration_failure_never_creates_child():
    api = FakeWindowsAPI(fail="configure_job")
    with pytest.raises(RuntimeError, match="NATIVE_JOB_CONTAINMENT_REQUIRED"):
        launch(api)
    assert "create_suspended_child" not in api.events
