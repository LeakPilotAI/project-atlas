"""Offline tests for failed native cleanup operations."""

import pytest

from scripts.observation_runtime.personal_native_job import (
    launch_contained_child,
)


class FailingCleanupAPI:
    def __init__(self):
        self.events = []
        self.job = object()
        self.process = object()
        self.thread = object()

    def create_job(self):
        self.events.append("create_job")
        return self.job

    def configure_kill_on_close(self, job):
        self.events.append("configure_job")

    def create_suspended_child(self, command):
        self.events.append("create_child")
        return self.process, self.thread

    def assign_child(self, job, process):
        self.events.append("assign_child")
        raise RuntimeError("ASSIGNMENT_FAILED")

    def resume_child(self, thread):
        self.events.append("resume_child")

    def terminate_process(self, process):
        self.events.append("terminate_process")
        raise RuntimeError("TERMINATION_FAILED")

    def terminate_job(self, job):
        self.events.append("terminate_job")

    def close_handle(self, handle):
        if handle is self.thread:
            self.events.append("close_thread")
        elif handle is self.process:
            self.events.append("close_process")
        elif handle is self.job:
            self.events.append("close_job")


def test_termination_failure_is_reported():
    api = FailingCleanupAPI()

    with pytest.raises(
        RuntimeError,
        match="CLEANUP_INCOMPLETE",
    ):
        launch_contained_child(api, ["mock-python.exe"])


def test_termination_failure_does_not_resume_child():
    api = FailingCleanupAPI()

    with pytest.raises(RuntimeError):
        launch_contained_child(api, ["mock-python.exe"])

    assert "resume_child" not in api.events


def test_termination_failure_attempts_job_cleanup():
    api = FailingCleanupAPI()

    with pytest.raises(RuntimeError):
        launch_contained_child(api, ["mock-python.exe"])

    assert "terminate_job" in api.events


def test_termination_failure_attempts_handle_cleanup():
    api = FailingCleanupAPI()

    with pytest.raises(RuntimeError):
        launch_contained_child(api, ["mock-python.exe"])

    assert "close_thread" in api.events
    assert "close_process" not in api.events
    assert "close_job" in api.events
