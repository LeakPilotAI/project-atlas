"""Retry ownership regressions; fake API only, no native process creation."""
import pytest

from scripts.observation_runtime.personal_native_job import launch_contained_child


class API:
    def __init__(self):
        self.live = {"job", "process", "thread"}
        self.events = []
        self.fail_termination = True
        self.fail_thread_close = False
    def create_job(self): return "job"
    def configure_kill_on_close(self, job): pass
    def create_suspended_child(self, command): return "process", "thread"
    def assign_child(self, job, process): raise RuntimeError("assignment refused")
    def resume_child(self, thread): raise AssertionError("must never resume")
    def terminate_process(self, process):
        self.events.append("terminate_process")
        if self.fail_termination: raise RuntimeError("termination refused")
    def terminate_job(self, job): self.events.append("terminate_job")
    def close_handle(self, handle):
        self.events.append("close_" + handle)
        if handle == "thread" and self.fail_thread_close:
            raise RuntimeError("close refused")
        self.live.remove(handle)

def test_unassigned_failed_termination_retains_last_process_handle_for_retry():
    api = API()
    with pytest.raises(RuntimeError) as caught:
        launch_contained_child(api, ["mock"])
    cleanup = caught.value.cleanup
    assert cleanup.process == "process"
    assert "process" in api.live
    assert "close_process" not in api.events
    api.fail_termination = False
    cleanup.close()
    assert cleanup.closed
    assert not api.live

def test_failed_thread_close_remains_owned_on_exception():
    api = API()
    api.fail_termination = False
    api.fail_thread_close = True
    with pytest.raises(RuntimeError) as caught:
        launch_contained_child(api, ["mock"])
    cleanup = caught.value.cleanup
    assert cleanup.thread == "thread"
    api.fail_thread_close = False
    cleanup.close()
    assert cleanup.closed
    assert not api.live


def test_authority_nul_is_rejected_before_path_probe(monkeypatch):
    import sys

    from scripts.observation_runtime.personal_native_launch_contract import (
        validate_authorized_launch,
    )
    with pytest.raises(ValueError, match="NATIVE_LAUNCH_INVALID_AUTHORITY"):
        validate_authorized_launch([sys.executable], sys.executable + "\x00")
