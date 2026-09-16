"""HTTP for Phase 6 paper validation. Read-only production controls; research endpoints never place orders."""
from __future__ import annotations
import json
from typing import Any, Dict
from fastapi import APIRouter
from fastapi.responses import JSONResponse
router=APIRouter(prefix="/api/validation",tags=["validation"])
def _json_http(body:Any,status_code:int=200)->JSONResponse:
    try:payload=json.loads(json.dumps(body,allow_nan=False,default=str))
    except Exception as e:payload={"ok":False,"error":f"serialize: {type(e).__name__}: {str(e)[:180]}","live_capital_allowed":False}
    return JSONResponse(content=payload,status_code=status_code)
def _clean_policy_guard_errors(body:Any)->Any:
    if not isinstance(body,dict):return body
    raw=list(body.get("section_errors") or []);guards=[x for x in raw if str(x).lower().startswith("redacted phrase guard:")];body["section_errors"]=[x for x in raw if x not in guards];body["policy_guard_activations"]=len(guards);body["diagnostics_healthy"]=bool(body.get("ok",True)) and not body["section_errors"];return body
@router.get("")
@router.get("/report")
async def validation_report()->Dict[str,Any]:
    from app.services.paper_validation import full_report
    return full_report()
@router.get("/summary")
async def validation_summary()->Dict[str,Any]:
    from app.services.paper_validation import readiness_report,uncertainty,load_paper_closes
    rows=load_paper_closes();rd=readiness_report(rows);return {"closed":rd["closed_trades"],"winrate":rd["observed_wr"],"expectancy":rd["observed_expectancy"],"total_r":rd["total_r"],"uncertainty":uncertainty(rows),"data_sufficiency":rd["data_sufficiency"],"statistical_stability":rd["statistical_stability"],"performance":rd["performance"],"risk":rd["risk"],"data_integrity":rd["data_integrity"],"conclusion":rd["conclusion"],"live_capital_allowed":False,"milestone":rd["milestone"]}
@router.get("/text")
async def validation_text_endpoint()->Dict[str,str]:
    from app.services.paper_validation import validation_text
    return {"text":validation_text()}
@router.get("/edge")
async def edge_endpoint()->JSONResponse:
    try:
        from app.services.edge_diagnostics import edge_report
        body=_clean_policy_guard_errors(edge_report())
    except Exception as e:body={"ok":False,"title":"ATLAS EDGE DIAGNOSTICS","error":f"{type(e).__name__}: {str(e)[:240]}","live_capital_allowed":False}
    return _json_http(body)
@router.get("/edge/text")
async def edge_text_endpoint()->JSONResponse:
    try:
        from app.services.edge_diagnostics import edge_text
        body={"text":edge_text()}
    except Exception as e:body={"text":f"ATLAS EDGE DIAGNOSTICS failed: {type(e).__name__}: {str(e)[:180]}"}
    return _json_http(body)
@router.get("/challengers")
async def challenger_lab_endpoint()->JSONResponse:
    try:
        from app.services.challenger_lab import challenger_report
        body=challenger_report()
    except Exception as e:body={"ok":False,"error":str(e)[:240],"production_strategy_modified":False,"live_capital_allowed":False,"automatic_real_money_execution":False}
    return _json_http(body)
@router.get("/challengers/prospective")
async def challenger_prospective_endpoint()->JSONResponse:
    try:
        from app.services.challenger_prospective import prospective_report
        body=prospective_report()
    except Exception as e:body={"ok":False,"error":str(e)[:240],"production_strategy_modified":False,"live_capital_allowed":False,"automatic_real_money_execution":False}
    return _json_http(body)
@router.get("/challengers/comparison")
async def challenger_comparison_endpoint()->JSONResponse:
    try:
        from app.services.v6_candidate_comparison import candidate_comparison
        body=candidate_comparison()
    except Exception as e:body={"ok":False,"title":"ATLAS V6 PROSPECTIVE CANDIDATE COMPARISON","error":str(e)[:240],"research_nominations":[],"trading_readiness":"NOT_READY","production_strategy_modified":False,"live_capital_allowed":False,"automatic_real_money_execution":False}
    return _json_http(body)
