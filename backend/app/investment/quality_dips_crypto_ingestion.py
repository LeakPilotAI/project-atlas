"""Manual/operator-only prospective Crypto Quality Dips evidence ingestion."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from app.investment.quality_dips_crypto_evidence import normalize_crypto_evidence, prospective_crypto_evidence_record, qualify_crypto_research_universe
from app.investment.quality_dips_crypto_store import CryptoProspectiveEvidenceStore

@dataclass(frozen=True)
class IngestionResult:
    accepted: bool
    persisted: bool
    duplicate: bool
    reasons: tuple[str,...]
    execution_authority: bool=False
    paper_entry_authority: bool=False
    strategy_mutation_authority: bool=False
    threshold_mutation_authority: bool=False
    promotion_authority: bool=False
    live_capital_allowed: bool=False

class ManualCryptoEvidenceIngestion:
    def __init__(self,store: CryptoProspectiveEvidenceStore):
        self.store=store
        self.counters={"attempted":0,"accepted":0,"persisted":0,"duplicate":0,"rejected":0}
        self.audit={"operator_attempts":0,"intent_rejections":0,"integrity_rejections":0,"last_result":"NONE","last_reasons":[]}

    def ingest(self,*,symbol:str,allowlisted:bool,liquidity_qualified:bool,raw_evidence:dict[str,Any],observed_at:str,max_age_seconds:int):
        self.counters["attempted"]+=1
        qualification=qualify_crypto_research_universe(symbol=symbol,allowlisted=allowlisted,liquidity_qualified=liquidity_qualified)
        if not qualification["eligible"]:
            self.counters["rejected"]+=1
            return IngestionResult(False,False,False,tuple(qualification["reasons"]))
        try:
            normalized=normalize_crypto_evidence(raw_evidence,as_of=observed_at,max_age_seconds=max_age_seconds)
        except ValueError as exc:
            self.counters["rejected"]+=1
            return IngestionResult(False,False,False,(str(exc),))
        record=prospective_crypto_evidence_record(symbol=qualification["symbol"],observed_at=observed_at,normalized=normalized)
        if not record["evidence_complete"] or not record["evidence_valid"]:
            reasons=[]
            for item in normalized.values():
                reasons.extend(item.reasons)
            self.counters["rejected"]+=1
            return IngestionResult(False,False,False,tuple(sorted(set(reasons))))
        self.counters["accepted"]+=1
        persisted=self.store.append(record)
        self.counters["persisted" if persisted else "duplicate"]+=1
        return IngestionResult(True,persisted,not persisted,())

    def observability(self):
        return {**self.counters,"audit":dict(self.audit),"read_only":True,"raw_evidence_retained":False,"outcomes_inferred":False,"performance_inferred":False,"execution_authority":False,"paper_entry_authority":False,"strategy_mutation_authority":False,"threshold_mutation_authority":False,"promotion_authority":False,"live_capital_allowed":False}


def invoke_operator_ingestion(service: ManualCryptoEvidenceIngestion, *, operator_intent: bool, **submission):
    """Local operator-only invocation boundary; not an HTTP route."""
    service.audit["operator_attempts"]+=1
    if operator_intent is not True:
        service.audit.update(intent_rejections=service.audit["intent_rejections"]+1,last_result="REJECTED",last_reasons=["EXPLICIT_OPERATOR_INTENT_REQUIRED"])
        return IngestionResult(False,False,False,("EXPLICIT_OPERATOR_INTENT_REQUIRED",))
    if not service.store.integrity["ok"]:
        service.audit.update(integrity_rejections=service.audit["integrity_rejections"]+1,last_result="REJECTED",last_reasons=["EVIDENCE_STORE_INTEGRITY_FAILED"])
        return IngestionResult(False,False,False,("EVIDENCE_STORE_INTEGRITY_FAILED",))
    result=service.ingest(**submission)
    service.audit.update(last_result="ACCEPTED" if result.accepted else "REJECTED",last_reasons=list(result.reasons))
    return result
