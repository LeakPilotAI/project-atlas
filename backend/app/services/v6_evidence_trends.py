"""Read-only trend surface over append-only V6 forward evidence snapshots."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
from app.services.paper_journal import iter_jsonl
from app.services.v6_forward_monitor import HISTORY_PATH


def _snapshots(path:Path)->list[Dict[str,Any]]:
    if not path.exists(): return []
    return [r for r in iter_jsonl(path) if r.get("event")=="v6_forward_evidence_snapshot"]


def _point(row:Dict[str,Any],name:str)->Dict[str,Any]:
    ev=row.get("evidence") or {}; f=(ev.get("forward") or {}).get(name) or {}; replay=ev.get("exit_replay") or {}; shadow=ev.get("shadow_paper") or {}
    return {"timestamp":row.get("timestamp"),"closed":int(f.get("closed") or 0),"expectancy":float(f.get("expectancy") or 0.0),"expectancy_ci95":f.get("expectancy_ci95"),"sample_sufficient":bool(f.get("sample_sufficient",False)),"positive_expectancy":bool(f.get("positive_expectancy",False)),"positive_lower_ci95":bool(f.get("uncertainty_supports_positive_edge",False)),"research_evidence_ready":bool(f.get("research_evidence_ready",False)),"replay_path_coverage":float(replay.get("path_coverage") or 0.0),"prospective_nomination_count":int(shadow.get("prospective_nomination_count") or 0)}


def evidence_trends(*,path:Path=HISTORY_PATH)->Dict[str,Any]:
    rows=_snapshots(path); names=[]
    for row in rows:
        for name in ((row.get("evidence") or {}).get("forward") or {}):
            if name not in names:names.append(name)
    series={name:[_point(row,name) for row in rows if name in (((row.get("evidence") or {}).get("forward") or {}))] for name in names}
    summary={}
    for name,points in series.items():
        first=points[0]; last=points[-1]
        summary[name]={"snapshot_count":len(points),"closed_first":first["closed"],"closed_latest":last["closed"],"closed_growth":last["closed"]-first["closed"],"expectancy_first":first["expectancy"],"expectancy_latest":last["expectancy"],"expectancy_change":round(last["expectancy"]-first["expectancy"],6),"positive_ci_transitions":sum(1 for a,b in zip(points,points[1:]) if a["positive_lower_ci95"]!=b["positive_lower_ci95"]),"sample_sufficiency_transitions":sum(1 for a,b in zip(points,points[1:]) if a["sample_sufficient"]!=b["sample_sufficient"])}
    latest=rows[-1] if rows else None
    return {"ok":True,"title":"ATLAS V6 EVIDENCE TRENDS","mode":"READ_ONLY_APPEND_ONLY_HISTORY","snapshot_count":len(rows),"series":series,"summary":summary,"latest_timestamp":latest.get("timestamp") if latest else None,"history_rewritten":False,"normal_command_center_recompute":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_promotion":False,"automatic_real_money_execution":False}
