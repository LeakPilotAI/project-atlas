from app.investment.quality_dips_crypto_store import CryptoProspectiveEvidenceStore, evidence_summary, observation_identity
from app.investment.quality_dips_crypto_evidence import normalize_crypto_evidence, prospective_crypto_evidence_record
from app.investment.quality_dips_research_envelope import CRYPTO_EVIDENCE_DIMENSIONS
from app.investment.quality_dips_v3_state import QualityDipsV3StateStore

NOW="2026-10-06T10:00:00+00:00"
def record(symbol="BTC"):
    raw={d:{"value":1,"source":"manual","observed_at":"2026-10-06T09:30:00+00:00"} for d in CRYPTO_EVIDENCE_DIMENSIONS}
    norm=normalize_crypto_evidence(raw,as_of=NOW,max_age_seconds=3600)
    return prospective_crypto_evidence_record(symbol=symbol,observed_at=NOW,normalized=norm)

def test_identity_is_deterministic_and_append_dedupes(tmp_path):
    row=record(); assert observation_identity(row)==observation_identity(dict(row))
    store=CryptoProspectiveEvidenceStore(tmp_path/"crypto.jsonl")
    assert store.append(row) is True and store.append(row) is False
    assert len(store.records)==1

def test_reload_preserves_single_observation(tmp_path):
    path=tmp_path/"crypto.jsonl"; first=CryptoProspectiveEvidenceStore(path)
    first.append(record("ETH")); second=CryptoProspectiveEvidenceStore(path)
    assert len(second.records)==1 and second.records[0]["symbol"]=="ETH"

def test_summary_is_read_only_and_zero_authority(tmp_path):
    store=CryptoProspectiveEvidenceStore(tmp_path/"crypto.jsonl"); store.append(record())
    summary=evidence_summary(store.records)
    assert summary["total_observations"]==1 and summary["valid_observations"]==1
    assert summary["readiness_gates_met"] is False
    for key in ("scoring_active","dip_state_active","can_emit_signal","paper_entry_authority","execution_authority","strategy_selection_authority","threshold_mutation_authority","promotion_authority","live_capital_allowed"):
        assert summary[key] is False
