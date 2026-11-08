"""Refused personal activation must not consume a create-only custody root."""
import sys
from types import SimpleNamespace

import pytest

from scripts.observation_runtime import personal_activation_publisher as publisher


def test_oversized_validated_activation_never_opens_native_root(monkeypatch):
    class Clock:
        def require_operational(self, runtime_id):
            assert runtime_id == 'paper-test'
        def runtime_sample(self):
            return {'utc': 123}
        def verify_runtime_sample(self, sample):
            return True

    monkeypatch.setitem(sys.modules, 'scripts.observation_runtime.personal_windows_clock',
                        SimpleNamespace(LocalWindowsClock=Clock))
    monkeypatch.setitem(sys.modules, 'scripts.volume_inspector.windows_output',
                        SimpleNamespace(current_sid=lambda: 'operator'))
    monkeypatch.setattr('backend.app.services.personal_paper_runtime.validate_activation_record',
                        lambda *args, **kwargs: True)
    called = []
    monkeypatch.setattr(publisher, '_native_store', lambda: called.append('native') or None)
    record = {'actions': ['READ_ONLY'], 'oversized': 'x' * 65536}
    with pytest.raises(publisher.PersonalActivationPublicationRefused,
                       match='exceeds native output bound'):
        publisher.publish_personal_activation(
            root=r'D:\AtlasCustody\PersonalPaper\test-once-only',
            record=record, policy={}, operator_id='operator', release_digest='a'*64,
            accounts={'QUALITY_DIPS':'b'*64}, clock=Clock(), runtime_id='paper-test')
    assert called == []
