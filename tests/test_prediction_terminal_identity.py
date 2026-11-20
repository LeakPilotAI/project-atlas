"""Contradictory synthetic terminal identity must not free a position."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from app.prediction.paper_engine import PredictionPaperError
from test_prediction_accounting_completeness import closed, journal, opened, write_rows


@pytest.mark.parametrize('event', ['close', 'expired_unclosed'])
@pytest.mark.parametrize('field,value', [('ticker', 'OTHER_SYNTHETIC'), ('side', 'NO')])
def test_conflicting_terminal_identity_is_refused_before_state_projection(tmp_path, event, field, value):
    j = journal(tmp_path)
    terminal = closed()
    terminal['event'] = event
    terminal[field] = value
    write_rows(j, [opened(), terminal])
    before = j.journal_path.read_bytes()
    with pytest.raises(PredictionPaperError, match='identity'):
        j.open_trade()
    with pytest.raises(PredictionPaperError):
        j.snapshot()
    assert j.persistence_failure(include_candidates=False) is not None
    with pytest.raises(PredictionPaperError):
        journal(tmp_path).open_trade()
    assert j.journal_path.read_bytes() == before


@pytest.mark.parametrize('records', [
    [{'event': 'open', 'trade_id': 'legacy'}, {'event': 'close', 'trade_id': 'legacy'}],
    [opened(), {'event': 'close', 'trade_id': 'a'}],
    [opened(), closed()],
])
def test_valid_or_missing_legacy_copy_fields_preserve_bytes(tmp_path, records):
    j = journal(tmp_path)
    write_rows(j, records)
    before = j.journal_path.read_bytes()
    assert j.open_trade() is None
    assert json.loads(before.splitlines()[0]) == records[0]
    assert j.journal_path.read_bytes() == before



def test_fresh_process_rejects_conflict_without_inmemory_refusal_cache(tmp_path):
    j = journal(tmp_path)
    terminal = closed()
    terminal['side'] = 'NO'
    write_rows(j, [opened(), terminal])
    before = j.journal_path.read_bytes()
    code = """import sys
from pathlib import Path
import app.prediction.paper_engine as module
assert Path(module.__file__).resolve().is_relative_to(Path(sys.argv[3]).resolve())
j=module.PredictionPaperJournal(journal_path=Path(sys.argv[1]),candidate_path=Path(sys.argv[2]))
try:j.open_trade()
except module.PredictionPaperPersistenceError:
 print('REFUSED_FROM_RECORDED_EVIDENCE');sys.exit(0)
sys.exit(3)
"""
    import app.prediction.paper_engine as module
    result = subprocess.run([sys.executable, '-c', code, str(j.journal_path), str(j.candidate_path),
                             str(Path(module.__file__).resolve().parents[1])],
                            capture_output=True, text=True, timeout=15, env=os.environ.copy(), check=False)
    assert result.returncode == 0, result.stdout+result.stderr
    assert result.stdout.strip() == 'REFUSED_FROM_RECORDED_EVIDENCE'
    assert j.journal_path.read_bytes() == before
