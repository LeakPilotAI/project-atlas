import json
from fastapi.testclient import TestClient
from app.main import app
import app.api.crypto_quality_dips_research as api
from app.investment.quality_dips_crypto_store import CryptoProspectiveEvidenceStore, observation_identity

client=TestClient(app)
def row(): return {"asset_class":"CRYPTO","symbol":"BTC","observed_at":"2026-10-06T15:00:00+00:00","evidence":{},"evidence_valid":True}
def fetch(path,monkeypatch): monkeypatch.setattr(api,"EVIDENCE_PATH",path); return client.get("/api/investments/crypto-quality-dips/evidence-readiness").json()

def test_no_chain_presentation(tmp_path,monkeypatch):
    p=fetch(tmp_path/"e.jsonl",monkeypatch)["operator_presentation"]
    assert (p["status"],p["severity"],p["operator_attention_required"])==("NO_EVIDENCE_YET","INFO",False)
    assert p["read_only"] is True and p["repair_action_available"] is False and p["mutation_action_available"] is False

def test_legacy_presentation_requires_attention(tmp_path,monkeypatch):
    path=tmp_path/"e.jsonl"; item=row(); item["observation_id"]=observation_identity(item); path.write_text(json.dumps(item)+"\n",encoding="utf-8")
    p=fetch(path,monkeypatch)["operator_presentation"]
    assert (p["status"],p["severity"],p["operator_attention_required"])==("LEGACY_REVIEW_REQUIRED","WARNING",True)

def test_verified_presentation_is_collecting(tmp_path,monkeypatch):
    path=tmp_path/"e.jsonl"; CryptoProspectiveEvidenceStore(path).append(row()); before=path.read_text(encoding="utf-8")
    data=fetch(path,monkeypatch); p=data["operator_presentation"]
    assert (p["status"],p["severity"],p["operator_attention_required"])==("COLLECTING_EVIDENCE","INFO",False)
    assert p["chain_state"]=="VERIFIED" and path.read_text(encoding="utf-8")==before

def test_compromised_presentation_is_critical_and_readiness_false(tmp_path,monkeypatch):
    path=tmp_path/"e.jsonl"; store=CryptoProspectiveEvidenceStore(path); store.append(row()); store.head_path.unlink(); before=path.read_text(encoding="utf-8")
    data=fetch(path,monkeypatch); p=data["operator_presentation"]
    assert (p["status"],p["severity"],p["operator_attention_required"])==("INTEGRITY_REVIEW_REQUIRED","CRITICAL",True)
    assert p["readiness_gates_met"] is False and p["recovery_status"]=="MANUAL_REVIEW_REQUIRED"
    assert path.read_text(encoding="utf-8")==before
    for forbidden in ("chain_hash","path","evidence","raw"):
        assert forbidden not in p
