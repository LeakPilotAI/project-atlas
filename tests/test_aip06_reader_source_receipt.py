from types import SimpleNamespace
import pytest
from scripts.observation_runtime.aip06_reader_context_entry import verify_inherited_reader_source
from scripts.observation_runtime.aip06_scoped_context import READER_ENTRY

@pytest.mark.parametrize('damage', ['missing_pin', 'wrong_hash', 'open_receipt', 'wrong_path', 'missing_receipt'])
def test_inherited_reader_source_requires_closed_matching_native_receipt(damage):
    pin = 'a' * 64
    receipt = {'path': READER_ENTRY, 'sha256': pin, 'closed': True}
    pins = {READER_ENTRY: pin}
    if damage == 'missing_pin': pins = {}
    if damage == 'wrong_hash': receipt['sha256'] = 'b' * 64
    if damage == 'open_receipt': receipt['closed'] = False
    if damage == 'wrong_path': receipt['path'] = 'other.py'
    if damage == 'missing_receipt': receipt = None
    runtime = SimpleNamespace(descriptor={'argv': ['python', '-B', READER_ENTRY], 'source_pins': pins}, verify_source=lambda path: receipt)
    guard = SimpleNamespace(processes=SimpleNamespace(runtime=runtime))
    with pytest.raises(ValueError, match='PINNED_INHERITED_READER_ENTRY_REQUIRED' if damage == 'missing_pin' else 'CLOSED_INHERITED_READER_SOURCE_RECEIPT_REQUIRED'):
        verify_inherited_reader_source(guard)

def test_inherited_reader_source_accepts_closed_matching_receipt():
    pin = 'a' * 64
    runtime = SimpleNamespace(descriptor={'argv': ['python', '-B', READER_ENTRY], 'source_pins': {READER_ENTRY: pin}},
                              verify_source=lambda path: {'path': path, 'sha256': pin, 'closed': True})
    verify_inherited_reader_source(SimpleNamespace(processes=SimpleNamespace(runtime=runtime)))

@pytest.mark.parametrize('argv', [None, [], ['python', '-X', READER_ENTRY], ['python', '-B', 'other.py']])
def test_inherited_reader_source_refuses_wrong_child_command_before_receipt(argv):
    checks = []
    runtime = SimpleNamespace(descriptor={'argv': argv, 'source_pins': {READER_ENTRY: 'a' * 64}},
                              verify_source=lambda path: checks.append(path))
    with pytest.raises(ValueError, match='PINNED_INHERITED_READER_COMMAND_REQUIRED'):
        verify_inherited_reader_source(SimpleNamespace(processes=SimpleNamespace(runtime=runtime)))
    assert checks == []


def test_provider_reader_reuses_single_original_guard_after_source_verification(monkeypatch):
    from scripts.observation_runtime import aip06_reader_context_entry as entry
    from scripts.observation_runtime import aip06_fixture_guard as fixture
    from scripts.observation_runtime import aip06_windows_acceptance_adapters as adapters
    from types import SimpleNamespace
    calls = []
    guard = object()
    monkeypatch.setattr(fixture, 'require_fixture', lambda role: calls.append(('guard', role)) or guard)
    monkeypatch.setattr(entry, 'verify_inherited_reader_source', lambda value: calls.append(('source', value)))
    monkeypatch.setattr(entry, '_prepare_reader_with_guard',
                        lambda value, a, b: calls.append(('prepare', value, a, b)) or 'context')
    pair = (object.__new__(adapters.WindowsReaderSet), object.__new__(adapters.PinnedWindowsRead))
    assert entry.prepare_reader_from_provider(pair) == 'context'
    assert calls == [('guard', 'independent-scoped-reader'), ('source', guard),
                     ('prepare', guard, pair[0], pair[1])]


@pytest.mark.parametrize('pin', ['', 'a' * 63, 'A' * 64, 'z' * 64, 42, None])
def test_inherited_reader_source_refuses_malformed_digest_before_receipt(pin):
    checks = []
    runtime = SimpleNamespace(
        descriptor={'argv': ['python', '-B', READER_ENTRY], 'source_pins': {READER_ENTRY: pin}},
        verify_source=lambda path: checks.append(path))
    with pytest.raises(ValueError, match='PINNED_INHERITED_READER_ENTRY_REQUIRED'):
        verify_inherited_reader_source(SimpleNamespace(processes=SimpleNamespace(runtime=runtime)))
    assert checks == []
