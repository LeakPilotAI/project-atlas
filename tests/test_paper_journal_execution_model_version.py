import asyncio
import json

import app.services.paper_journal as journal_mod
from app.services.paper_execution_model import PAPER_EXECUTION_MODEL_VERSION


def test_paper_open_stamps_execution_model_version(monkeypatch, tmp_path):
    journal_path = tmp_path / "paper.jsonl"
    candidate_path = tmp_path / "candidates.jsonl"
    monkeypatch.setattr(journal_mod, "JOURNAL_PATH", journal_path)
    monkeypatch.setattr(journal_mod, "CANDIDATE_PATH", candidate_path)

    journal = journal_mod.PaperJournal()
    asyncio.run(journal.open_trade(
        symbol="BTC",
        side="LONG",
        entry=100.0,
        stop=99.0,
        tp1=101.0,
        tp2=102.0,
        features={"setup_rr": 1.8},
    ))
    row = json.loads(journal_path.read_text(encoding="utf-8").splitlines()[0])
    assert row["features"]["paper_execution_model_version"] == PAPER_EXECUTION_MODEL_VERSION
