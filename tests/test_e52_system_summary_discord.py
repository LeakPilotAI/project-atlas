import pytest
from types import SimpleNamespace
import app.services.micro_heartbeat as hbmod
import app.services.command_center as ccmod
import app.services.daily_paper_recap as drmod
import app.alerts.discord as discord

@pytest.mark.asyncio
async def test_e52_heartbeat_uses_typed_system_route(monkeypatch):
    sent=[]
    monkeypatch.setattr(discord,"is_discord_ready",lambda:True)
    async def sender(**p): sent.append(p); return True
    monkeypatch.setattr(discord,"send_discord_alert",sender)
    await hbmod.MicroHeartbeatService()._pulse()
    assert len(sent)==1 and sent[0]["symbol"]=="SYSTEM"
    assert sent[0]["title"]=="Atlas · Micro Heartbeat"

@pytest.mark.asyncio
async def test_e52_command_center_typed_send_preserves_false_result(monkeypatch):
    sent=[]
    monkeypatch.setattr(discord,"is_discord_ready",lambda:True)
    async def sender(**p): sent.append(p); return False
    monkeypatch.setattr(discord,"send_discord_alert",sender)
    monkeypatch.setattr(ccmod,"live_command_center_summary",lambda snapshot:{"perps":{},"investments":{}})
    monkeypatch.setattr(ccmod.perp_manual_service,"snapshot",lambda:{})
    await ccmod.CommandCenterService()._send()
    assert len(sent)==1 and sent[0]["symbol"]=="SYSTEM" and sent[0]["title"]=="Atlas · Morning Command Center"

@pytest.mark.asyncio
async def test_e52_daily_recap_typed_send_does_not_claim_success_on_failure(monkeypatch):
    sent=[]
    monkeypatch.setattr(discord,"is_discord_ready",lambda:True)
    async def sender(**p): sent.append(p); return False
    monkeypatch.setattr(discord,"send_discord_alert",sender)
    class J:
        async def stats_since(self,since): return {"wins":0,"losses":0,"sum_r":0,"closed":0,"open":0,"trades":[]}
        async def stats(self): return {"wins":0,"losses":0,"win_rate_pct":0,"sum_r":0}
    import app.services.paper_journal as pj
    monkeypatch.setattr(pj,"paper_journal",J())
    await drmod.DailyPaperRecapService()._send()
    assert len(sent)==1 and sent[0]["symbol"]=="SYSTEM" and sent[0]["title"]=="Atlas · Daily Paper Recap"

def test_e52_schedule_state_contracts_unchanged():
    assert ccmod.CommandCenterService()._last_date is None
    assert drmod.DailyPaperRecapService()._last_date is None
    assert hbmod.MicroHeartbeatService().scans==0
