import pytest
from app.services.e30_evidence_maturity import evidence_view,transition_key,alert_evidence_transition_if_needed

def card(status="NOT_READY",b=0,c=0):
    arm=lambda n:{"closed_trades":n,"distinct_symbols":0,"forward_calendar_days":0,"expectancy_r_after_recorded_costs":None,"max_drawdown_r":None,"worst_trade_r":None,"setup_stop_rate":None,"avg_stop_overshoot_r":None,"avg_execution_slippage_bps":None}
    return {"status":status,"scorecard_version":"e29","challenger_version":"v1","freeze_start_utc":"freeze","baseline":arm(b),"challenger":arm(c),"minimum_evidence_gates":{}}

def test_view_is_read_only_and_truthful_zero():
    v=evidence_view(card()); assert v["status"]=="NOT_READY" and v["baseline"]["closed_trades"]==0
    assert v["promotion_allowed"] is False and v["live_capital_allowed"] is False

def test_transition_key_only_changes_at_meaningful_paired_milestones_or_state():
    assert transition_key(evidence_view(card(b=1,c=0)))=="NOT_READY|paired-close-milestone:0"
    assert transition_key(evidence_view(card(b=1,c=1)))=="NOT_READY|paired-close-milestone:1"
    assert transition_key(evidence_view(card(b=12,c=10)))=="NOT_READY|paired-close-milestone:10"
    assert transition_key(evidence_view(card(status="READY_FOR_GATE_EVALUATION",b=60,c=60)))=="READY_FOR_GATE_EVALUATION|paired-close-milestone:60"

@pytest.mark.asyncio
async def test_initial_zero_state_is_persisted_without_discord_spam(tmp_path):
    sent=[]
    async def sender(**kw): sent.append(kw); return True
    p=tmp_path/"state.json"; r=await alert_evidence_transition_if_needed(sender=sender,state_path=p,scorecard=card())
    assert r["reason"]=="INITIAL_ZERO_STATE" and sent==[]
    r2=await alert_evidence_transition_if_needed(sender=sender,state_path=p,scorecard=card())
    assert r2["reason"]=="UNCHANGED" and sent==[]

@pytest.mark.asyncio
async def test_milestone_alert_sends_once_and_never_claims_promotion(tmp_path):
    sent=[]
    async def sender(**kw): sent.append(kw); return True
    p=tmp_path/"state.json"; await alert_evidence_transition_if_needed(sender=sender,state_path=p,scorecard=card())
    r=await alert_evidence_transition_if_needed(sender=sender,state_path=p,scorecard=card(b=1,c=1))
    assert r["delivered"]==1 and len(sent)==1 and "no strategy promotion" in sent[0]["description"]
    r2=await alert_evidence_transition_if_needed(sender=sender,state_path=p,scorecard=card(b=2,c=1))
    assert r2["reason"]=="UNCHANGED" and len(sent)==1
