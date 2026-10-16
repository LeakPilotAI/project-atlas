"""Inactive crypto research evidence normalization. No trading authority."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from app.investment.quality_dips_research_envelope import CRYPTO_EVIDENCE_DIMENSIONS

@dataclass(frozen=True)
class CryptoEvidenceItem:
    dimension: str
    value: Any
    source: str
    observed_at: str
    valid: bool
    reasons: tuple[str, ...]

def _timestamp(value: str) -> datetime | None:
    try:
        parsed=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None

def normalize_crypto_evidence(raw: dict[str, Any], *, as_of: str, max_age_seconds: int):
    now=_timestamp(as_of)
    if now is None or max_age_seconds < 0:
        raise ValueError("valid as_of and max age required")
    out={}
    for dimension in CRYPTO_EVIDENCE_DIMENSIONS:
        item=raw.get(dimension)
        reasons=[]
        if not isinstance(item, dict):
            item={}; reasons.append("MISSING")
        source=str(item.get("source") or "").strip()
        observed=str(item.get("observed_at") or "").strip()
        value=item.get("value")
        ts=_timestamp(observed)
        if not source: reasons.append("MISSING_SOURCE")
        if value is None: reasons.append("MISSING_VALUE")
        if ts is None: reasons.append("INVALID_TIMESTAMP")
        else:
            age=(now-ts.astimezone(timezone.utc)).total_seconds()
            if age < 0: reasons.append("FUTURE_TIMESTAMP")
            if age > max_age_seconds: reasons.append("STALE")
        out[dimension]=CryptoEvidenceItem(dimension,value,source,observed,not reasons,tuple(reasons))
    return out

def qualify_crypto_research_universe(*, symbol: str, allowlisted: bool, liquidity_qualified: bool):
    sym=str(symbol or "").upper().strip()
    reasons=[]
    if not sym: reasons.append("MISSING_SYMBOL")
    if not allowlisted: reasons.append("NOT_ALLOWLISTED")
    if not liquidity_qualified: reasons.append("LIQUIDITY_NOT_QUALIFIED")
    return {"symbol":sym,"eligible":not reasons,"reasons":reasons,
            "input_mode":"EXPLICIT_RESEARCH_ONLY","autonomous_discovery":False}

def prospective_crypto_evidence_record(*, symbol: str, observed_at: str, normalized):
    complete=set(normalized)==set(CRYPTO_EVIDENCE_DIMENSIONS)
    valid=complete and all(x.valid for x in normalized.values())
    return {
        "asset_class":"CRYPTO","symbol":str(symbol or "").upper().strip(),
        "observed_at":str(observed_at or ""),
        "evidence":{k:asdict(v) for k,v in normalized.items()},
        "evidence_complete":complete,"evidence_valid":valid,
        "prospective_only":True,"scoring_defined":False,"dip_state_defined":False,
        "can_emit_signal":False,"paper_entry_authority":False,"execution_authority":False,
        "strategy_selection_authority":False,"threshold_mutation_authority":False,
        "promotion_authority":False,"live_capital_allowed":False,
    }
