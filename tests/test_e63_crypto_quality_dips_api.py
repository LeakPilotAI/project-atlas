from fastapi.testclient import TestClient
from app.main import app
import app.api.crypto_quality_dips_research as api

client=TestClient(app)

def test_e63_get_only_empty_readiness(tmp_path,monkeypatch):
    monkeypatch.setattr(api,"EVIDENCE_PATH",tmp_path/"evidence.jsonl")
    data=client.get("/api/investments/crypto-quality-dips/evidence-readiness").json()
    assert data["read_only"] is True and data["record_count"]==0
    assert data["readiness_gates_met"] is False
    assert data["scoring_active"] is False and data["can_emit_signal"] is False

def test_e63_mutation_verbs_rejected(tmp_path,monkeypatch):
    path=tmp_path/"evidence.jsonl"
    monkeypatch.setattr(api,"EVIDENCE_PATH",path)
    for method in ("post","put","patch","delete"):
        assert getattr(client,method)("/api/investments/crypto-quality-dips/evidence-readiness").status_code==405
    assert not path.exists()
