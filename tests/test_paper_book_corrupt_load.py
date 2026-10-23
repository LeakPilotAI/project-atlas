from pathlib import Path

import pytest
from app.investment.paper_book import PaperBook, PaperBookStateUnavailable


@pytest.mark.parametrize('raw', [b'{', b'', b'\xff\xfe', b'{"cash":NaN'])
def test_existing_unreadable_state_never_blank_book(tmp_path, raw):
    path = tmp_path / 'paper.json'
    path.write_bytes(raw)
    with pytest.raises(PaperBookStateUnavailable) as raised:
        PaperBook.load(path, ledger_path=tmp_path / 'ledger.jsonl')
    assert isinstance(raised.value.__cause__, (OSError, ValueError))
    assert path.read_bytes() == raw
    assert not (tmp_path / 'ledger.jsonl').exists()


def test_read_failure_preserves_context_and_never_initializes(tmp_path, monkeypatch):
    path = tmp_path / 'paper.json'
    path.write_text('{}')
    error = PermissionError('synthetic denied read')
    original = Path.read_text
    def refuse(self, *args, **kwargs):
        if self == path:
            raise error
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', refuse)
    with pytest.raises(PaperBookStateUnavailable) as raised:
        PaperBook.load(path, ledger_path=tmp_path / 'ledger.jsonl')
    assert raised.value.__cause__ is error


def test_missing_state_legacy_initialization_unchanged(tmp_path):
    path = tmp_path / 'missing.json'
    book = PaperBook.load(path, cash=123, ledger_path=tmp_path / 'ledger.jsonl')
    assert book.cash == 123
    assert not path.exists()
