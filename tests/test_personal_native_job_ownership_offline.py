"""Offline handle-ownership and cleanup-retry tests.

No Windows processes or Job Objects are created.
"""

import pytest

from scripts.observation_runtime.personal_native_job import (
    ContainedChild,
)


class FakeAPI:
    def __init__(self):
        self.handles = {"job", "process"}
        self.events = []
        self.failures = set()

    def terminate_job(self, job):
        self.events.append(("terminate_job", job))

    def close_handle(self, handle):
        self.events.append(("close", handle))

        if handle in self.failures:
            raise RuntimeError(f"close_failed:{handle}")

        self.handles.discard(handle)


def test_successful_close_releases_ownership():
    api = FakeAPI()
    child = ContainedChild(api, "job", "process")

    child.close()

    assert child.closed
    assert child.job is None
    assert child.process is None
    assert not api.handles


def test_failed_process_close_preserves_process_reference():
    api = FakeAPI()
    api.failures.add("process")

    child = ContainedChild(api, "job", "process")

    with pytest.raises(RuntimeError):
        child.close()

    assert child.process == "process"
    assert child.job is None
    assert not child.closed


def test_failed_job_close_preserves_job_reference():
    api = FakeAPI()
    api.failures.add("job")

    child = ContainedChild(api, "job", "process")

    with pytest.raises(RuntimeError):
        child.close()

    assert child.job == "job"
    assert child.process is None
    assert not child.closed


def test_retry_releases_previously_failed_handle():
    api = FakeAPI()
    api.failures.add("process")

    child = ContainedChild(api, "job", "process")

    with pytest.raises(RuntimeError):
        child.close()

    api.failures.clear()

    child.close()

    assert child.closed
    assert child.process is None
    assert child.job is None
    assert not api.handles


def test_retry_does_not_close_already_released_job():
    api = FakeAPI()
    api.failures.add("process")

    child = ContainedChild(api, "job", "process")

    with pytest.raises(RuntimeError):
        child.close()

    api.failures.clear()

    child.close()

    job_closes = [
        event
        for event in api.events
        if event == ("close", "job")
    ]

    assert len(job_closes) == 1
