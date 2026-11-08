"""R7E46O adversarial journal tests: all storage/providers are isolated."""
import asyncio
import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from app.investment.extended_hours_collector import ExtendedHoursCollector
from app.investment.extended_hours_integrity import (
    JournalCommitment,
    JournalIntegrityError,
)

NOW = datetime(2026, 10, 16, 12, tzinfo=UTC)

class Quotes:
    def __init__(self):
        self.timestamp = NOW
        self.price = 250
    async def get_many(self, symbols):
        return {s: {"price": self.price, "effective_timestamp": self.timestamp.isoformat(),
                    "source": "fixture", "quality": "LIVE"} for s in symbols}

def collect(path, quotes):
    return asyncio.run(ExtendedHoursCollector(quotes, path).collect_once(["TEST"], now=quotes.timestamp))

def seed(path):
    quotes = Quotes()
    assert len(collect(path, quotes)) == 1
    quotes.timestamp += timedelta(seconds=10)
    assert len(collect(path, quotes)) == 1
    return quotes

@pytest.mark.parametrize("damage", ["tail", "empty", "delete", "middle", "same_size", "replace"])
def test_missing_or_changed_records_fail_closed_across_restart(tmp_path, damage):
    path = tmp_path / "research.jsonl"
    quotes = seed(path)
    original = path.read_bytes()
    if damage == "tail": path.write_bytes(original.splitlines(keepends=True)[0])
    elif damage == "empty": path.write_bytes(b"")
    elif damage == "delete": path.unlink()
    elif damage == "middle": path.write_bytes(original.splitlines(keepends=True)[1])
    elif damage == "same_size": path.write_bytes(original.replace(b"250", b"251"))
    else: path.write_bytes(b'{"other":"valid JSON"}\n')
    damaged = path.read_bytes() if path.exists() else None
    with pytest.raises(JournalIntegrityError): collect(path, quotes)
    assert (path.read_bytes() if path.exists() else None) == damaged

@pytest.mark.parametrize("damage", ["missing", "empty", "garbage", "wrong_path", "pending"])
def test_invalid_independent_witness_blocks_without_reconstruction(tmp_path, damage):
    path = tmp_path / "research.jsonl"
    quotes = seed(path)
    witness = JournalCommitment(path).path
    if damage == "missing": witness.unlink()
    elif damage == "empty": witness.write_bytes(b"")
    elif damage == "garbage": witness.write_bytes(b"invalid sqlite")
    else:
        with sqlite3.connect(witness) as db:
            db.execute("UPDATE commitment SET " + ("journal='foreign'" if damage == "wrong_path" else "pending=1"))
    original = path.read_bytes()
    state = witness.read_bytes() if witness.exists() else None
    with pytest.raises(JournalIntegrityError): collect(path, quotes)
    assert path.read_bytes() == original
    assert (witness.read_bytes() if witness.exists() else None) == state

@pytest.mark.parametrize("phase", ["before_append", "after_fsync"])
def test_interrupted_commit_is_quarantined_not_retried(tmp_path, monkeypatch, phase):
    path = tmp_path / "research.jsonl"
    quotes = seed(path)
    quotes.timestamp += timedelta(seconds=10)
    if phase == "after_fsync":
        monkeypatch.setattr(JournalCommitment, "finish", lambda *a: (_ for _ in ()).throw(OSError("fixture interruption")))
    else:
        prepare = JournalCommitment.prepare
        def interrupted(self, content):
            prepare(self, content)
            raise OSError("fixture interruption")
        monkeypatch.setattr(JournalCommitment, "prepare", interrupted)
    with pytest.raises(OSError): collect(path, quotes)
    original = path.read_bytes()
    monkeypatch.undo()
    with pytest.raises(JournalIntegrityError): collect(path, quotes)
    assert path.read_bytes() == original

def test_verified_original_backup_restores_committed_pair_without_changing_witness(tmp_path):
    path = tmp_path / "research.jsonl"
    quotes = seed(path)
    original = path.read_bytes()
    witness = JournalCommitment(path).path.read_bytes()
    path.write_bytes(original.splitlines(keepends=True)[0])
    with pytest.raises(JournalIntegrityError): collect(path, quotes)
    path.write_bytes(original) # Simulated approved offline restore, fixture ONLY.
    assert collect(path, quotes) == []
    assert JournalCommitment(path).path.read_bytes() == witness

def test_explicit_legacy_migration_preserves_bytes_and_then_detects_loss(tmp_path):
    path = tmp_path / "research.jsonl"
    quotes = seed(path)
    legacy = tmp_path / "legacy.jsonl"
    legacy.write_bytes(path.read_bytes())
    c = ExtendedHoursCollector(quotes, legacy)
    with pytest.raises(JournalIntegrityError): collect(legacy, quotes)
    assert not JournalCommitment(legacy).path.exists()
    with pytest.raises(JournalIntegrityError): c.adopt_legacy_journal(expected_sha256="wrong")
    assert not JournalCommitment(legacy).path.exists()
    original = legacy.read_bytes()
    c.adopt_legacy_journal(expected_sha256=hashlib.sha256(original).hexdigest())
    assert legacy.read_bytes() == original
    assert collect(legacy, quotes) == []
    with pytest.raises(JournalIntegrityError): c.adopt_legacy_journal(expected_sha256=hashlib.sha256(original).hexdigest())
    legacy.write_bytes(original.splitlines(keepends=True)[0])
    with pytest.raises(JournalIntegrityError): collect(legacy, quotes)

def test_conflicting_identity_does_not_change_either_committed_file(tmp_path):
    path = tmp_path / "research.jsonl"
    quotes = seed(path)
    original = path.read_bytes()
    witness = JournalCommitment(path).path.read_bytes()
    quotes.price = 999
    with pytest.raises(JournalIntegrityError, match="Conflicting"): collect(path, quotes)
    assert path.read_bytes() == original
    assert JournalCommitment(path).path.read_bytes() == witness
