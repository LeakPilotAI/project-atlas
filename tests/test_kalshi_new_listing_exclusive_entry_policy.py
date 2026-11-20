"""Protect the user-approved Kalshi NEW-LISTINGS-ONLY operational strategy.

Legacy generalized pre-event PAPER entry must be retired while public read
research and closing already-open PAPER journals remain available.
"""
import pytest
from fastapi import HTTPException

from app.api import prediction as api
from app.prediction import policy
from app.prediction.prediction_paper_automation import prediction_paper_automation


def test_target_policy_supersedes_legacy_pre_event_repricing():
    row=policy.policy_snapshot()
    assert row['target_paper_strategy']=='NEWLY_LISTED_SINGLE_YES_NO_PRICE_DISCOVERY_V1'
    assert row['legacy_repricing_paper_entry_enabled'] is False
    assert row['target_new_listing_paper_entry_commissioned'] is False
    assert row['verified_new_listing_required_for_future_paper_entry'] is True
    assert row['yes_no_single_leg_only'] is True
    assert row['early_price_discovery_repricing_only'] is True
    assert row['existing_general_pre_event_reclaim_signal_research_only'] is True
    assert row['combos_allowed'] is False
    assert row['parlays_allowed'] is False
    assert row['multivariate_allowed'] is False
    assert row['stacking_allowed'] is False
    assert row['max_concurrent_prediction_positions']==1
    assert row['live_execution'] is False


@pytest.mark.asyncio
@pytest.mark.parametrize('side',['YES','NO'])
async def test_old_paper_open_endpoint_refuses_before_network_or_journal(monkeypatch,side):
    async def no_network(*args,**kwargs):
        pytest.fail('LEGACY_KALSHI_PAPER_MUST_NOT_LOAD_PROVIDER')
    monkeypatch.setattr(api.kalshi_public,'get_market',no_network)
    monkeypatch.setattr(api.kalshi_public,'get_orderbook',no_network)
    monkeypatch.setattr(api.prediction_paper_journal,'open_from_evaluation',
                        lambda *args,**kwargs:pytest.fail('LEGACY_PAPER_JOURNAL_MUTATION'))
    monkeypatch.setattr(api.prediction_paper_journal,'log_candidate',
                        lambda *args,**kwargs:pytest.fail('LEGACY_CANDIDATE_MUTATION'))
    with pytest.raises(HTTPException) as exc:
        await api.prediction_paper_open('KX-OLD',side=side)
    assert exc.value.status_code==409
    assert exc.value.detail=='KALSHI_LEGACY_PAPER_ENTRY_RETIRED_NEW_LISTING_ONLY'


@pytest.mark.asyncio
async def test_public_kalshi_status_keeps_research_read_only():
    value=await api.prediction_status()
    assert value['provider_mode']=='PUBLIC_MARKET_DATA_ONLY'
    assert value['authenticated_provider_access'] is False
    assert value['order_submission'] is False
    assert value['strategy_policy']['target_new_listing_paper_entry_commissioned'] is False
    assert value['strategy_policy']['legacy_repricing_paper_entry_enabled'] is False


def test_legacy_automatic_paper_entry_remains_blocked():
    info=prediction_paper_automation.status()
    assert info['unattended_paper_open_enabled'] is False
    assert info['automatic_paper_position_opening'] is False
    assert info['unattended_paper_open_blocked'] is True


def test_old_entry_route_removed_not_old_exit_recovery():
    from pathlib import Path
    src=Path(api.__file__).read_text(encoding='utf-8')
    old_section=src.split('@router.post("/paper/open/{ticker}")',1)[1].split(
        '@router.post("/paper/close")',1)[0]
    assert 'KALSHI_LEGACY_PAPER_ENTRY_RETIRED_NEW_LISTING_ONLY' in old_section
    assert 'open_from_evaluation(' not in old_section
    assert 'log_candidate(' not in old_section
    assert '@router.post("/paper/close")' in src
