"""Read-only Crypto Quality Dips prospective evidence surface."""
from pathlib import Path
from fastapi import APIRouter
from app.investment.quality_dips_crypto_store import CryptoProspectiveEvidenceStore, evidence_summary, integrity_diagnostic, lifecycle_status, operator_presentation

router=APIRouter(prefix="/api/investments/crypto-quality-dips",tags=["crypto quality dips research"])
EVIDENCE_PATH=Path("data/research/crypto_quality_dips_prospective.jsonl")
PUBLIC_API_SCHEMA_VERSION="E72_CRYPTO_QUALITY_DIPS_PUBLIC_V1"

def _readiness_result():
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

def public_status_projection(result):
    operator=result["operator_presentation"]
    return {
        "schema_version":PUBLIC_API_SCHEMA_VERSION,
        "surface":"CRYPTO_QUALITY_DIPS_RESEARCH",
        "read_only":True,
        "operator":{
            "status":operator["status"],
            "severity":operator["severity"],
            "operator_attention_required":operator["operator_attention_required"],
            "chain_state":operator["chain_state"],
            "recovery_status":operator["recovery_status"],
        },
        "readiness":{
            "gates_met":bool(result["readiness_gates_met"]),
            "total_observations":int(result["total_observations"]),
            "valid_observations":int(result["valid_observations"]),
            "valid_fraction":float(result["valid_fraction"]),
            "distinct_observation_days":int(result["distinct_observation_days"]),
            "gate_checks":dict(result["gate_checks"]),
            "policy":dict(result["predeclared_readiness_policy"]),
        },
        "authority":{
            "scoring_active":False,
            "paper_entry_authority":False,
            "execution_authority":False,
            "live_capital_allowed":False,
            "repair_action_available":False,
            "mutation_action_available":False,
        },
    }

@router.get("/evidence-readiness")
def evidence_readiness():
    return _readiness_result()

@router.get("/status")
def public_status():
    return public_status_projection(_readiness_result())

OPERATOR_INGESTION_CONTRACT={
    "status":"DESIGN_ONLY","mode":"MANUAL_OPERATOR_ONLY","endpoint_active":False,
    "autonomous_collection":False,"external_feeds_connected":False,
    "requires_normalized_evidence":True,"requires_explicit_universe_qualification":True,
    "execution_authority":False,"paper_entry_authority":False,
}
