"""Keep superseded Kalshi engine out of Atlas default boot while preserving Stop.

Source-only regression: native selected R12 is a separate installed release.
"""
import ast
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api import prediction as api
from app.prediction.policy import policy_snapshot

ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT/'backend/app/main.py'


def test_boot_registry_excludes_superseded_prediction_scanner():
    tree=ast.parse(MAIN.read_text(encoding='utf-8'))
    starts=[]
    stops=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name):
            if node.value.id=='prediction_paper_automation':
                if node.attr=='start':
                    starts.append(node.lineno)
                if node.attr=='stop':
                    stops.append(node.lineno)
    assert starts==[],('LEGACY_AUTO_START_STILL_REGISTERED',starts)
    assert len(stops)==1,'STOP_CLEANUP_FOR_PREEXISTING_LEGACY_WORKER_LOST'


@pytest.mark.asyncio
async def test_old_entry_refuses_and_cannot_make_provider_calls(monkeypatch):
    async def no_provider(*args,**kwargs):
        pytest.fail('LEGACY_PAPER_ENTRY_MUST_NOT_CONNECT_KALSHI')
    monkeypatch.setattr(api.kalshi_public,'get_market',no_provider)
    monkeypatch.setattr(api.kalshi_public,'get_orderbook',no_provider)
    monkeypatch.setattr(api.prediction_paper_journal,'open_from_evaluation',
                        lambda *args,**kwargs:pytest.fail('LEGACY_PAPER_ENTRY_MUST_NOT_WRITE'))
    with pytest.raises(HTTPException) as exc:
        await api.prediction_paper_open('KX-OLDER')
    assert exc.value.status_code==409
    assert exc.value.detail=='KALSHI_LEGACY_PAPER_ENTRY_RETIRED_NEW_LISTING_ONLY'


def test_no_alternative_authorized_paper_strategy_default():
    policy=policy_snapshot()
    assert policy['target_paper_strategy']=='NEWLY_LISTED_SINGLE_YES_NO_PRICE_DISCOVERY_V1'
    assert policy['legacy_repricing_paper_entry_enabled'] is False
    assert policy['target_new_listing_paper_entry_commissioned'] is False
    assert policy['verified_new_listing_required_for_future_paper_entry'] is True
    assert policy['live_execution'] is False
    assert policy['parlays_allowed'] is False
    assert policy['multivariate_allowed'] is False


def test_read_only_kalshi_and_close_recovery_routes_preserved():
    body=(ROOT/'backend/app/api/prediction.py').read_text(encoding='utf-8')
    assert '@router.get("/markets")' in body
    assert '@router.get("/markets/{ticker}")' in body
    assert '@router.post("/paper/close")' in body


def test_application_owned_legacy_prediction_paper_journal_refuses_direct_bypass(monkeypatch):
    from app.prediction import paper_engine
    app_journal=paper_engine.prediction_paper_journal
    monkeypatch.setattr(app_journal,'open_trade',
        lambda *args,**kwargs:pytest.fail('OLD_JOURNAL_MUST_NOT_READ_POSITIONS_FOR_ENTRY'))
    monkeypatch.setattr(app_journal,'_append',
        lambda *args,**kwargs:pytest.fail('OLD_JOURNAL_MUST_NOT_APPEND_PAPER_ENTRY'))
    for requested in ({'eligible':True,'strategy':'PRE_EVENT_RECENT_RECLAIM_V1'},
                      {'eligible':True,'strategy':'NEWLY_LISTED_SINGLE_YES_NO_PRICE_DISCOVERY_V1'}):
        with pytest.raises(paper_engine.PredictionPaperError,
                           match='KALSHI_LEGACY_PAPER_JOURNAL_ENTRY_RETIRED'):
            app_journal.open_from_evaluation(requested)


def test_disposable_legacy_paper_engine_remains_test_only(tmp_path):
    from app.prediction import paper_engine
    isolated=paper_engine.PredictionPaperJournal(
        journal_path=tmp_path/'isolated-paper.jsonl',
        candidate_path=tmp_path/'isolated-candidates.jsonl')
    assert isolated is not paper_engine.prediction_paper_journal
    with pytest.raises(paper_engine.PredictionPaperError,
                       match='candidate is not eligible'):
        isolated.open_from_evaluation({'eligible':False})
    assert not (tmp_path/'isolated-paper.jsonl').exists()
