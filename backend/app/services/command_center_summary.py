"""Read-only cross-domain summary for Project Atlas. No orders or domain mixing."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Iterable
from app.investment.board import build_quality_dips_board
from app.investment.storage import OPPORTUNITIES_PATH, PLANS_PATH

def _load_jsonl(path:Path)->list[dict[str,Any]]:
    if not path.exists(): return []
    rows=[]
    with path.open("r",encoding="utf-8") as f:
        for line in f:
            try: row=json.loads(line.strip())
            except Exception: continue
            if isinstance(row,dict): rows.append(row)
    return rows

def _perp_summary(snapshot:dict[str,Any])->dict[str,Any]:
    setups=list(snapshot.get("setups") or []); plans=list(snapshot.get("plans") or []); auto=dict(snapshot.get("auto_paper") or {}); obs=dict(auto.get("observability") or {}); ph=dict(obs.get("pending_health") or {}); cc=dict(obs.get("clean_cohort") or {}); actionable={"PREPARE","L1_ACTIVE","L2_ACTIVE","L3_ACTIVE"}; top=setups[0] if setups else None
    return {"domain":"HYPERLIQUID_PERPS","source":"hyperliquid","execution":"MANUAL_ONLY","running":bool(snapshot.get("running")),"updated_at":snapshot.get("updated_at") or snapshot.get("last_refresh_at"),"market_count":int(snapshot.get("market_count") or 0),"setup_count":len(setups),"prime_count":sum(str(x.get("tier") or "")=="PRIME" for x in setups),"qualified_count":sum(str(x.get("tier") or "")=="QUALIFIED" for x in setups),"actionable_count":sum(str(x.get("state") or "") in actionable for x in setups),"entered_count":sum(str(x.get("status") or "")=="ENTERED" for x in plans),"auto_paper_pending_count":int(auto.get("pending_count") or 0),"auto_paper_open_count":int(auto.get("open_count") or 0),"auto_paper_opened_total":int(auto.get("opened_total") or 0),"auto_paper_closed_total":int(auto.get("closed_total") or 0),"auto_paper_included_in_journal":bool(auto.get("included_in_paper_journal",False)),"auto_paper_pending_health":{"currently_backed":int(ph.get("currently_backed") or 0),"not_in_current_snapshot":int(ph.get("not_in_current_snapshot") or 0),"oldest_pending_age_hours":ph.get("oldest_pending_age_hours"),"review_recommended":bool(ph.get("review_recommended")),"age_buckets":dict(ph.get("age_buckets") or {})},"auto_paper_clean_cohort":{"cohort":cc.get("cohort"),"started_at":cc.get("started_at"),"opened":int(cc.get("opened") or 0),"closed":int(cc.get("closed") or 0),"open":int(cc.get("open") or 0)},"alert_candidate_count":len(snapshot.get("alert_candidates") or []),"top_setup":None if top is None else {"symbol":top.get("symbol"),"side":top.get("side"),"tier":top.get("tier"),"state":top.get("state"),"score":top.get("score"),"next_action":top.get("next_action")},"last_error":snapshot.get("last_error"),"note":"Hyperliquid manual research with automatic PAPER mirroring of each verified resting-L1 instruction. PAPER opens only after an L1 touch/cross. No real order is placed."}

def _investment_summary(board:Iterable[dict[str,Any]])->dict[str,Any]:
    rows=list(board); counts={"ACCUMULATE":0,"PREPARE":0,"WATCH":0,"STAND_DOWN":0}
    for row in rows:
        stance=str(row.get("stance") or "WATCH"); counts[stance]=counts.get(stance,0)+1
    top=rows[0] if rows else None
    return {"domain":"EQUITY_INVESTMENT","source":"investment_research_store","execution":"MANUAL_ONLY","asset_count":len(rows),"counts":counts,"top_opportunity":None if top is None else {"symbol":top.get("symbol"),"asset_type":top.get("asset_type"),"stance":top.get("stance"),"classification":top.get("classification"),"opportunity_score":top.get("opportunity_score"),"evidence_quality":top.get("evidence_quality"),"thesis":top.get("thesis"),"ladder_eligible":bool(top.get("ladder_eligible"))},"note":"Stock/ETF-only investment research. No perp state included."}

def build_command_center_summary(perp_snapshot:dict[str,Any],research_rows:Iterable[dict[str,Any]],plan_rows:Iterable[dict[str,Any]]=(),*,v6_status:dict[str,Any]|None=None)->dict[str,Any]:
    board=build_quality_dips_board(research_rows,plan_rows,limit=100)
    if v6_status is None:
        from app.services.v6_research_status import research_status
        v6_status=research_status()
    return {"domain":"ORCHESTRATION","mode":"READ_ONLY","execution":"NO_ORDER_ACTIONS","perps":_perp_summary(perp_snapshot),"investments":_investment_summary(board),"research":v6_status,"guardrails":{"shared_symbols":False,"shared_capital_assumptions":False,"shared_performance":False,"shared_action_logic":False},"research_guardrails":{"research_is_trading_readiness":False,"automatic_promotion":False,"live_capital_allowed":False},"note":"Command Center observes domains and research status without combining risk, capital, scores, performance, or execution logic."}

def live_command_center_summary(perp_snapshot:dict[str,Any])->dict[str,Any]:
    return build_command_center_summary(perp_snapshot,_load_jsonl(OPPORTUNITIES_PATH),_load_jsonl(PLANS_PATH))
