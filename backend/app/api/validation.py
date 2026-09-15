"""HTTP for Phase 6 paper validation. Read-only production controls; research endpoints never place orders."""
from __future__ import annotations
import json
from typing import Any, Dict
from fastapi import APIRouter
from fastapi.responses import JSONResponse
router=APIRouter(prefix="/api/validation",tags=["validation"])

def _json_http(body:Any,status_code:int=200)->JSONResponse:
    try: payload=json.loads(json.dumps(body,allow_nan=False,default=str))
    except Exception as e: payload={"ok":False,"title":"ATLAS EDGE DIAGNOSTICS","error":f"serialize: {type(e).__name__}: {str(e)[:180]}","live_capital_allowed":False}
    return JSONResponse(content=payload,status_code=status_code)

def _clean_policy_guard_errors(body:Any)->Any:
    if not isinstance(body,dict): return body
    raw=list(body.get("section_errors") or []); guards=[x for x in raw if str(x).lower().startswith("redacted phrase guard:")]
    body["section_errors"]=[x for x in raw if x not in guards]; body["policy_guard_activations"]=len(guards); body["diagnostics_healthy"]=bool(body.get("ok",True)) and not body["section_errors"]
    return body

@router.get("")
@router.get("/report")
async def validation_report()->Dict[str,Any]:
    from app.services.paper_validation import full_report
    return full_report()
@router.get("/summary")
async def validation_summary()->Dict[str,Any]:
    from app.services.paper_validation import readiness_report,uncertainty,load_paper_closes
    rows=load_paper_closes(); rd=readiness_report(rows)
    return {"closed":rd["closed_trades"],"winrate":rd["observed_wr"],"expectancy":rd["observed_expectancy"],"total_r":rd["total_r"],"uncertainty":uncertainty(rows),"data_sufficiency":rd["data_sufficiency"],"statistical_stability":rd["statistical_stability"],"performance":rd["performance"],"risk":rd["risk"],"data_integrity":rd["data_integrity"],"conclusion":rd["conclusion"],"live_capital_allowed":False,"milestone":rd["milestone"]}
@router.get("/text")
async def validation_text_endpoint()->Dict[str,str]:
    from app.services.paper_validation import validation_text
    return {"text":validation_text()}
@router.get("/edge")
async def edge_endpoint()->JSONResponse:
    try:
        from app.services.edge_diagnostics import edge_report
        body=_clean_policy_guard_errors(edge_report())
    except Exception as e: body={"ok":False,"title":"ATLAS EDGE DIAGNOSTICS","error":f"{type(e).__name__}: {str(e)[:240]}","live_capital_allowed":False}
    return _json_http(body)
@router.get("/edge/text")
async def edge_text_endpoint()->JSONResponse:
    try:
        from app.services.edge_diagnostics import edge_text
        body={"text":edge_text()}
    except Exception as e: body={"text":f"ATLAS EDGE DIAGNOSTICS failed: {type(e).__name__}: {str(e)[:180]}"}
    return _json_http(body)
@router.get("/challengers")
async def challenger_lab_endpoint()->JSONResponse:
    try:
        from app.services.challenger_lab import challenger_report
        body=challenger_report()
    except Exception as e: body={"ok":False,"title":"ATLAS V6 CHALLENGER LAB","error":f"{type(e).__name__}: {str(e)[:240]}","production_strategy_modified":False,"live_capital_allowed":False,"automatic_real_money_execution":False}
    return _json_http(body)
@router.get("/challengers/prospective")
async def challenger_prospective_endpoint()->JSONResponse:
    try:
        from app.services.challenger_prospective import prospective_report
        body=prospective_report()
    except Exception as e: body={"ok":False,"title":"ATLAS V6 PROSPECTIVE CHALLENGER COHORT","error":f"{type(e).__name__}: {str(e)[:240]}","production_strategy_modified":False,"live_capital_allowed":False,"automatic_real_money_execution":False}
    return _json_http(body)
@router.get("/challengers/exit-replay")
async def challenger_exit_replay_endpoint()->JSONResponse:
    try:
        from app.services.challenger_exit_replay import exit_replay_report
        body=exit_replay_report()
    except Exception as e: body={"ok":False,"title":"ATLAS V6 POINT-IN-TIME EXIT REPLAY","error":f"{type(e).__name__}: {str(e)[:240]}","production_strategy_modified":False,"live_capital_allowed":False,"automatic_real_money_execution":False}
    return _json_http(body)
@router.get("/challengers/shadow-paper")
async def challenger_shadow_paper_endpoint()->JSONResponse:
    """Separate-population interaction research; never pools SHADOW and PAPER."""
    try:
        from app.services.shadow_paper_interactions import interaction_report
        body=interaction_report()
    except Exception as e: body={"ok":False,"title":"ATLAS V6 SHADOW-vs-PAPER INTERACTION DIAGNOSTICS","error":f"{type(e).__name__}: {str(e)[:240]}","populations_pooled":False,"production_strategy_modified":False,"live_capital_allowed":False,"automatic_real_money_execution":False}
    return _json_http(body)
