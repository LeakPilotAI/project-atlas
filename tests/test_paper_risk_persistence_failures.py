import json

import pytest
from app.services import paper_risk_controls as controls
from app.services.paper_risk import check_paper_risk


@pytest.mark.parametrize('value', ['invalid', None, True, float('nan'), float('inf'), {}, []])
def test_invalid_loss_never_reliable_zero(tmp_path, value):
    path = tmp_path / 'controls.json'
    path.write_text(json.dumps({'kill_switch': False, 'session_net_r': value}))
    store = controls.PaperRiskControlStore(path)
    assert store.reliable is False
    result = check_paper_risk(open_positions=[], requested_risk_usd=1,
                              controls_reliable=store.reliable, session_net_r=store.session_net_r)
    assert result['allowed'] is False
    with pytest.raises(RuntimeError, match='reconciliation'):
        store.save()


@pytest.mark.parametrize('stage', ['write', 'replace', 'parent'])
def test_failure_propagates_and_refuses_retry(tmp_path, monkeypatch, stage):
    path = tmp_path / 'controls.json'
    store = controls.PaperRiskControlStore(path)
    store.session_net_r = -2.5
    store.save()
    original = path.read_bytes()
    store.kill_switch = True
    error = OSError(28, 'synthetic persistence failure')
    def fail(*args, **kwargs):
        raise error
    if stage == 'write':
        monkeypatch.setattr(controls, 'write_flushed', fail)
    elif stage == 'replace':
        monkeypatch.setattr(type(path), 'replace', fail)
    else:
        monkeypatch.setattr(controls, 'sync_parent', fail)
    with pytest.raises(OSError) as raised:
        store.save()
    assert raised.value is error
    assert store.reliable is False
    with pytest.raises(RuntimeError, match='reconciliation'):
        store.save()
    with pytest.raises(RuntimeError, match='reconciliation'):
        store.load()
    if stage != 'parent':
        assert path.read_bytes() == original
        assert list(tmp_path.glob('*.tmp'))  # Partial evidence preserved.
    else:
        assert json.loads(path.read_bytes())['kill_switch'] is True  # Publication uncertain, never success.


def test_restart_preserves_loss_and_kill_switch(tmp_path):
    path = tmp_path / 'controls.json'
    store = controls.PaperRiskControlStore(path)
    store.session_net_r = -3.5
    store.kill_switch = True
    store.save()
    loaded = controls.PaperRiskControlStore(path)
    assert loaded.snapshot() == {'kill_switch': True, 'session_net_r': -3.5, 'reliable': True}
