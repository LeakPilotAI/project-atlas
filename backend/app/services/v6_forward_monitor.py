"""Append-only longitudinal monitor for V6 research evidence.

Explicit refresh only. Never called by normal Command Center refresh and never
promotes production or unlocks live capital.
"""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from app.services.paper_journal import iter_jsonl

HISTORY_PATH=Path(__file__).resolve().parents[2]/"data"/"v6_forward_evidence_history.jsonl"

def _now()->str:return datetime.now(timezone.utc).isoformat()

def _compact(report:Dict[str,Any])->Dict[str,Any]:
    forward={}
    for name,row in (report.get("forward_evidence") or {}).items():
        forward[name]={k:row.get(k) for k in ("opened","closed","open","expectancy","expectancy_ci95","sample_sufficient","positive_expectancy","uncertainty_supports_positive_edge","research_evidence_ready")}
    return {"forward":forward,"exit_replay":dict(report.get("exit_replay") or {}),"shadow_paper":{"prospective_nomination_count":int((report.get("shadow_paper") or {}).get("prospective_nomination_count") or 0),"populations_pooled":bool((report.get("shadow_paper") or {}).get("populations_pooled",False))},"research_evidence_ready":bool(report.get("research_evidence_ready",False)),"trading_readiness":"NOT_READY","live_capital_allowed":False}

def _previous(path:Path)->Dict[str,Any]|None:
    last=None
    if path.exists():
        for row in iter_jsonl(path):
            if row.get("event")=="v6_forward_evidence_snapshot":last=row
    return last

def _deltas(current:Dict[str,Any],previous:Dict[str,Any]|None)->Dict[str,Any]:
    prev=(previous or {}).get("evidence") or {}; out={"forward":{}}
    for name,row in current.get("forward",{}).items():
        old=(prev.get("forward") or {}).get(name) or {}
        out["forward"][name]={"closed_delta":int(row.get("closed") or 0)-int(old.get("closed") or 0),"expectancy_delta":round(float(row.get("expectancy") or 0)-float(old.get("expectancy") or 0),6),"sample_sufficient_changed":bool(row.get("sample_sufficient"))!=bool(old.get("sample_sufficient")),"positive_ci_changed":bool(row.get("uncertainty_supports_positive_edge"))!=bool(old.get("uncertainty_supports_positive_edge"))}
    old_replay=(prev.get("exit_replay") or {}).get("path_coverage") or 0
    out["exit_replay_path_coverage_delta"]=round(float((current.get("exit_replay") or {}).get("path_coverage") or 0)-float(old_replay),6)
    out["nomination_count_delta"]=int((current.get("shadow_paper") or {}).get("prospective_nomination_count") or 0)-int((prev.get("shadow_paper") or {}).get("prospective_nomination_count") or 0)
    return out

def append_snapshot(report:Dict[str,Any],*,path:Path=HISTORY_PATH,timestamp:str|None=None)->Dict[str,Any]:
    evidence=_compact(report); previous=_previous(path); row={"event":"v6_forward_evidence_snapshot","timestamp":timestamp or _now(),"evidence":evidence,"deltas":_deltas(evidence,previous),"automatic_promotion":False,"production_strategy_modified":False,"automatic_real_money_execution":False}
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as f:
        f.write(json.dumps(row,allow_nan=False,default=str)+"\n");f.flush()
        try:os.fsync(f.fileno())
        except OSError:pass
    return row

def refresh_forward_evidence(*,path:Path=HISTORY_PATH)->Dict[str,Any]:
    from app.services.v6_readiness_scorecard import readiness_scorecard
    report=readiness_scorecard(); snapshot=append_snapshot(report,path=path)
    return {"ok":True,"title":"ATLAS V6 FORWARD EVIDENCE MONITOR","snapshot":snapshot,"history_path":str(path),"mode":"EXPLICIT_REFRESH_APPEND_ONLY","normal_command_center_recompute":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_promotion":False,"automatic_real_money_execution":False}

def monitor_status(*,path:Path=HISTORY_PATH)->Dict[str,Any]:
    rows=[r for r in iter_jsonl(path) if r.get("event")=="v6_forward_evidence_snapshot"] if path.exists() else []
    return {"snapshot_count":len(rows),"latest":rows[-1] if rows else None,"append_only":True,"trading_readiness":"NOT_READY","live_capital_allowed":False}
