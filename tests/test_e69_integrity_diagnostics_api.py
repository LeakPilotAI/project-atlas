import json
from fastapi.testclient import TestClient
from app.main import app
import app.api.crypto_quality_dips_research as api
from app.investment.quality_dips_crypto_store import CryptoProspectiveEvidenceStore, observation_identity

client=TestClient(app)
def get(path,monkeypatch):
    monkeypatch.setattr(api,"EVIDENCE_PATH",path)
    return client.get("/api/investments/crypto-quality-dips/evidence-readiness").json()
def row(): return {"asset_class":"CRYPTO","symbol":"BTC","observed_at":"2026-10-06T14:00:00+00:00","evidence":{},"evidence_valid":True}

def test_no_chain_yet_api_is_bounded(tmp_path,monkeypatch):
    data=get(tmp_path/"e.jsonl",monkeypatch); diag=data["integrity_diagnostic"]
    assert diag["chain_state"]=="NO_CHAIN_YET" and diag["healthy"] is True
    assert diag["repair_available"] is False and diag["mutation_available"] is False
    assert "chain_hash" not in diag and "path" not in diag

def test_legacy_state_is_explicit_not_verified(tmp_path,monkeypatch):
    path=tmp_path/"e.jsonl"; item=row(); item["observation_id"]=observation_identity(item); path.write_text(json.dumps(item)+"\n",encoding="utf-8")
    data=get(path,monkeypatch)
    assert data["integrity_diagnostic"]["chain_state"]=="LEGACY_UNVERIFIED"
    assert "LEGACY_EVIDENCE_UNVERIFIED" in data["integrity_diagnostic"]["reason_codes"]

def test_verified_state_api(tmp_path,monkeypatch):
    path=tmp_path/"e.jsonl"; store=CryptoProspectiveEvidenceStore(path); store.append(row())
    data=get(path,monkeypatch)
    assert data["integrity_diagnostic"]["chain_state"]=="VERIFIED"
    assert data["integrity_diagnostic"]["readiness_eligible"] is True
    assert data["execution_authority"] is False and data["paper_entry_authority"] is False

def test_compromised_forces_readiness_false_and_is_get_only(tmp_path,monkeypatch):
    path=tmp_path/"e.jsonl"; store=CryptoProspectiveEvidenceStore(path); store.append(row()); store.head_path.unlink()
    before=path.read_text(encoding="utf-8"); data=get(path,monkeypatch)
    assert data["integrity_diagnostic"]["chain_state"]=="COMPROMISED"
    assert data["integrity_diagnostic"]["readiness_eligible"] is False
    assert data["readiness_gates_met"] is False and data["gate_checks"]["integrity"] is False
    assert "CHAIN_ANCHOR_INVALID" in data["integrity_diagnostic"]["reason_codes"]
    assert path.read_text(encoding="utf-8")==before
    for verb in ("post","put","patch","delete"):
        assert getattr(client,verb)("/api/investments/crypto-quality-dips/evidence-readiness").status_code==405
