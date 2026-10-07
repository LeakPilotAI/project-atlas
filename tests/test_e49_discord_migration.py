import asyncio
from datetime import datetime, timezone
from app.prediction.eligible_alerts import deliver_prediction_eligible_alerts
from app.prediction.paper_engine import PredictionPaperJournal
from app.services.alpha_presentation import alert_new_alpha_events

def _pred():
    return {"eligible":True,"ticker":"KXTEST-A","side":"YES","score":88,"quantity_contracts":"10",
    "occurrence_datetime":"2026-10-02T18:00:00+00:00","flat_deadline":"2026-10-02T17:30:00+00:00",
    "strategy":"PRE_EVENT_RECENT_RECLAIM_V1","entry_fill":{"vwap_dollars":"0.42"},
    "current_quote":{"spread_dollars":"0.03"},"projected":{"net_edge_dollars_per_contract":"0.04"},"activity":{}}

def test_e49_prediction_durable_journal_survives_fresh_typed_state(tmp_path):
    journal=PredictionPaperJournal(journal_path=tmp_path/"paper.jsonl",candidate_path=tmp_path/"cand.jsonl")
    sent=[]
    async def sender(**p): sent.append(p); return True
    a=asyncio.run(deliver_prediction_eligible_alerts([_pred()],journal=journal,sender=sender))
    b=asyncio.run(deliver_prediction_eligible_alerts([_pred()],journal=journal,sender=sender))
    assert a["delivered"]==1 and b["deduped"]==1 and len(sent)==1

