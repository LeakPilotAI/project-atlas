from pathlib import Path
SOURCE=Path("frontend/src/lib/cryptoQualityDipsStatus.ts")
def source(): return SOURCE.read_text(encoding="utf-8")

def test_e73_consumer_is_pinned_to_frozen_e72_schema():
    text=source()
    assert 'CRYPTO_QUALITY_DIPS_SCHEMA_VERSION = "E72_CRYPTO_QUALITY_DIPS_PUBLIC_V1"' in text
    assert 'payload.schema_version !== CRYPTO_QUALITY_DIPS_SCHEMA_VERSION' in text
    assert '"UNSUPPORTED_SCHEMA_VERSION"' in text

def test_e73_consumer_fails_closed_on_malformed_public_contract():
    text=source()
    for reason in ("MALFORMED_PAYLOAD","INVALID_PUBLIC_BOUNDARY","MISSING_REQUIRED_SECTION","MALFORMED_REQUIRED_FIELD"): assert reason in text
    for token in ('displayState: "UNAVAILABLE"','severity: "CRITICAL"','operatorAttentionRequired: true','gatesMet: false'): assert token in text

def test_e73_consumer_rejects_any_authority_unlock():
    text=source()
    for field in ("scoring_active","paper_entry_authority","execution_authority","live_capital_allowed","repair_action_available","mutation_action_available"): assert f'"{field}"' in text
    assert 'authority[key] !== false' in text
    assert '"AUTHORITY_BOUNDARY_VIOLATION"' in text
    assert 'authorityLocked: true' in text

def test_e73_view_model_is_presentation_only():
    text=source()
    for state in ("NO_EVIDENCE","COLLECTING","RESEARCH_GATES_MET","REVIEW_REQUIRED","UNAVAILABLE"): assert f'"{state}"' in text
    for token in ("fetch(","POST","PUT","PATCH","DELETE","repair(","mutate(","paperOrder","brokerOrder"): assert token not in text
