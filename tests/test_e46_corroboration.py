from datetime import datetime, timezone
from app.services.alpha_intelligence import SourceRecord, normalize_event, annotate_context
from app.services.e46_corroboration import POLICY, equivalent_claim

NOW=datetime(2026,10,6,6,0,tzinfo=timezone.utc)
A=SourceRecord("a","A","NEWS","REPUTABLE_REPORTING","a.example")
B=SourceRecord("b","B","OFFICIAL","PRIMARY_OFFICIAL","b.example")
A2=SourceRecord("a2","A2","NEWS","REPUTABLE_REPORTING","a.example")

def ev(source,title,*,published="2026-10-06T05:00:00+00:00",event_type="REGULATORY",symbols=("BTC",),entities=("Bitcoin",),eid=None):
    return normalize_event({
        "event_id":eid or source.source_id+title[:4],
        "url":f"https://{source.domain}/item",
        "published_at":published,
        "retrieved_at":"2026-10-06T05:10:00+00:00",
        "title":title,
        "summary":"",
        "event_type":event_type,
        "symbols":list(symbols),
        "entities":list(entities),
    },source,now=NOW)

def test_policy_is_frozen_bounded_and_non_semantic():
    assert POLICY=={
        "version":"e46-equivalent-claim-v1",
        "min_token_jaccard":0.75,
        "max_publication_gap_hours":72.0,
        "require_same_event_type":True,
        "require_same_structured_subject":True,
        "require_same_polarity":True,
        "require_independent_domain":True,
    }

def test_reworded_equivalent_claim_on_independent_domain_corroborates():
    x=ev(A,"SEC approves spot Bitcoin ETF applications",eid="x")
    y=ev(B,"SEC approves applications for spot Bitcoin ETF",eid="y")
    assert x.content_fingerprint!=y.content_fingerprint
    assert equivalent_claim(x,y)
    out={z.event_id:z for z in annotate_context([x,y])}
    assert out["x"].corroboration_count==1
    assert out["x"].corroborators==({"source_id":"b","domain":"b.example","trust_tier":"PRIMARY_OFFICIAL","url":"https://b.example/item"},)

def test_same_domain_never_inflates_corroboration():
    x=ev(A,"SEC approves spot Bitcoin ETF applications",eid="x")
    y=ev(A2,"SEC approves applications for spot Bitcoin ETF",eid="y")
    assert not equivalent_claim(x,y)

def test_contradiction_is_distinct_not_corroboration():
    x=ev(A,"SEC approves spot Bitcoin ETF applications",eid="x")
    y=ev(B,"SEC does not approve spot Bitcoin ETF applications",eid="y")
    assert not equivalent_claim(x,y)
    out={z.event_id:z for z in annotate_context([x,y])}
    assert out["x"].corroboration_count==0
    assert out["x"].contradiction is True

def test_merely_related_claim_is_not_equivalent():
    x=ev(A,"SEC approves spot Bitcoin ETF applications",eid="x")
    y=ev(B,"SEC opens comment period for Bitcoin custody rules",eid="y")
    assert not equivalent_claim(x,y)

def test_structured_subject_and_time_bounds_fail_closed():
    x=ev(A,"SEC approves spot Bitcoin ETF applications",eid="x")
    other=ev(B,"SEC approves spot Bitcoin ETF applications",symbols=("ETH",),entities=("Ethereum",),eid="y")
    old=ev(B,"SEC approves spot Bitcoin ETF applications",published="2026-10-01T01:00:00+00:00",eid="z")
    assert not equivalent_claim(x,other)
    assert not equivalent_claim(x,old)

def test_corroboration_has_no_authority():
    x=ev(A,"SEC approves spot Bitcoin ETF applications",eid="x")
    y=ev(B,"SEC approves applications for spot Bitcoin ETF",eid="y")
    out=annotate_context([x,y])[0]
    assert out.execution_authority is False
    assert out.strategy_mutation_authority is False
    assert out.membership_mutation_authority is False
    assert out.threshold_mutation_authority is False
