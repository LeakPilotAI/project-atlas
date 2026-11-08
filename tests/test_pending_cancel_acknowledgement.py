import pytest
from app.services.perp_setup_paper_mirror import PerpSetupPaperMirror


def mirror(tmp_path):
    obj=PerpSetupPaperMirror(pending_path=tmp_path/'synthetic-pending.jsonl');obj._seeded=True
    obj._pending={'first':{'setup_key':'BTC:LONG','symbol':'BTC','side':'LONG'}}
    return obj


@pytest.mark.parametrize('error',[OSError('synthetic disk full'),PermissionError('synthetic denied'),RuntimeError('synthetic publication failure')])
def test_failed_cancel_append_preserves_pending_and_terminal_state(tmp_path,monkeypatch,error):
    obj=mirror(tmp_path);before=dict(obj._pending)
    def fail(_):raise error
    monkeypatch.setattr(obj,'_append_pending_event',fail)
    with pytest.raises(type(error)) as actual:obj.cancel_all_pending(reason='OPERATOR_CANCEL')
    assert actual.value is error and obj._pending==before
    assert obj._recent_terminal==[] and obj._terminal_pending_instances==set()


def test_partial_batch_keeps_committed_cancel_but_retains_unacknowledged_pending(tmp_path,monkeypatch):
    obj=mirror(tmp_path);obj._pending['second']={'setup_key':'ETH:LONG','symbol':'ETH','side':'LONG'};committed=[]
    def append(row):
        if row['setup_instance_id']=='second':raise OSError('synthetic second failure')
        committed.append(row)
    monkeypatch.setattr(obj,'_append_pending_event',append)
    with pytest.raises(OSError):obj.cancel_all_pending(reason='OPERATOR_CANCEL')
    assert set(obj._pending)=={'second'} and obj._terminal_pending_instances=={'first'}
    assert len(committed)==1 and committed[0]['setup_instance_id']=='first'


def test_successful_cancel_retry_does_not_append_duplicate_and_shutdown_preserves(tmp_path,monkeypatch):
    obj=mirror(tmp_path);committed=[];monkeypatch.setattr(obj,'_append_pending_event',committed.append)
    assert obj.cancel_all_pending(reason='ATLAS_SHUTDOWN')==0 and not committed
    assert obj.cancel_all_pending(reason='OPERATOR_CANCEL')==1
    assert obj.cancel_all_pending(reason='OPERATOR_CANCEL')==0 and len(committed)==1
