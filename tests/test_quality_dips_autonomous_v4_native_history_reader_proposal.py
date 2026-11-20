"""Real confined Windows native readback through source-only proposed V4 consumer."""
import pytest
from app.services.quality_dips_autonomous_v4_native_history_reader_proposal import inspect_bounded_proposed_v4_native_history
from test_quality_dips_autonomous_v4_native_proposal_readback import native_proposal


class ConfinedReader:
    def __init__(self, fixture):
        self.module, self.output, self.root, self.pins, self.enrollment = fixture
        self.reads = 0
    def list_names(self):
        return [p.name for p in (self.root / 'source').iterdir()]
    def read_bound(self, name, pin):
        self.reads += 1
        raw, _ = self.module.s.read_bound(self.output, name, pin)
        return raw


def test_proposed_bounded_native_history_reconciles_nonzero(native_proposal):
    reader = ConfinedReader(native_proposal)
    result = inspect_bounded_proposed_v4_native_history(reader, reader.pins, reader.enrollment)
    assert result['revision'] == 3
    assert reader.reads == 8
    assert result['native_history_readback_checked'] is True
    assert result['independent_custody_accepted'] is False
    assert result['paper_execution_authorized'] is False


@pytest.mark.parametrize('attack', ['missing', 'extra', 'alter_event', 'alter_assertion',
    'wrong_pin', 'noncontiguous', 'post_audit_event', 'post_audit_assertion'])
def test_proposed_bounded_native_history_refuses_faults(native_proposal, attack):
    reader = ConfinedReader(native_proposal)
    source = reader.root / 'source'
    if attack == 'missing': (source / '0002-event.json').unlink()
    if attack == 'extra': (source / 'rogue.json').write_bytes(b'{}')
    if attack == 'alter_event': (source / '0002-event.json').write_bytes(b'{}')
    if attack == 'alter_assertion': (source / 'assertion.json').write_bytes(b'{}')
    if attack == 'wrong_pin': reader.pins['0001-event.json']['sha256'] = 'f'*64
    if attack == 'noncontiguous': reader.pins['0002-event.jsonx'] = reader.pins.pop('0002-event.json')
    if attack.startswith('post_audit'):
        original = reader.read_bound
        def mutate(name, pin):
            raw = original(name, pin)
            if reader.reads == 4:
                target = '0002-event.json' if attack == 'post_audit_event' else 'assertion.json'
                (source / target).write_bytes(b'{}')
            return raw
        reader.read_bound = mutate
    with pytest.raises((ValueError, OSError)):
        inspect_bounded_proposed_v4_native_history(reader, reader.pins, reader.enrollment)


def test_proposed_bounded_native_history_rejects_untrusted_pin_shape(native_proposal):
    reader = ConfinedReader(native_proposal)
    reader.pins['0001-event.json']['id'] = [True, 0, 0]
    with pytest.raises(ValueError):
        inspect_bounded_proposed_v4_native_history(reader, reader.pins, reader.enrollment)