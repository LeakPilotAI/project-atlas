import pytest
from scripts.observation_runtime import personal_native_mutex_contention as m


def test_mutex_probe_refuses_unverified_native_roots(monkeypatch):
    monkeypatch.setattr(m, 'inspect', lambda: {'all_six_verified': False})
    with pytest.raises(ValueError, match='QD_NATIVE_RESOURCES_UNVERIFIED'):
        m.probe()


def test_child_code_requires_exact_native_root_identity():
    assert 'ROOT_ID_CHANGED' in m.CHILD
    assert 'status=reg.wait(reg.mutex,200)' in m.CHILD
    assert 'if status==0:reg.release(reg.mutex)' in m.CHILD
