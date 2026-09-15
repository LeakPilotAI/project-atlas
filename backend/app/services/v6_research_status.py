"""Lightweight Command Center status for V6 research infrastructure.

No historical challenger/edge recomputation occurs during normal refresh. Durable
forward membership and optional cached scorecard state are summarized only.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Optional
from app.services.challenger_prospective import MARKER_PATH, MEMBERSHIP_PATH, COHORT_NAME
from app.services.paper_journal import iter_jsonl

SCORECARD_CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "v6_readiness_scorecard_cache.json"
TARGET_FORWARD_CLOSED = 100
TARGET_REPLAY_COVERAGE = 0.70


def _json(path:Path)->Optional[dict[str,Any]]:
    if not path.exists(): return None
    try:
        row=json.loads(path.read_text(encoding="utf-8")); return row if isinstance(row,dict) else None
    except Exception: return None


def _membership_counts(path:Path)->dict[str,Any]:
    unique={}
    if path.exists():
        for row in iter_jsonl(path):
            if row.get("event")=="membership" and row.get("trade_id"): unique[str(row["trade_id"])]=row
    by={"trend_regime":0,"extension_3pct":0,"quality_85":0,"trend_extension_quality":0}
    for row in unique.values():
        for name in row.get("challengers") or []:
            if name in by: by[name]+=1
    return {"unique_memberships":len(unique),"by_challenger":by}


def _progress(cache:Optional[dict[str,Any]], counts:dict[str,Any])->dict[str,Any]:
    cache=cache or {}; forward=cache.get("forward_evidence") if isinstance(cache.get("forward_evidence"),dict) else {}
    rows={}
    for name,opened in counts.get("by_challenger",{}).items():
        ev=forward.get(name) if isinstance(forward.get(name),dict) else {}
        closed=int(ev.get("closed") or 0)
        rows[name]={"opened":int(opened or 0),"closed":closed,"target_closed":TARGET_FORWARD_CLOSED,"closed_progress":round(min(1.0,closed/TARGET_FORWARD_CLOSED),4),"positive_expectancy":bool(ev.get("positive_expectancy",False)),"positive_lower_ci95":bool(ev.get("uncertainty_supports_positive_edge",False)),"research_evidence_ready":bool(ev.get("research_evidence_ready",False))}
    replay=cache.get("exit_replay") if isinstance(cache.get("exit_replay"),dict) else {}
    coverage=float(replay.get("path_coverage") or 0.0)
    shadow=cache.get("shadow_paper") if isinstance(cache.get("shadow_paper"),dict) else {}
    return {"source":"CACHED_SCORECARD" if cache else "DURABLE_MEMBERSHIP_ONLY","forward":rows,"exit_replay":{"path_coverage":coverage,"target_path_coverage":TARGET_REPLAY_COVERAGE,"coverage_progress":round(min(1.0,coverage/TARGET_REPLAY_COVERAGE),4),"coverage_sufficient":bool(replay.get("coverage_sufficient",False))},"shadow_paper":{"prospective_nomination_count":int(shadow.get("prospective_nomination_count") or 0),"populations_pooled":bool(shadow.get("populations_pooled",False))},"research_evidence_ready":bool(cache.get("research_evidence_ready",False)),"trading_readiness":"NOT_READY","live_capital_allowed":False}


def research_status(*,marker_path:Path=MARKER_PATH,membership_path:Path=MEMBERSHIP_PATH,scorecard_cache_path:Path=SCORECARD_CACHE_PATH)->dict[str,Any]:
    marker=_json(marker_path); counts=_membership_counts(membership_path); cache=_json(scorecard_cache_path)
    return {"domain":"V6_RESEARCH","mode":"READ_ONLY_STATUS","heavy_retrospective_recompute":False,"services":{"challenger_lab":True,"prospective_cohort":True,"point_in_time_exit_replay":True,"shadow_paper_interactions":True,"readiness_scorecard":True},"prospective":{"cohort":(marker or {}).get("cohort") or COHORT_NAME,"started_at":(marker or {}).get("started_at"),"initialized":bool(marker),**counts},"readiness_progress":_progress(cache,counts),"research_collection_healthy":bool(marker),"research_health_meaning":"Infrastructure/cutoff status only; not evidence of positive expectancy.","trading_readiness":"NOT_READY","stable_positive_expectancy_established":False,"automatic_promotion":False,"production_strategy_modified":False,"live_capital_allowed":False,"automatic_real_money_execution":False}
