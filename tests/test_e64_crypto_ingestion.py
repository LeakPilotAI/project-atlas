from app.investment.quality_dips_crypto_ingestion import ManualCryptoEvidenceIngestion
from app.investment.quality_dips_crypto_store import CryptoProspectiveEvidenceStore
from app.investment.quality_dips_research_envelope import CRYPTO_EVIDENCE_DIMENSIONS
from app.investment.quality_dips_v3_state import QualityDipsV3StateStore

NOW="2026-10-06T11:00:00+00:00"
def evidence(ts="2026-10-06T10:30:00+00:00"):
    return {d:{"value":1,"source":"operator-source","observed_at":ts} for d in CRYPTO_EVIDENCE_DIMENSIONS}

def service(tmp_path):
    return ManualCryptoEvidenceIngestion(CryptoProspectiveEvidenceStore(tmp_path/"crypto.jsonl"))

def test_e64_valid_manual_ingestion_is_idempotent(tmp_path):
    svc=service(tmp_path)
    a=svc.ingest(symbol="BTC",allowlisted=True,liquidity_qualified=True,raw_evidence=evidence(),observed_at=NOW,max_age_seconds=3600)
    b=svc.ingest(symbol="BTC",allowlisted=True,liquidity_qualified=True,raw_evidence=evidence(),observed_at=NOW,max_age_seconds=3600)
    assert a.accepted and a.persisted and not a.duplicate
    assert b.accepted and not b.persisted and b.duplicate
    assert len(svc.store.records)==1

def test_e64_unqualified_and_stale_cannot_persist(tmp_path):
    svc=service(tmp_path)
    bad=svc.ingest(symbol="ETH",allowlisted=False,liquidity_qualified=True,raw_evidence=evidence(),observed_at=NOW,max_age_seconds=3600)
    stale=svc.ingest(symbol="SOL",allowlisted=True,liquidity_qualified=True,raw_evidence=evidence("2026-10-05T00:00:00+00:00"),observed_at=NOW,max_age_seconds=3600)
    assert not bad.accepted and not stale.accepted
    assert len(svc.store.records)==0

def test_e64_zero_authority_observability(tmp_path):
    svc=service(tmp_path); svc.ingest(symbol="BTC",allowlisted=True,liquidity_qualified=True,raw_evidence=evidence(),observed_at=NOW,max_age_seconds=3600)
    obs=svc.observability()
    assert obs["attempted"]==1 and obs["persisted"]==1
    assert obs["outcomes_inferred"] is False and obs["performance_inferred"] is False
    for key in ("execution_authority","paper_entry_authority","strategy_mutation_authority","threshold_mutation_authority","promotion_authority","live_capital_allowed"):
        assert obs[key] is False