@router.get("/challengers/evidence-trends")
async def challenger_evidence_trends_endpoint()->JSONResponse:
    try:
        from app.services.v6_evidence_trends import evidence_trends
        body=evidence_trends()
    except Exception as e:body={"ok":False,"title":"ATLAS V6 EVIDENCE TRENDS","error":str(e)[:240],"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_promotion":False,"automatic_real_money_execution":False}
    return _json_http(body)
@router.get("/challengers/stability")
async def challenger_stability_endpoint()->JSONResponse:
    try:
        from app.services.v6_stability import stability_report
        body=stability_report()
    except Exception as e:body={"ok":False,"title":"ATLAS V6 MULTI-SNAPSHOT PROSPECTIVE STABILITY","error":str(e)[:240],"human_review_eligible":[],"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_promotion":False,"automatic_real_money_execution":False}
    return _json_http(body)
@router.get("/challengers/diversity")
async def challenger_diversity_endpoint()->JSONResponse:
    try:
        from app.services.v6_window_diversity import diversity_report
        body=diversity_report()
    except Exception as e:body={"ok":False,"title":"ATLAS V6 FORWARD WINDOW DIVERSITY","error":str(e)[:240],"diversity_established":[],"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_promotion":False,"automatic_real_money_execution":False}
    return _json_http(body)
@router.get("/challengers/diversity-trends")
async def challenger_diversity_trends_endpoint()->JSONResponse:
    try:
        from app.services.v6_diversity_trends import diversity_trends
        body=diversity_trends()
    except Exception as e:body={"ok":False,"title":"ATLAS V6 FORWARD DIVERSITY TRENDS","error":str(e)[:240],"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_promotion":False,"automatic_real_money_execution":False}
    return _json_http(body)
@router.get("/challengers/research-evidence")
async def challenger_research_evidence_endpoint()->JSONResponse:
    try:
        from app.services.v6_research_evidence_ui import research_evidence_ui
        body=research_evidence_ui()
    except Exception as e:body={"ok":False,"title":"ATLAS V6 RESEARCH EVIDENCE","error":str(e)[:240],"heavy_research_recompute":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_promotion":False,"automatic_real_money_execution":False}
    return _json_http(body)
@router.get("/challengers/exit-replay")
async def challenger_exit_replay_endpoint()->JSONResponse:
    try:
        from app.services.challenger_exit_replay import exit_replay_report
        body=exit_replay_report()
    except Exception as e:body={"ok":False,"error":str(e)[:240],"production_strategy_modified":False,"live_capital_allowed":False,"automatic_real_money_execution":False}
    return _json_http(body)
@router.get("/challengers/shadow-paper")
async def challenger_shadow_paper_endpoint()->JSONResponse:
    try:
        from app.services.shadow_paper_interactions import interaction_report
        body=interaction_report()
    except Exception as e:body={"ok":False,"error":str(e)[:240],"populations_pooled":False,"production_strategy_modified":False,"live_capital_allowed":False,"automatic_real_money_execution":False}
    return _json_http(body)
@router.get("/challengers/readiness")
async def challenger_readiness_endpoint()->JSONResponse:
    try:
        from app.services.v6_readiness_scorecard import readiness_scorecard
        body=readiness_scorecard()
    except Exception as e:body={"ok":False,"error":str(e)[:240],"research_evidence_ready":False,"trading_readiness":"NOT_READY","production_strategy_modified":False,"live_capital_allowed":False,"automatic_real_money_execution":False}
    return _json_http(body)
@router.get("/challengers/forward-monitor")
async def challenger_forward_monitor_status()->JSONResponse:
    try:
        from app.services.v6_forward_monitor import monitor_status
        body=monitor_status()
    except Exception as e:body={"ok":False,"error":str(e)[:240],"trading_readiness":"NOT_READY","live_capital_allowed":False}
    return _json_http(body)
@router.post("/challengers/forward-monitor/refresh")
async def challenger_forward_monitor_refresh()->JSONResponse:
    try:
        from app.services.v6_forward_monitor import refresh_forward_evidence
        body=refresh_forward_evidence()
    except Exception as e:body={"ok":False,"error":str(e)[:240],"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_promotion":False,"automatic_real_money_execution":False}
    return _json_http(body)