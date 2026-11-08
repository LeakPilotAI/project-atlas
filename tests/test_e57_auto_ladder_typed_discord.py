import pytest
import app.alerts.discord as discord
import app.services.e48_discord_events as e48
from app.services.auto_ladder import AutoLadderService, PROTECTED

class FakeRedis:
    def __init__(self): self.data={}; self.order=[]
    async def get(self,k): return self.data.get(k)
    async def keys(self,p): return []
    async def set(self,k,v,**kw):
        self.order.append("set:"+k)
        if kw.get("nx") and k in self.data: return False
        self.data[k]=v; return True

@pytest.mark.asyncio
@pytest.mark.parametrize("send_result",[True,False])
async def test_typed_notify_keeps_creation_committed(monkeypatch,send_result):
    svc=AutoLadderService(); r=FakeRedis(); svc._redis=r
    e48._OBSERVATIONS.clear()
    monkeypatch.setattr(discord,"is_discord_ready",lambda:True)
    async def sender(**p): r.order.append("notify"); return send_result
    monkeypatch.setattr(discord,"send_discord_alert",sender)
    out=await svc.maybe_create_from_dip(symbol="ABC",price=100,name="ABC")
    assert out and await svc.already_created("ABC")
    assert r.order[0].startswith("set:atlas:auto_ladder:created:ABC")
    assert r.order[1].startswith("set:atlas:auto_ladder:def:ABC")
    assert r.order[2]=="notify"
    row=e48.delivery_observability()["observations"][-1]
    assert row["lane"]=="SYSTEM" and row["event_type"]=="SESSION"
    assert row["acknowledged"] is send_result
    assert e48.delivery_observability()["execution_authority"] is False

@pytest.mark.asyncio
async def test_typed_sender_exception_is_swallowed_after_creation(monkeypatch):
    svc=AutoLadderService(); r=FakeRedis(); svc._redis=r
    monkeypatch.setattr(discord,"is_discord_ready",lambda:True)
    async def sender(**p): raise RuntimeError("down")
    monkeypatch.setattr(discord,"send_discord_alert",sender)
    out=await svc.maybe_create_from_dip(symbol="XYZ",price=50,name="XYZ")
    assert out and await svc.already_created("XYZ")
    again=await svc.maybe_create_from_dip(symbol="XYZ",price=49,name="XYZ")
    assert again is None

@pytest.mark.asyncio
async def test_protected_core_still_never_auto_creates(monkeypatch):
    svc=AutoLadderService(); r=FakeRedis(); svc._redis=r
    for symbol in PROTECTED:
        assert await svc.maybe_create_from_dip(symbol=symbol,price=100,name=symbol) is None
    assert r.data=={}
