"""Actual Windows NTFS pinned journal crash inspection regression."""
import copy
import pytest
from app.services.quality_dips_autonomous_v4_native_journal_recovery_proposal import inspect_pinned_native_v4_journal
from test_quality_dips_autonomous_v4_native_journal_writer_proposal import journal, record
from test_quality_dips_autonomous_v4_native_proposal_readback import native_proposal


def check(port, writer, pins=None):
    return inspect_pinned_native_v4_journal(port, copy.deepcopy(writer.pins) if pins is None else pins)


def test_native_crash_inspection_two_commits_remains_fenced(journal):
    port, writer = journal
    writer.reserve(record())
    writer.commit()
    writer.reserve(record(2))
    writer.commit()
    result = check(port, writer)
    assert result['revision'] == 2 and result['status'] == 'IDLE'
    assert result['snapshot_count'] == 4
    assert result['restart_fenced'] is True
    assert result['paper_execution_authorized'] is False


def test_native_crash_inspection_pending_is_uncertain(journal):
    port, writer = journal
    writer.reserve(record())
    result = check(port, writer)
    assert result['revision'] == 0 and result['status'] == 'UNCERTAIN'
    assert result['restart_fenced'] is True


@pytest.mark.parametrize('damage', ['missing', 'extra', 'changed', 'wrong_pin', 'gap',
    'wrong_revision', 'wrong_head', 'post_read_mutation', 'post_read_extra'])
def test_native_crash_inspection_refuses_corrupt_history(journal, damage):
    port, writer = journal
    writer.reserve(record())
    writer.commit()
    writer.reserve(record(2))
    writer.commit()
    root = port.root / 'journal'
    pins = copy.deepcopy(writer.pins)
    if damage == 'missing': (root / '0001-reserved.json').unlink()
    if damage == 'extra': (root / 'rogue.json').write_bytes(b'{}')
    if damage == 'changed': (root / '0002-committed.json').write_bytes(b'{}')
    if damage == 'wrong_pin': pins['0001-committed.json']['sha256'] = 'f'*64
    if damage == 'gap': pins['0002-reserved.jsonx'] = pins.pop('0002-reserved.json')
    if damage == 'wrong_revision': pins['0001-reserved.json']['id'] = [True, 0, 0]
    if damage == 'wrong_head': pins['0001-committed.json']['sha256'] = 'g'*64
    if damage.startswith('post_read'):
        original = port.read_bound
        calls = [0]
        def mutate(name, pin):
            raw = original(name, pin)
            calls[0] += 1
            if calls[0] == 4:
                if damage == 'post_read_mutation': (root / '0001-reserved.json').write_bytes(b'{}')
                else: (root / 'rogue.json').write_bytes(b'{}')
            return raw
        port.read_bound = mutate
    with pytest.raises((ValueError, OSError)):
        check(port, writer, pins)


def test_native_crash_inspection_refuses_self_recovery_without_pins(journal):
    port, writer = journal
    writer.reserve(record())
    with pytest.raises(ValueError): inspect_pinned_native_v4_journal(port, {})