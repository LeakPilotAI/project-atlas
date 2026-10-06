"""Read-only Crypto Quality Dips prospective evidence surface."""
from pathlib import Path
from fastapi import APIRouter
from app.investment.quality_dips_crypto_store import CryptoProspectiveEvidenceStore, evidence_summary

router=APIRouter(prefix="/api/investments/crypto-quality-dips",tags=["crypto quality dips research"])
EVIDENCE_PATH=Path("data/research/crypto_quality_dips_prospective.jsonl")

@router.get("/evidence-readiness")
def evidence_readiness():
    store=CryptoProspectiveEvidenceStore(EVIDENCE_PATH)
    result=evidence_summary(store.records)
    result["read_only"]=True
    result["record_count"]=len(store.records)
    result["store_integrity"]={**store.integrity,"repair_performed":False}
    result["ingestion"]={"mode":"MANUAL_OPERATOR_ONLY","http_mutation_endpoint":False,"autonomous_collection":False}
    return result

OPERATOR_INGESTION_CONTRACT={
    "status":"DESIGN_ONLY","mode":"MANUAL_OPERATOR_ONLY","endpoint_active":False,
    "autonomous_collection":False,"external_feeds_connected":False,
    "requires_normalized_evidence":True,"requires_explicit_universe_qualification":True,
    "execution_authority":False,"paper_entry_authority":False,
}
