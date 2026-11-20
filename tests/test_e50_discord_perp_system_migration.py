import pytest
from datetime import datetime, timezone, timedelta
from app.services.perp_alert_delivery import deliver_alert_candidates
import app.services.paper_reconciliation_alert as rec
from app.services.e30_evidence_maturity import alert_evidence_transition_if_needed

def perp(**x):
 r={"setup_key":"BTC:LONG","symbol":"BTC","side":"LONG","tier":"PRIME","state":"PREPARE","score":90,
 "price":100000,"alert_eligible":True,"alert_reason":"<script>BUY NOW</script>","next_action":"Review only.",
 "levels":{"l1":99000,"l2":98000,"l3":97000,"stop":96000,"tp1":102000,"tp2":104000}}
 r.update(x);return r

@pytest.mark.asyncio
async def test_perp_typed_route_preserves_ack_only_after_success():
 sent=[];acked=[]
 async def sender(**p): sent.append(p);return True
 out=await deliver_alert_candidates([perp()],acknowledge=lambda k: acked.append(k) or True,sender=sender)
 assert out["delivered"]==1 and acked==["BTC:LONG"] and len(sent)==1
 assert sent[0]["symbol"]=="PERP_ALERT" and "<script>BUY NOW</script>" in sent[0]["description"]

@pytest.mark.asyncio
async def test_perp_failure_never_acknowledges():
 ack=[]
 async def sender(**p): return False
 out=await deliver_alert_candidates([perp()],acknowledge=lambda k: ack.append(k) or True,sender=sender)
 assert out["failed"]==1 and ack==[]

@pytest.mark.asyncio
async def test_system_reconciliation_typed_route_preserves_cooldown(monkeypatch):
 rec.reset_reconciliation_alert_state()
 monkeypatch.setattr(rec,"reconciliation_summary",lambda:{"reconciliation_ok":False,"duplicate_fill_count":1,"duplicate_fill_instances":["x"],"journal_currently_open":2})
 sent=[]
 async def sender(**p): sent.append(p);return True
 now=datetime.now(timezone.utc)
 a=await rec.alert_reconciliation_if_needed(sender=sender,now=now,cooldown_seconds=900)
 b=await rec.alert_reconciliation_if_needed(sender=sender,now=now+timedelta(seconds=1),cooldown_seconds=900)
 assert a["delivered"]==1 and b["suppressed"] is True and len(sent)==1 and sent[0]["symbol"]=="SYSTEM"

@pytest.mark.asyncio
async def test_e29_system_transition_durable_state_prevents_frequency_increase(tmp_path):
 score={"status":"READY","scorecard_version":"v","challenger_version":"c","freeze_start_utc":"x",
 "baseline":{"closed_trades":10,"distinct_symbols":8,"forward_calendar_days":14},
 "challenger":{"closed_trades":10,"distinct_symbols":8,"forward_calendar_days":14},"minimum_evidence_gates":{}}
 sent=[]
 async def sender(**p): sent.append(p);return True
 state=tmp_path/"s.json"
 a=await alert_evidence_transition_if_needed(sender=sender,state_path=state,scorecard=score)
 b=await alert_evidence_transition_if_needed(sender=sender,state_path=state,scorecard=score)
 assert a["delivered"]==1 and b["attempted"]==0 and len(sent)==1 and sent[0]["symbol"]=="SYSTEM"
