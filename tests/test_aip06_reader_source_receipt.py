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
    runtime = SimpleNamespace(descriptor={'source_pins': pins}, verify_source=lambda path: receipt)
    guard = SimpleNamespace(processes=SimpleNamespace(runtime=runtime))
    with pytest.raises(ValueError, match='PINNED_INHERITED_READER_ENTRY_REQUIRED' if damage == 'missing_pin' else 'CLOSED_INHERITED_READER_SOURCE_RECEIPT_REQUIRED'):
        verify_inherited_reader_source(guard)

def test_inherited_reader_source_accepts_closed_matching_receipt():
    pin = 'a' * 64
    runtime = SimpleNamespace(descriptor={'source_pins': {READER_ENTRY: pin}},
                              verify_source=lambda path: {'path': path, 'sha256': pin, 'closed': True})
    verify_inherited_reader_source(SimpleNamespace(processes=SimpleNamespace(runtime=runtime)))
