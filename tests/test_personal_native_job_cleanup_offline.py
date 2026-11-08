"""Advanced offline cleanup contracts for V5 containment.

No Windows processes or Job Objects are created.
"""

import pytest

from scripts.observation_runtime.personal_native_job import (
    ContainedChild,
    launch_contained_child,
)


class FakeAPI:
    def __init__(self, fail=None):
        self.fail = fail
        self.events = []
        self.handles = set()

    def record(self, event):
        self.events.append(event)
        if self.fail == event:
            raise RuntimeError(event)

    def create_job(self):
        self.record("create_job")
        self.handles.add("job")
        return "job"

    def configure_kill_on_close(self, job):
        self.record("configure_job")

    def create_suspended_child(self, command):
        self.record("create_child")
        self.handles.update(("process", "thread"))
        return "process", "thread"

    def assign_child(self, job, process):
        self.record("assign_child")

    def resume_child(self, thread):
        self.record("resume_child")

    def terminate_job(self, job):
        self.record("terminate_job")

    def close_handle(self, handle):
        self.events.append("close_" + handle)
        if self.fail == "close_" + handle:
            raise RuntimeError("close_" + handle)
        self.handles.discard(handle)


def test_successful_close_releases_handles():
    api = FakeAPI()
    child = launch_contained_child(api, ["mock"])
    child.close()
    assert not api.handles


def test_close_is_idempotent():
    api = FakeAPI()
    child = launch_contained_child(api, ["mock"])
    child.close()
    count = len(api.events)
    child.close()
    assert len(api.events) == count


def test_process_close_failure_still_attempts_job_close():
    api = FakeAPI(fail="close_process")
    child = launch_contained_child(api, ["mock"])
    with pytest.raises(RuntimeError):
        child.close()
    assert "close_job" in api.events


def test_job_close_failure_is_reported():
    api = FakeAPI(fail="close_job")
    child = launch_contained_child(api, ["mock"])
    with pytest.raises(RuntimeError):
        child.close()


def test_assignment_failure_attempts_termination():
    api = FakeAPI(fail="assign_child")
    with pytest.raises(
        RuntimeError,
        match="NATIVE_JOB_CONTAINMENT_REQUIRED",
    ):
        launch_contained_child(api, ["mock"])
    assert "terminate_job" in api.events


def test_failed_termination_is_not_silent():
    api = FakeAPI()
    original = api.assign_child

    def fail_assignment(job, process):
        api.fail = "terminate_job"
        raise RuntimeError("assignment_failed")

    api.assign_child = fail_assignment

    with pytest.raises(RuntimeError) as error:
        launch_contained_child(api, ["mock"])

    assert "terminate_job" in str(error.value)


def test_thread_close_failure_is_reported():
    api = FakeAPI(fail="close_thread")

    with pytest.raises(
        RuntimeError,
        match="NATIVE_JOB_CONTAINMENT_REQUIRED",
    ) as error:
        launch_contained_child(api, ["mock"])

    assert "close_thread" in str(error.value)
    assert "close_job" in api.events
    assert "close_process" in api.events
    assert "thread" in api.handles


def test_unrelated_handle_is_never_closed():
    api = FakeAPI()
    api.handles.add("genesis_unrelated")
    child = launch_contained_child(api, ["mock"])
    child.close()
    assert api.handles == {"genesis_unrelated"}
    assert "close_genesis_unrelated" not in api.events
