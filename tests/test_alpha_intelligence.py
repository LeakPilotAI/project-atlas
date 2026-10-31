from datetime import datetime,timezone,timedelta
import pytest
from app.services.alpha_intelligence import SourceRecord,normalize_event,annotate_context,deduplicate,safety_contract

NOW=datetime(2026,10,5,12,tzinfo=timezone.utc)
def source(id="official",domain="example.org",cls="OFFICIAL",tier="PRIMARY_OFFICIAL"):
    return SourceRecord(id,id,cls,tier,domain)
def raw(**kw):
    d={"url":"https://example.org/a","retrieved_at":NOW.isoformat(),"published_at":NOW.isoformat(),"title":"Protocol upgrade approved","summary":"Upgrade approved by governance","event_type":"PROTOCOL","symbols":["abc"],"entities":["Example"]}
    d.update(kw); return d

def test_normalizes_provenance_and_has_zero_execution_authority():
    e=normalize_event(raw(),source(),now=NOW)
    assert e.domain=="example.org" and e.symbols==("ABC",) and e.untrusted_external_text is True
    assert e.execution_authority is False and e.strategy_mutation_authority is False
    assert e.membership_mutation_authority is False and e.threshold_mutation_authority is False

def test_rejects_url_source_domain_mismatch():
    with pytest.raises(ValueError):normalize_event(raw(url="https://evil.test/a"),source(),now=NOW)

def test_staleness_is_source_class_aware_and_missing_publication_uses_retrieval():
    old=(NOW-timedelta(days=10)).isoformat()
    assert normalize_event(raw(published_at=old),source(),now=NOW).stale is True
    assert normalize_event(raw(published_at=None,retrieved_at=NOW.isoformat()),source(),now=NOW).stale is False

def test_social_is_rumor_only_until_independently_corroborated():
    social=source("social","social.example","SOCIAL","GOVERNED_SOCIAL")
    e=normalize_event(raw(url="https://social.example/a"),social,now=NOW)
    assert e.rumor_only is True

def test_corroboration_requires_separate_domain_and_clears_rumor_flag():
    s1=source("s1","a.example","SOCIAL","GOVERNED_SOCIAL"); s2=source("s2","b.example","NEWS","REPUTABLE_REPORTING")
    a=normalize_event(raw(url="https://a.example/a"),s1,now=NOW)
    b=normalize_event(raw(url="https://b.example/b"),s2,now=NOW)
    rows=annotate_context([a,b])
    assert rows[0].corroboration_count==1 and rows[0].rumor_only is False

def test_contradiction_flag_preserves_both_claims():
    s1=source("s1","a.example"); s2=source("s2","b.example","NEWS","REPUTABLE_REPORTING")
    a=normalize_event(raw(url="https://a.example/a",title="Protocol upgrade approved"),s1,now=NOW)
    b=normalize_event(raw(url="https://b.example/b",title="Protocol denies upgrade approved",summary="Upgrade denied"),s2,now=NOW)
    rows=annotate_context([a,b]); assert all(x.contradiction for x in rows)

def test_dedup_prefers_higher_trust_without_rewriting_source():
    low=normalize_event(raw(url="https://social.example/a"),source("lo","social.example","SOCIAL","GOVERNED_SOCIAL"),now=NOW)
    high=normalize_event(raw(url="https://news.example/a"),source("hi","news.example","NEWS","REPUTABLE_REPORTING"),now=NOW)
    rows=deduplicate([low,high]); assert len(rows)==1 and rows[0].source_id=="hi"

def test_safety_contract_is_context_only():
    s=safety_contract()
    assert s["external_text_is_untrusted_data"] is True
    for k in ("execution_authority","live_capital_allowed","automatic_real_money_execution","strategy_mutation_authority","membership_mutation_authority","threshold_mutation_authority","paper_entry_authority"):
        assert s[k] is False
