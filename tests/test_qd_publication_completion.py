"""Pure publication-port race tests. No stores, providers, accounts or hosts."""
import copy
from types import SimpleNamespace

import pytest
from app.services.quality_dips_publication_reader import QualityDipsPublicationReader


def fixture():
    now = [100]
    cut = {'state': {'positions': {}}}
    packet = {'schema': 'QD_SCANNER_PUBLICATION_V1', 'source_id': 'SYNTHETIC', 'revision': 1,
              'observed_at': 100, 'bundles': [], 'monitors': {}}
    authority = SimpleNamespace(verify_publication_components=lambda *args: True,
                                verify_scanner_publication=lambda *args: True)
    runtime = SimpleNamespace(grant={}, stopped=SimpleNamespace(is_set=lambda: False), halted=False,
                              _now=lambda: now[0])
    writer = SimpleNamespace(authority=authority, binding={}, runtime=SimpleNamespace(runtime=runtime),
                             _cut=lambda: copy.deepcopy(cut))
    source = SimpleNamespace(read_publication=lambda timeout: copy.deepcopy(packet))
    reader = QualityDipsPublicationReader(writer=writer, source=source)
    return SimpleNamespace(**locals())


def test_valid_empty_publication_is_healthy_no_signal():
    s = fixture()
    assert s.reader.read_request(.2) is None
    assert s.reader._last[1] == 1


@pytest.mark.parametrize('damage', ['expiry', 'clock-backward', 'clock-type', 'cut', 'stop', 'revocation'])
def test_qd_completion_refuses_changed_source_context(damage):
    s = fixture()
    calls = [0]
    def verify(*args):
        calls[0] += 1
        if calls[0] > 1:
            return damage != 'revocation'
        if damage == 'expiry': s.now[0] = 131
        elif damage == 'clock-backward': s.now[0] = 99
        elif damage == 'clock-type': s.now[0] = 100.0
        elif damage == 'cut': s.cut['state']['unexpected_revision'] = 2
        elif damage == 'stop': s.runtime.halted = True
        return True
    s.authority.verify_scanner_publication = verify
    with pytest.raises(ValueError):
        s.reader.read_request(.2)
    assert s.reader._last is None
