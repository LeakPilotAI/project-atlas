import pytest
import app.alerts.discord as discord
import app.services.e48_discord_events as e48
import app.main as main

@pytest.mark.asyncio
async def test_session_announcement_typed_once_per_invocation(monkeypatch):
    calls=[]
    e48._OBSERVATIONS.clear()
    async def no_sleep(_): return None
    monkeypatch.setattr(main.asyncio,"sleep",no_sleep)
    monkeypatch.setattr(discord,"is_discord_ready",lambda:True)
    async def sender(**payload): calls.append(payload); return True
    monkeypatch.setattr(discord,"send_discord_alert",sender)
    await main._announce_session({"session_id":"S58","prior_closed_archived":2,"rolled_open":[]})
    assert len(calls)==1
    obs=e48.delivery_observability()
    row=obs["observations"][-1]
    assert row["lane"]=="SYSTEM" and row["event_type"]=="SESSION"
    assert row["acknowledged"] is True
    assert obs["execution_authority"] is False
    assert "description" not in row and "title" not in row

@pytest.mark.asyncio
async def test_session_announcement_not_ready_sends_nothing(monkeypatch):
    calls=[]
    async def no_sleep(_): return None
    monkeypatch.setattr(main.asyncio,"sleep",no_sleep)
    monkeypatch.setattr(discord,"is_discord_ready",lambda:False)
    async def sender(**payload): calls.append(payload); return True
    monkeypatch.setattr(discord,"send_discord_alert",sender)
    await main._announce_session({"session_id":"S58"})
    assert calls==[]

def test_manual_diagnostics_is_explicitly_operator_triggered():
    from app.api.diagnostics import router
    routes=[r for r in router.routes if getattr(r,"path",None)=="/diagnostics/paper-test"]
    assert routes
    methods=set().union(*(r.methods for r in routes))
    assert {"GET","POST"}.issubset(methods)
