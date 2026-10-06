"""Execution 30 read-only evidence maturity surface + transition alerts."""
from __future__ import annotations
import json, os
from pathlib import Path
from app.alerts.discord import send_discord_alert
from app.services.e29_forward_scorecard import e29_forward_scorecard
STATE_PATH=Path(__file__).resolve().parents[2]/"data"/"e30_evidence_maturity_state.json"
MILESTONES=(1,10,25,50,60)

def evidence_view(scorecard):
    b=scorecard.get("baseline") or {}; c=scorecard.get("challenger") or {}
    return {"status":scorecard.get("status") or "NOT_READY","scorecard_version":scorecard.get("scorecard_version"),"challenger_version":scorecard.get("challenger_version"),"freeze_start_utc":scorecard.get("freeze_start_utc"),"baseline":b,"challenger":c,"minimum_evidence_gates":scorecard.get("minimum_evidence_gates") or {},"promotion_allowed":False,"paper_research_only":True,"live_capital_allowed":False,"automatic_real_money_execution":False}

def transition_key(view):
    b=int((view.get("baseline") or {}).get("closed_trades") or 0); c=int((view.get("challenger") or {}).get("closed_trades") or 0)
    crossed=max((m for m in MILESTONES if min(b,c)>=m),default=0)
    return f"{view.get('status')}|paired-close-milestone:{crossed}"

def build_evidence_alert(view):
    b=view["baseline"]; c=view["challenger"]
    desc=(f"**Forward PAPER evidence maturity: {view['status']}**\nBaseline closes {b.get('closed_trades',0)}/60 | challenger closes {c.get('closed_trades',0)}/60\nSymbols {b.get('distinct_symbols',0)}/8 baseline | {c.get('distinct_symbols',0)}/8 challenger\nForward days {b.get('forward_calendar_days',0)}/14 baseline | {c.get('forward_calendar_days',0)}/14 challenger\nChallenger {view.get('challenger_version')}\nFreeze {view.get('freeze_start_utc')}\n\n_Evidence status only. PAPER research; no strategy promotion or live order authority._")
    return {"symbol":"PERPS-EVIDENCE","title":"Atlas Perps Evidence Maturity","description":desc,"price":0.0,"severity":"INFO","opportunity":0,"confidence":0,"risk":0}

def _load_state(path):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except Exception:return {}

def _save_state(path,state):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(".tmp"); tmp.write_text(json.dumps(state,sort_keys=True),encoding="utf-8"); os.replace(tmp,path)

async def alert_evidence_transition_if_needed(*,sender=send_discord_alert,state_path=STATE_PATH,scorecard=None):
    view=evidence_view(scorecard or e29_forward_scorecard()); key=transition_key(view); old=_load_state(state_path).get("last_delivered_key")
    if key==old:return {"attempted":0,"delivered":0,"transition_key":key,"reason":"UNCHANGED"}
    if old is None and key=="NOT_READY|paired-close-milestone:0":
        _save_state(state_path,{"last_delivered_key":key}); return {"attempted":0,"delivered":0,"transition_key":key,"reason":"INITIAL_ZERO_STATE"}
    ok=bool(await sender(**build_evidence_alert(view)))
    if ok:_save_state(state_path,{"last_delivered_key":key})
    return {"attempted":1,"delivered":int(ok),"transition_key":key,"reason":"DELIVERED" if ok else "SEND_FAILED"}
