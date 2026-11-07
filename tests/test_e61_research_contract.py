from app.investment.quality_dips_crypto_evidence import normalize_crypto_evidence, qualify_crypto_research_universe, prospective_crypto_evidence_record
from app.investment.quality_dips_research_envelope import CRYPTO_EVIDENCE_DIMENSIONS

NOW="2026-10-06T10:00:00+00:00"
def raw():
    return {d:{"value":1,"source":"manual","observed_at":"2026-10-06T09:30:00+00:00"} for d in CRYPTO_EVIDENCE_DIMENSIONS}

def test_fresh_complete():
    rows=normalize_crypto_evidence(raw(),as_of=NOW,max_age_seconds=3600)
    assert all(x.valid for x in rows.values())

def test_bad_inputs_fail_closed():
    data=raw(); data.pop("network_activity")
    rows=normalize_crypto_evidence(data,as_of=NOW,max_age_seconds=3600)
    assert not rows["network_activity"].valid
