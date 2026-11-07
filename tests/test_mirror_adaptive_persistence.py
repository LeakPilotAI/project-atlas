"""Temporary journals only: adaptive exit evidence must not fail silently."""
import asyncio

import app.services.perp_setup_paper_mirror as mirror_mod
import pytest
from test_r7e47r_durable_acknowledgements import source_module


@pytest.fixture
def journal(tmp_path):
    module = source_module("backend/app/services/paper_journal.py", "paper_journal")
    module.JOURNAL_PATH = tmp_path/"paper.jsonl"
    module.CANDIDATE_PATH = tmp_path/"candidates.jsonl"
    return module, module.PaperJournal()


def test_actual_adaptive_fsync_failure_reaches_mirror_caller(journal, tmp_path, monkeypatch):
    module, owner = journal
    identity = asyncio.run(owner.open_trade(
        symbol="BTC", side="LONG", entry=100, stop=95, tp1=105, tp2=110,
        source=mirror_mod.SOURCE, counts_for_live=False,
    ))
    mirror = mirror_mod.PerpSetupPaperMirror(pending_path=tmp_path/"pending.jsonl")
    mirror._seeded = mirror._terminal_cache_hydrated = True
    mirror._source_open_ids.add(identity)
    monkeypatch.setattr(mirror_mod, "paper_journal", owner)
    monkeypatch.setattr(mirror, "_fresh_mark_timestamp", lambda _: True)
    monkeypatch.setattr(mirror_mod, "evaluate_adaptive_exit", lambda *_: {
        "eligible":True, "working_stop":100, "working_target":110,
        "stage":"PROTECT", "policy_version":"synthetic", "evidence":{},
    })
    original = OSError("synthetic adaptive fsync failure")
    update = owner.update_excursion
    def fail(_descriptor):
        raise original
    def mark_then_fail(*args, **kwargs):
        update(*args, **kwargs)
        monkeypatch.setattr(module.os, "fsync", fail)
    monkeypatch.setattr(owner, "update_excursion", mark_then_fail)
    with pytest.raises(OSError) as caught:
        asyncio.run(mirror.sync([], {"BTC":101}))
    assert caught.value is original
    assert owner.first_fsync_error is original
    assert owner._open[identity].get("working_stop",95) == 95
    assert identity in mirror._source_open_ids

    from app.core.shutdown import ShutdownReport
    report = ShutdownReport(timeout=1, clock=lambda:0)
    async def shutdown_review():
        with pytest.raises(OSError) as repeated:
            await report.run("paper_review", lambda:mirror.sync([], {"BTC":101}))
        assert repeated.value is original
    asyncio.run(shutdown_review())
    report.sealed = True
    assert report.outcome == "INCOMPLETE"
    assert report.errors == [("paper_review",original)]
