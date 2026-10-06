import json
from app.investment.quality_dips_crypto_store import CryptoProspectiveEvidenceStore, observation_identity, evidence_summary
from app.investment.quality_dips_crypto_ingestion import ManualCryptoEvidenceIngestion, invoke_operator_ingestion
from app.investment.quality_dips_research_envelope import CRYPTO_EVIDENCE_DIMENSIONS

NOW="2026-10-06T13:00:00+00:00"
def evidence():
    return {d:{"value":1,"source":"operator","observed_at":"2026-10-06T12:30:00+00:00"} for d in CRYPTO_EVIDENCE_DIMENSIONS}
def submission():
    return dict(symbol="BTC",allowlisted=True,liquidity_qualified=True,raw_evidence=evidence(),observed_at=NOW,max_age_seconds=3600)

def test_identity_tamper_is_quarantined_and_blocks_append(tmp_path):
    path=tmp_path/"e.jsonl"
    row={"asset_class":"CRYPTO","symbol":"BTC","observed_at":NOW,"evidence":{},"evidence_valid":True}
    row["observation_id"]="tampered"
    path.write_text(json.dumps(row)+"\n",encoding="utf-8")
    store=CryptoProspectiveEvidenceStore(path)
    assert store.integrity["ok"] is False and store.integrity["identity_mismatch_lines"]==1
    assert store.records==[] and evidence_summary(store.records)["total_observations"]==0
    try:
        store.append(row); assert False
    except ValueError as exc:
        assert str(exc)=="EVIDENCE_STORE_INTEGRITY_FAILED"

def test_operator_audit_is_bounded_and_contains_no_raw_evidence(tmp_path):
    svc=ManualCryptoEvidenceIngestion(CryptoProspectiveEvidenceStore(tmp_path/"e.jsonl"))
    invoke_operator_ingestion(svc,operator_intent=False,**submission())
    obs=svc.observability()
    assert obs["audit"]["operator_attempts"]==1 and obs["audit"]["intent_rejections"]==1
    assert obs["raw_evidence_retained"] is False
    assert "raw_evidence" not in obs["audit"] and "outcome" not in obs["audit"] and "performance" not in obs["audit"]
    assert obs["execution_authority"] is False and obs["paper_entry_authority"] is False

def test_valid_stored_identity_survives_reload(tmp_path):
    path=tmp_path/"e.jsonl"; store=CryptoProspectiveEvidenceStore(path)
    svc=ManualCryptoEvidenceIngestion(store)
    result=invoke_operator_ingestion(svc,operator_intent=True,**submission())
    assert result.persisted
    loaded=CryptoProspectiveEvidenceStore(path)
    assert loaded.integrity["ok"] is True and len(loaded.records)==1
    assert loaded.records[0]["observation_id"]==observation_identity(loaded.records[0])
