from fastapi.testclient import TestClient
from app.main import app
import app.api.crypto_quality_dips_research as api
from app.investment.quality_dips_crypto_ingestion import ManualCryptoEvidenceIngestion, invoke_operator_ingestion
from app.investment.quality_dips_crypto_store import CryptoProspectiveEvidenceStore
from app.investment.quality_dips_research_envelope import CRYPTO_EVIDENCE_DIMENSIONS

NOW="2026-10-06T12:00:00+00:00"
def evidence():
    return {d:{"value":1,"source":"operator","observed_at":"2026-10-06T11:30:00+00:00"} for d in CRYPTO_EVIDENCE_DIMENSIONS}
def submission():
    return dict(symbol="BTC",allowlisted=True,liquidity_qualified=True,raw_evidence=evidence(),observed_at=NOW,max_age_seconds=3600)

def test_operator_intent_required(tmp_path):
    svc=ManualCryptoEvidenceIngestion(CryptoProspectiveEvidenceStore(tmp_path/"e.jsonl"))
    result=invoke_operator_ingestion(svc,operator_intent=False,**submission())
    assert not result.accepted and not svc.store.records

def test_operator_boundary_cannot_bypass_validation(tmp_path):
    svc=ManualCryptoEvidenceIngestion(CryptoProspectiveEvidenceStore(tmp_path/"e.jsonl"))
    data=submission(); data["allowlisted"]=False
    result=invoke_operator_ingestion(svc,operator_intent=True,**data)
    assert not result.accepted and not svc.store.records

def test_corrupt_log_fails_closed_without_repair(tmp_path):
    path=tmp_path/"e.jsonl"; path.write_text("{broken\n",encoding="utf-8")
    store=CryptoProspectiveEvidenceStore(path)
    before=path.read_text(encoding="utf-8")
    assert store.integrity["ok"] is False and store.integrity["malformed_lines"]==1
    try:
        store.append({"asset_class":"CRYPTO","symbol":"BTC","observed_at":NOW,"evidence":{}})
        assert False
    except ValueError as exc:
        assert str(exc)=="EVIDENCE_STORE_INTEGRITY_FAILED"
    assert path.read_text(encoding="utf-8")==before

def test_readonly_api_reports_integrity_without_mutation(tmp_path,monkeypatch):
    path=tmp_path/"e.jsonl"; path.write_text("{broken\n",encoding="utf-8")
    monkeypatch.setattr(api,"EVIDENCE_PATH",path)
    before=path.read_text(encoding="utf-8")
    data=TestClient(app).get("/api/investments/crypto-quality-dips/evidence-readiness").json()
    assert data["store_integrity"]["ok"] is False
    assert data["store_integrity"]["repair_performed"] is False
    assert data["ingestion"]["http_mutation_endpoint"] is False
    assert path.read_text(encoding="utf-8")==before
