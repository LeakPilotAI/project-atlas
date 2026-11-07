import pytest
import app.alerts.discord as discord
from app.services.accumulation_ladder import AccumulationLadderService
from app.services.btc_accumulation import BtcAccumulationService
from app.services.auto_ladder import AutoLadderService
from app.investment.quality_dips_v3_delivery import deliver_v3_events
from app.investment.quality_dips_v3_state import QualityDipsV3StateStore

@pytest.mark.asyncio
@pytest.mark.parametrize("kind,expected", [("NEAR",["send","mark:NEAR"]),("HIT",["send","mark:HIT","mark:NEAR"])])
async def test_stock_send_success_precedes_marks(monkeypatch,kind,expected):
    svc=AccumulationLadderService(); order=[]
    monkeypatch.setattr(discord,"is_discord_ready",lambda:True)
    async def sender(**p): order.append("send"); return True
    monkeypatch.setattr(discord,"send_discord_alert",sender)
    async def sent(*a): return False
    async def merged(): return {"MSFT":[(100.0,200.0),(90.0,250.0)]}
    async def mark(symbol,level,k): order.append("mark:"+k)
    monkeypatch.setattr(svc,"_sent",sent); monkeypatch.setattr(svc,"_merged_ladders",merged); monkeypatch.setattr(svc,"_mark",mark)
    assert await svc._send(symbol="MSFT",level=100,amount=200,price=99,kind=kind,level_index=1,total_levels=2)
    assert order==expected

@pytest.mark.asyncio
async def test_stock_failed_send_never_marks(monkeypatch):
    svc=AccumulationLadderService(); marks=[]
    monkeypatch.setattr(discord,"is_discord_ready",lambda:True)
    async def sender(**p): return False
    monkeypatch.setattr(discord,"send_discord_alert",sender)
    async def sent(*a): return False
    async def merged(): return {"MSFT":[(100.0,200.0)]}
    async def mark(*a): marks.append(a)
    monkeypatch.setattr(svc,"_sent",sent); monkeypatch.setattr(svc,"_merged_ladders",merged); monkeypatch.setattr(svc,"_mark",mark)
    assert not await svc._send(symbol="MSFT",level=100,amount=200,price=99,kind="HIT",level_index=1,total_levels=1)
    assert marks==[]

@pytest.mark.asyncio
async def test_btc_success_marks_hit_then_near_and_failure_marks_nothing(monkeypatch):
    svc=BtcAccumulationService(); order=[]
    monkeypatch.setattr(discord,"is_discord_ready",lambda:True)
    async def sent(*a): return False
    async def mark(level,k): order.append("mark:"+k)
    monkeypatch.setattr(svc,"_sent",sent); monkeypatch.setattr(svc,"_mark",mark)
    async def ok(**p): order.append("send"); return True
    monkeypatch.setattr(discord,"send_discord_alert",ok)
    assert await svc._send(level=60000,amount=300,price=59000,kind="HIT",level_index=1,total=7)
    assert order==["send","mark:HIT","mark:NEAR"]
    order.clear()
    async def fail(**p): order.append("send"); return False
    monkeypatch.setattr(discord,"send_discord_alert",fail)
    assert not await svc._send(level=56000,amount=400,price=55000,kind="HIT",level_index=2,total=7)
    assert order==["send"]

@pytest.mark.asyncio
async def test_btc_63500_suppression_marks_without_notification(monkeypatch):
    svc=BtcAccumulationService(); marks=[]; sends=[]
    monkeypatch.setattr(discord,"is_discord_ready",lambda:True)
    async def sender(**p): sends.append(p); return True
    monkeypatch.setattr(discord,"send_discord_alert",sender)
    async def mark(level,k): marks.append(k)
    monkeypatch.setattr(svc,"_mark",mark)
    assert not await svc._send(level=63500,amount=1,price=63000,kind="HIT",level_index=1,total=1)
    assert sends==[] and marks==["HIT","NEAR"]

@pytest.mark.asyncio
async def test_quality_dips_failed_delivery_retries_durably(tmp_path):
    store=QualityDipsV3StateStore(tmp_path/"v3.json")
    event={"key":"V3:ABC:LEVEL:L1","event_type":"ENTRY_LEVEL_REACHED","symbol":"ABC","message":"research"}
    store.mark_event(event["key"],symbol="ABC",event_type=event["event_type"],payload=event)
    calls=[]
    async def fail(**p): calls.append("fail"); return False
    async def ok(**p): calls.append("ok"); return True
    assert (await deliver_v3_events([event],store=store,sender=fail))["failed"]==1
    assert store.get_event(event["key"])["delivery"]["delivered"] is False
    assert (await deliver_v3_events([event],store=store,sender=ok))["delivered"]==1
    assert store.get_event(event["key"])["delivery"]["attempts"]==2

class FakeRedis:
    def __init__(self): self.data={}; self.order=[]
    async def get(self,k): return self.data.get(k)
    async def keys(self,p): return []
    async def set(self,k,v,**kw):
        self.order.append("set:"+k)
        if kw.get("nx") and k in self.data: return False
        self.data[k]=v; return True

@pytest.mark.asyncio
async def test_auto_ladder_persists_creation_before_notification_failure(monkeypatch):
    svc=AutoLadderService(); r=FakeRedis(); svc._redis=r; order=r.order
    async def notify(**kw): order.append("notify"); raise RuntimeError("discord down")
    monkeypatch.setattr(svc,"_notify_created",notify)
    with pytest.raises(RuntimeError):
        await svc.maybe_create_from_dip(symbol="ABC",price=100,name="ABC")
    assert order[0].startswith("set:atlas:auto_ladder:created:ABC")
    assert order[1].startswith("set:atlas:auto_ladder:def:ABC")
    assert order[2]=="notify"
    assert await svc.already_created("ABC") is True
