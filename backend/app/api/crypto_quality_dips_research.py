"""Read-only Crypto Quality Dips prospective evidence surface."""
from pathlib import Path
from fastapi import APIRouter
from app.investment.quality_dips_crypto_store import CryptoProspectiveEvidenceStore, evidence_summary, integrity_diagnostic, lifecycle_status, operator_presentation

router=APIRouter(prefix="/api/investments/crypto-quality-dips",tags=["crypto quality dips research"])
EVIDENCE_PATH=Path("data/research/crypto_quality_dips_prospective.jsonl")

@router.get("/evidence-readiness")
def evidence_readiness():
    store=CryptoProspectiveEvidenceStore(EVIDENCE_PATH)
    result=evidence_summary(store.records)
    result["read_only"]=True
    result["record_count"]=len(store.records)
    diagnostic=integrity_diagnostic(store.integrity)
    result["store_integrity"]={**store.integrity,"repair_performed":False}
    result["integrity_diagnostic"]=diagnostic
    result["evidence_lifecycle"]=lifecycle_status(store.records,store.integrity)
    result["operator_presentation"]=operator_presentation(result,diagnostic,result["evidence_lifecycle"])
    if not diagnostic["readiness_eligible"]:
        result["readiness_gates_met"]=False
        result["gate_checks"]["integrity"]=False
    else:
        result["gate_checks"]["integrity"]=True
    result["ingestion"]={"mode":"MANUAL_OPERATOR_ONLY","http_mutation_endpoint":False,"autonomous_collection":False}
    return result

OPERATOR_INGESTION_CONTRACT={
    "status":"DESIGN_ONLY","mode":"MANUAL_OPERATOR_ONLY","endpoint_active":False,
    "autonomous_collection":False,"external_feeds_connected":False,
    "requires_normalized_evidence":True,"requires_explicit_universe_qualification":True,
    "execution_authority":False,"paper_entry_authority":False,
}
