"""Real Windows NTFS confined immutable proposed journal write tests."""
import pytest
from app.services.quality_dips_autonomous_v4_native_journal_writer_proposal import ConfinedNativeV4JournalProposal
from test_quality_dips_autonomous_v4_native_proposal_readback import native_proposal


class NativePort:
    def __init__(self, fixture):
        self.module, self.output, self.root, _, _ = fixture
        self.source = self.root / 'source'
        # Separate fresh native root, not existing event history files.
        self.journal = self.module.s.w.WindowsOutput.create_root(str(self.root / 'journal'))
    def close(self): self.journal.close()
    def list_names(self): return [p.name for p in (self.root / 'journal').iterdir()]
    def write_bound(self, name, raw): return self.journal.write_bound(name, raw)
    def read_bound(self, name, pin): return self.module.s.read_bound(self.journal, name, pin)[0]


@pytest.fixture
def journal(native_proposal):
    port = NativePort(native_proposal)
    try: yield port, ConfinedNativeV4JournalProposal(port)
    finally: port.close()


def record(i=1): return {'publication_digest': f'{i:064x}', 'publication_id': f'PUB-{i}'}


def test_native_append_only_reserve_commit_two_revisions(journal):
    port, writer = journal
    writer.reserve(record())
    writer.commit()
    writer.reserve(record(2))
    writer.commit()
    assert writer.state['revision'] == 2
    assert writer.state['status'] == 'IDLE'
    assert len(writer.pins) == 4
    assert len(port.list_names()) == 4
    result = writer.restart()
    assert result['revision'] == 2
    assert result['paper_execution_authorized'] is False
    with pytest.raises(ValueError): writer.reserve(record(3))


def test_native_reserved_crash_fences_restart(journal):
    port, writer = journal
    writer.reserve(record())
    state = writer.restart()
    assert state['status'] == 'UNCERTAIN'
    with pytest.raises(ValueError): writer.commit()
    with pytest.raises(ValueError): writer.reserve(record(2))
    with pytest.raises(ValueError): ConfinedNativeV4JournalProposal(port)


@pytest.mark.parametrize('damage', ['reserved_changed', 'reserved_missing', 'extra',
    'wrong_pin', 'commit_changed', 'commit_missing'])
def test_native_writer_fails_closed_after_mutation(journal, damage):
    port, writer = journal
    writer.reserve(record())
    if damage.startswith('commit'):
        writer.commit()
        name = '0001-committed.json'
    else:
        name = '0001-reserved.json'
    if damage.endswith('changed'): (port.root / 'journal' / name).write_bytes(b'{}')
    if damage.endswith('missing'): (port.root / 'journal' / name).unlink()
    if damage == 'extra': (port.root / 'journal' / 'extra.json').write_bytes(b'{}')
    if damage == 'wrong_pin': writer.pins[name]['sha256'] = 'f'*64
    with pytest.raises((ValueError, OSError)):
        writer.reserve(record(2)) if damage.startswith('commit') else writer.commit()
    assert writer.fenced is True