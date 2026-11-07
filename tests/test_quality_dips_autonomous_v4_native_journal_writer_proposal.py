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
@pytest.mark.parametrize('attack', ['rebind_reservation', 'rebind_commit'])
def test_native_writer_replays_chain_not_just_individual_pins(journal, attack):
    import hashlib
    from app.services.paper_financial_replay import body, strict
    port, writer = journal
    writer.reserve(record())
    if attack == 'rebind_commit': writer.commit()
    name = '0001-reserved.json' if attack == 'rebind_reservation' else '0001-committed.json'
    path = port.root / 'journal' / name
    document = strict(path.read_text(encoding='utf-8'))
    if attack == 'rebind_reservation':
        document['pending']['record']['publication_id'] = 'ALTERED-PUB'
    else:
        document['head'] = 'f' * 64
    raw = body(document).encode('utf-8')
    path.write_bytes(raw)
    # Simulates a compromised same-process pin registry that re-pins altered
    # bytes. Native identity alone is not sufficient to prove chain continuity.
    writer.pins[name]['sha256'] = hashlib.sha256(raw).hexdigest()
    with pytest.raises((ValueError, OSError)):
        writer.commit() if attack == 'rebind_reservation' else writer.reserve(record(2))
    assert writer.fenced is True
@pytest.mark.parametrize('stage', ['reserve_before_write', 'reserve_after_write',
    'commit_before_write', 'commit_after_write'])
def test_native_writer_fences_ambiguous_partial_write(stage, journal):
    port, writer = journal
    if stage.startswith('commit'): writer.reserve(record())
    original = port.write_bound
    def fail(name, raw):
        if stage.endswith('after_write'): original(name, raw)
        raise OSError('injected native write uncertainty')
    port.write_bound = fail
    with pytest.raises(OSError):
        writer.reserve(record()) if stage.startswith('reserve') else writer.commit()
    assert writer.fenced is True
    assert writer.state['status'] == 'UNCERTAIN'
    with pytest.raises(ValueError): writer.commit()
    with pytest.raises(ValueError): writer.reserve(record(2))
    with pytest.raises(ValueError): ConfinedNativeV4JournalProposal(port) if stage.endswith('after_write') else writer.commit()