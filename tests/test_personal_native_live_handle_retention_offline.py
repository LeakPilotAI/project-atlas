"""No native process: injected fake Popen ownership and retry failures."""
import queue
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from personal_native_compatibility_fixture import OwnedChild

import scripts.observation_runtime.disposable_host_owner as observations


def child():
    owner = OwnedChild.__new__(OwnedChild)
    handle = Mock()
    handle.__int__ = Mock(return_value=123)
    owner.p = SimpleNamespace(_handle=handle,pid=234,wait=Mock(),poll=Mock(return_value=None),
        terminate=Mock(),stdout=Mock(),stderr=Mock(),returncode=None)
    owner.created = 100
    owner.seconds = 30
    owner.b = SimpleNamespace(check=lambda:0,write=Mock())
    owner.readers = []
    owner.lines = queue.Queue()
    owner.errors = []
    owner.identity = {'pid':234,'created':100,'image':'synthetic.exe'}
    return owner


@pytest.mark.parametrize('reason',['identity','budget','wait_failure'])
def test_failed_finish_keeps_live_process_handle_and_pipes(monkeypatch,reason):
    owner = child()
    monkeypatch.setattr(observations,'observe_handle',lambda handle:200 if reason=='identity' else 100)
    if reason=='budget':owner.b.check=lambda:540
    if reason=='wait_failure':owner.p.wait.side_effect=OSError('synthetic wait failure')
    with pytest.raises((ValueError,OSError)) as failure:
        owner.finish()
    owner.p._handle.Close.assert_not_called()
    owner.p.stdout.close.assert_not_called()
    owner.p.stderr.close.assert_not_called()
    assert failure.value.owned_child is owner
    owner.b.write.assert_not_called()


def test_wait_without_confirmed_exit_cannot_publish_clean_evidence(monkeypatch):
    owner=child()
    monkeypatch.setattr(observations,'observe_handle',lambda handle:100)
    with pytest.raises(ValueError,match='OWNED_CHILD_STILL_RUNNING'):
        owner.finish()
    owner.p._handle.Close.assert_not_called()
    owner.b.write.assert_not_called()


def test_verified_exit_releases_pipes_and_handle_once(monkeypatch):
    owner=child()
    monkeypatch.setattr(observations,'observe_handle',lambda handle:100)
    owner.p.poll.return_value=0
    owner.p.returncode=0
    from pathlib import Path
    owner.b.root=Path('synthetic-only-no-files-created')
    result=owner.finish()
    assert result['reaped'] is True
    owner.p._handle.Close.assert_called_once_with()
    owner.p.stdout.close.assert_called_once_with()
    owner.p.stderr.close.assert_called_once_with()


@pytest.mark.parametrize('resource',['stdout','handle'])
def test_exited_cleanup_failure_remains_retryable_without_republishing(monkeypatch,resource):
    owner=child()
    monkeypatch.setattr(observations,'observe_handle',lambda handle:100)
    owner.p.poll.return_value=0
    owner.p.returncode=0
    from pathlib import Path
    owner.b.root=Path('synthetic-only-no-files-created')
    failing=owner.p.stdout.close if resource=='stdout' else owner.p._handle.Close
    failing.side_effect=OSError('synthetic close failure')
    with pytest.raises(RuntimeError,match='OWNED_RESOURCE_CLEANUP_INCOMPLETE') as failure:
        owner.finish()
    assert failure.value.owned_child is owner
    owner.b.write.assert_called_once()
    failing.side_effect=None
    owner.finish()
    owner.b.write.assert_called_once()
    assert failing.call_count==2
    if resource=='stdout':owner.p._handle.Close.assert_called_once()
    else:owner.p.stdout.close.assert_called_once()


def test_repeated_finish_reuses_acknowledged_test_evidence(monkeypatch):
    owner=child()
    monkeypatch.setattr(observations,'observe_handle',lambda handle:100)
    owner.p.poll.return_value=0
    owner.p.returncode=0
    from pathlib import Path
    owner.b.root=Path('synthetic-only-no-files-created')
    first=owner.finish()
    assert owner.finish() is first
    owner.b.write.assert_called_once()
    owner.p._handle.Close.assert_called_once()
