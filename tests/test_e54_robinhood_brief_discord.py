import pytest
import app.services.robinhood_brief as rh
import app.alerts.discord as discord
import app.services.e48_discord_events as e48

@pytest.mark.asyncio
async def test_e54_robinhood_brief_uses_typed_system_summary(monkeypatch):
    sent=[]
    e48._OBSERVATIONS.clear()
    monkeypatch.setattr(discord,"is_discord_ready",lambda:True)
    async def sender(**p): sent.append(p); return True
    monkeypatch.setattr(discord,"send_discord_alert",sender)
    svc=rh.RobinhoodBriefService()
    async def candidates(): return []
    monkeypatch.setattr(svc,"_fetch_candidates",candidates)
    await svc._send_brief()
    assert len(sent)==1 and sent[0]["symbol"]=="SYSTEM"
    assert sent[0]["title"]=="Atlas · Robinhood Brief · HOLD CASH BIAS"
    view=e48.delivery_observability()
    assert view["observations"][-1]["lane"]=="SYSTEM"
    assert view["observations"][-1]["event_type"]=="SESSION"
    assert view["execution_authority"] is False and view["live_capital_allowed"] is False

@pytest.mark.asyncio
async def test_e54_robinhood_false_send_is_not_acknowledged(monkeypatch):
    e48._OBSERVATIONS.clear()
    monkeypatch.setattr(discord,"is_discord_ready",lambda:True)
    async def sender(**p): return False
    monkeypatch.setattr(discord,"send_discord_alert",sender)
    svc=rh.RobinhoodBriefService()
    async def candidates(): return []
    monkeypatch.setattr(svc,"_fetch_candidates",candidates)
    await svc._send_brief()
    row=e48.delivery_observability()["observations"][-1]
    assert row["attempted"] is True and row["acknowledged"] is False and row["retryable"] is True

def test_e54_robinhood_scheduler_contract_stays_once_per_date():
    svc=rh.RobinhoodBriefService()
    assert svc._last_date is None
    assert svc.running is False

def test_e54_route_has_zero_trading_authority():
    event=e48.make_event(lane="SYSTEM",event_type="SESSION",severity="MEDIUM",title="brief",body="research only",identity="rh")
    route=e48.route(event)
    assert route["eligible"] is True
    for key in ("execution_authority","paper_entry_authority","strategy_mutation_authority","membership_mutation_authority","threshold_mutation_authority","promotion_authority","live_capital_allowed"):
        assert route[key] is False
