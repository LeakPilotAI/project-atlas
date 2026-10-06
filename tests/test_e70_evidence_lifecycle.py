import json
from fastapi.testclient import TestClient
from app.main import app
import app.api.crypto_quality_dips_research as api
from app.investment.quality_dips_crypto_store import CryptoProspectiveEvidenceStore, observation_identity

client=TestClient(app)
def row(symbol,day): return {"asset_class":"CRYPTO","symbol":symbol,"observed_at":f"2026-10-{day}T12:00:00+00:00","evidence":{},"evidence_valid":True}
def fetch(path,monkeypatch): monkeypatch.setattr(api,"EVIDENCE_PATH",path); return client.get("/api/investments/crypto-quality-dips/evidence-readiness").json()

def test_lifecycle_is_bounded_append_only_status(tmp_path,monkeypatch):
    path=tmp_path/"e.jsonl"; store=CryptoProspectiveEvidenceStore(path); store.append(row("BTC","06")); store.append(row("ETH","08"))
    before=path.read_text(encoding="utf-8"); data=fetch(path,monkeypatch); life=data["evidence_lifecycle"]
    assert life["record_count"]==2 and life["chain_verified_count"]==2
    assert life["oldest_observation_date"]=="2026-10-06" and life["newest_observation_date"]=="2026-10-08"
    assert life["retention_mode"]=="APPEND_ONLY" and life["automatic_repair"] is False
    assert path.read_text(encoding="utf-8")==before
    assert "chain_hash" not in life and "path" not in life

def test_legacy_count_is_explicit(tmp_path,monkeypatch):
    path=tmp_path/"e.jsonl"; item=row("BTC","05"); item["observation_id"]=observation_identity(item); path.write_text(json.dumps(item)+"\n",encoding="utf-8")
    life=fetch(path,monkeypatch)["evidence_lifecycle"]
    assert life["legacy_unverified_count"]==1 and life["chain_verified_count"]==0

def test_compromised_recovery_is_manual_review_only(tmp_path,monkeypatch):
    path=tmp_path/"e.jsonl"; store=CryptoProspectiveEvidenceStore(path); store.append(row("BTC","06")); store.head_path.unlink()
    before=path.read_text(encoding="utf-8"); data=fetch(path,monkeypatch); life=data["evidence_lifecycle"]
    assert life["recovery_status"]=="MANUAL_REVIEW_REQUIRED"
    assert life["automatic_repair"] is False and data["readiness_gates_met"] is False
    assert data["execution_authority"] is False and data["paper_entry_authority"] is False
    assert path.read_text(encoding="utf-8")==before
    for verb in ("post","put","patch","delete"):
        assert getattr(client,verb)("/api/investments/crypto-quality-dips/evidence-readiness").status_code==405
