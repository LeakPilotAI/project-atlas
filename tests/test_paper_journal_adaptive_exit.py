import asyncio
import json

import app.services.paper_journal as journal_mod


def test_adaptive_exit_adjustment_is_append_only_and_recovers(tmp_path, monkeypatch):
    journal_path = tmp_path / "paper.jsonl"
    candidate_path = tmp_path / "candidates.jsonl"
    monkeypatch.setattr(journal_mod, "JOURNAL_PATH", journal_path)
    monkeypatch.setattr(journal_mod, "CANDIDATE_PATH", candidate_path)

    journal = journal_mod.PaperJournal()
    tid = asyncio.run(journal.open_trade(
        symbol="BTC",
        side="LONG",
        entry=100.0,
        stop=95.0,
        tp1=105.0,
        tp2=110.0,
        source="perp_manual_auto",
        strategy="test",
        features={"adaptive_exit_policy_version": "paper-exit-v1-evidence-protect"},
        counts_for_live=False,
        trade_type="PAPER",
    ))
    journal.update_excursion(tid, 103.0, force=True)
    changed = journal.note_adaptive_exit(
        tid,
        working_stop=100.5,
        working_target=110.0,
        stage="PROTECT",
        policy_version="paper-exit-v1-evidence-protect",
        reason="test evidence",
        evidence={"mfe_r": 0.6},
    )
    assert changed is True

    unchanged = journal.note_adaptive_exit(
        tid,
        working_stop=100.5,
        working_target=110.0,
        stage="PROTECT",
        policy_version="paper-exit-v1-evidence-protect",
        reason="same",
        evidence={"mfe_r": 0.6},
    )
    assert unchanged is False

    rows = [json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines()]
    adaptive_rows = [row for row in rows if row.get("adaptive_stage") == "PROTECT"]
    assert len(adaptive_rows) == 1
    assert adaptive_rows[0]["working_stop"] == 100.5
    assert adaptive_rows[0]["working_target"] == 110.0

    recovered = journal_mod.PaperJournal()
    open_row = next(row for row in recovered.list_open() if row["trade_id"] == tid)
    assert open_row["working_stop"] == 100.5
    assert open_row["working_target"] == 110.0
    assert open_row["adaptive_stage"] == "PROTECT"
    assert open_row["adaptive_exit_policy_version"] == "paper-exit-v1-evidence-protect"
