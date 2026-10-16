"""E46 deterministic bounded cross-source equivalent-claim research.

Policy is intentionally lexical/structured, not semantic or LLM-based.
It grants no execution, PAPER-entry, strategy, membership, or threshold authority.
"""
from __future__ import annotations
from datetime import datetime, timezone
import re

POLICY = {
    "version": "e46-equivalent-claim-v1",
    "min_token_jaccard": 0.75,
    "max_publication_gap_hours": 72.0,
    "require_same_event_type": True,
    "require_same_structured_subject": True,
    "require_same_polarity": True,
    "require_independent_domain": True,
}

_STOP = {
    "the","and","for","with","from","that","this","into","after","before","says","said",
    "official","update","statement","announces","announced","announcement","new",
}
_NEG = {"not","denies","denied","false","cancelled","canceled","rejects","rejected","halts","halted"}

def _dt(value):
    if not value:
        return None
    try:
        d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    except Exception:
        return None
    if d.tzinfo is None:
        d=d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)

def _tokens(event):
    text=f"{event.title} {event.summary}".lower()
    return {x for x in re.findall(r"[a-z0-9]{3,}", text) if x not in _STOP}

def polarity(event):
    text=" "+f"{event.title} {event.summary}".lower()+" "
    return -1 if any(re.search(rf"\b{re.escape(word)}\b", text) for word in _NEG) else 1

def _subject(event):
    symbols=tuple(sorted(str(x).upper() for x in event.symbols))
    entities=tuple(sorted(str(x).casefold() for x in event.entities))
    return symbols,entities

def equivalent_claim(a,b):
    if a.event_id==b.event_id:
        return False
    if POLICY["require_independent_domain"] and a.domain.casefold()==b.domain.casefold():
        return False
    if POLICY["require_same_event_type"] and a.event_type!=b.event_type:
        return False
    if POLICY["require_same_structured_subject"]:
        sa,sb=_subject(a),_subject(b)
        if sa!=((),()) and sb!=((),()) and sa!=sb:
            return False
        if sa==((),()) or sb==((),()):
            return False
    if POLICY["require_same_polarity"] and polarity(a)!=polarity(b):
        return False
    da=_dt(a.published_at or a.retrieved_at); db=_dt(b.published_at or b.retrieved_at)
    if da is None or db is None:
        return False
    if abs((da-db).total_seconds())/3600 > POLICY["max_publication_gap_hours"]:
        return False
    ta,tb=_tokens(a),_tokens(b)
    if not ta or not tb:
        return False
    score=len(ta & tb)/len(ta | tb)
    return score >= POLICY["min_token_jaccard"]

def corroborators_for(event, events):
    matches=[x for x in events if equivalent_claim(event,x)]
    matches.sort(key=lambda x:(x.domain,x.source_id,x.url))
    seen=set();out=[]
    for x in matches:
        key=x.domain.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append({"source_id":x.source_id,"domain":x.domain,"trust_tier":x.trust_tier,"url":x.url})
    return tuple(out)
