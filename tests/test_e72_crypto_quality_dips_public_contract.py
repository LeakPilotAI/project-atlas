import json
from fastapi.testclient import TestClient
from app.main import app
import app.api.crypto_quality_dips_research as api
from app.investment.quality_dips_crypto_store import CryptoProspectiveEvidenceStore, observation_identity

client=TestClient(app)
PUBLIC_KEYS={"schema_version","surface","read_only","operator","readiness","authority"}
OPERATOR_KEYS={"status","severity","operator_attention_required","chain_state","recovery_status"}
READINESS_KEYS={"gates_met","total_observations","valid_observations","valid_fraction","distinct_observation_days","gate_checks","policy"}
AUTHORITY_KEYS={"scoring_active","paper_entry_authority","execution_authority","live_capital_allowed","repair_action_available","mutation_action_available"}

def row():
    return {"asset_class":"CRYPTO","symbol":"BTC","observed_at":"2026-10-06T16:00:00+00:00","evidence":{},"evidence_valid":True}

def fetch(path,monkeypatch):
    monkeypatch.setattr(api,"EVIDENCE_PATH",path)
    response=client.get("/api/investments/crypto-quality-dips/status")
    assert response.status_code==200
    return response.json()

def test_e72_public_schema_is_frozen_and_bounded(tmp_path,monkeypatch):
    data=fetch(tmp_path/"e.jsonl",monkeypatch)
    assert set(data)==PUBLIC_KEYS
    assert set(data["operator"])==OPERATOR_KEYS
    assert set(data["readiness"])==READINESS_KEYS
    assert set(data["authority"])==AUTHORITY_KEYS
    assert data["schema_version"]=="E72_CRYPTO_QUALITY_DIPS_PUBLIC_V1"
    assert data["surface"]=="CRYPTO_QUALITY_DIPS_RESEARCH" and data["read_only"] is True
    assert data["operator"]["status"]=="NO_EVIDENCE_YET"

def test_e72_public_projection_omits_internal_store_fields(tmp_path,monkeypatch):
    path=tmp_path/"e.jsonl"; CryptoProspectiveEvidenceStore(path).append(row())
    data=fetch(path,monkeypatch)
    encoded=json.dumps(data,sort_keys=True)
    for forbidden in ("store_integrity","integrity_diagnostic","evidence_lifecycle","failure_reasons","chain_hash","previous_chain_hash","observation_id","path","raw"):
        assert forbidden not in encoded
    assert data["operator"]["chain_state"]=="VERIFIED"
    assert data["readiness"]["total_observations"]==1

def test_e72_compromised_public_status_stays_non_authoritative(tmp_path,monkeypatch):
    path=tmp_path/"e.jsonl"; store=CryptoProspectiveEvidenceStore(path); store.append(row()); store.head_path.unlink()
    before=path.read_text(encoding="utf-8")
    data=fetch(path,monkeypatch)
    assert data["operator"]["status"]=="INTEGRITY_REVIEW_REQUIRED"
    assert data["operator"]["severity"]=="CRITICAL"
    assert data["readiness"]["gates_met"] is False
    assert all(value is False for value in data["authority"].values())
    assert path.read_text(encoding="utf-8")==before

def test_e72_public_status_is_get_only_and_legacy_endpoint_remains(tmp_path,monkeypatch):
    path=tmp_path/"e.jsonl"; monkeypatch.setattr(api,"EVIDENCE_PATH",path)
    legacy=client.get("/api/investments/crypto-quality-dips/evidence-readiness")
    assert legacy.status_code==200 and "store_integrity" in legacy.json()
    for verb in ("post","put","patch","delete"):
        assert getattr(client,verb)("/api/investments/crypto-quality-dips/status").status_code==405
    assert not path.exists()
