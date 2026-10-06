"""Execution 31 governed Internet/Alpha context model.

This module normalizes externally fetched intelligence as untrusted research data.
It has deliberately no dependency on scanner, execution, paper-entry, broker, or
challenger-membership services.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib, re
from typing import Any, Iterable
from urllib.parse import urlparse

SCHEMA_VERSION="alpha-intel-event-v1"
TRUST_TIERS={"PRIMARY_OFFICIAL":4,"REPUTABLE_REPORTING":3,"MARKET_STRUCTURE":3,"GOVERNED_SOCIAL":1,"UNKNOWN":0}
SOURCE_CLASSES={"OFFICIAL","NEWS","MACRO","MARKET_STRUCTURE","SOCIAL","OTHER"}
EVENT_TYPES={"LISTING","DELISTING","PROTOCOL","REGULATORY","MACRO","SECURITY","FUNDING_OI","LIQUIDATION","PARTNERSHIP","TOKENOMICS","OTHER"}
MAX_AGE_HOURS={"OFFICIAL":168,"NEWS":72,"MACRO":168,"MARKET_STRUCTURE":24,"SOCIAL":12,"OTHER":72}

def _utc(value: str|datetime|None)->datetime|None:
    if value is None:return None
    if isinstance(value,datetime): dt=value
    else:
        try: dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        except ValueError:return None
    if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def _tokens(text:str)->set[str]:
    return set(re.findall(r"[a-z0-9]{3,}",(text or "").lower()))

@dataclass(frozen=True)
class SourceRecord:
    source_id:str; name:str; source_class:str; trust_tier:str; domain:str
    def __post_init__(self):
        if self.source_class not in SOURCE_CLASSES: raise ValueError("invalid source_class")
        if self.trust_tier not in TRUST_TIERS: raise ValueError("invalid trust_tier")
        if not self.domain or "/" in self.domain: raise ValueError("domain must be a hostname")

@dataclass(frozen=True)
class IntelligenceEvent:
    event_id:str; source_id:str; source_class:str; trust_tier:str; url:str; domain:str
    retrieved_at:str; published_at:str|None; title:str; summary:str; event_type:str
    symbols:tuple[str,...]; entities:tuple[str,...]; content_fingerprint:str
    stale:bool; rumor_only:bool; contradiction:bool; corroboration_count:int
    corroborators:tuple[dict,...]=()
    untrusted_external_text:bool=True; execution_authority:bool=False
    strategy_mutation_authority:bool=False; membership_mutation_authority:bool=False
    threshold_mutation_authority:bool=False

def normalize_event(raw:dict[str,Any],source:SourceRecord,*,now:datetime|None=None)->IntelligenceEvent:
    now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    url=str(raw.get("url") or "").strip(); host=(urlparse(url).hostname or "").lower()
    if not url.startswith(("http://","https://")) or host!=source.domain.lower(): raise ValueError("url/domain provenance mismatch")
    retrieved=_utc(raw.get("retrieved_at")) or now; published=_utc(raw.get("published_at"))
    title=" ".join(str(raw.get("title") or "").split()); summary=" ".join(str(raw.get("summary") or "").split())
    if not title: raise ValueError("title required")
    event_type=str(raw.get("event_type") or "OTHER").upper()
    if event_type not in EVENT_TYPES:event_type="OTHER"
    symbols=tuple(sorted({str(x).upper().strip() for x in raw.get("symbols") or [] if str(x).strip()}))
    entities=tuple(sorted({str(x).strip() for x in raw.get("entities") or [] if str(x).strip()}))
    canonical="|".join([event_type," ".join(sorted(_tokens(title+" "+summary)))])
    fp=hashlib.sha256(canonical.encode()).hexdigest()
    age_ref=published or retrieved
    stale=((now-age_ref).total_seconds()/3600)>MAX_AGE_HOURS[source.source_class]
    rumor=bool(raw.get("rumor_only")) or source.source_class=="SOCIAL" and not bool(raw.get("corroborated"))
    eid=str(raw.get("event_id") or hashlib.sha256((source.source_id+"|"+url+"|"+title).encode()).hexdigest()[:24])
    return IntelligenceEvent(eid,source.source_id,source.source_class,source.trust_tier,url,host,retrieved.isoformat(),published.isoformat() if published else None,title,summary,event_type,symbols,entities,fp,stale,rumor,False,0)

def annotate_context(events:Iterable[IntelligenceEvent])->list[IntelligenceEvent]:
    rows=list(events); out=[]
    for e in rows:
        corroborators=[x for x in rows if x.event_id!=e.event_id and x.content_fingerprint==e.content_fingerprint and x.domain!=e.domain]
        related=[x for x in rows if x.event_id!=e.event_id and x.event_type==e.event_type and set(x.symbols)&set(e.symbols)]
        contradiction=any(_is_contradiction(e,x) for x in related)
        data=asdict(e); data["corroboration_count"]=len({x.domain for x in corroborators}); data["contradiction"]=contradiction
        data["corroborators"]=tuple({"source_id":x.source_id,"domain":x.domain,"trust_tier":x.trust_tier,"url":x.url} for x in sorted(corroborators,key=lambda z:(z.source_id,z.url)))
        if data["corroboration_count"]>0:data["rumor_only"]=False
        out.append(IntelligenceEvent(**data))
    return out

def _is_contradiction(a:IntelligenceEvent,b:IntelligenceEvent)->bool:
    neg=(" not "," denies "," denied "," false "," cancelled "," canceled "," rejects "," rejected ")
    def polarity(x): return -1 if any(n in " "+(x.title+" "+x.summary).lower()+" " for n in neg) else 1
    return polarity(a)!=polarity(b)

def deduplicate(events:Iterable[IntelligenceEvent])->list[IntelligenceEvent]:
    best={}
    for e in events:
        key=e.content_fingerprint; cur=best.get(key)
        rank=(TRUST_TIERS[e.trust_tier], bool(e.published_at), e.retrieved_at)
        if cur is None or rank>(TRUST_TIERS[cur.trust_tier],bool(cur.published_at),cur.retrieved_at):best[key]=e
    return list(best.values())

def safety_contract()->dict[str,Any]:
    return {"schema_version":SCHEMA_VERSION,"external_text_is_untrusted_data":True,"execution_authority":False,"live_capital_allowed":False,"automatic_real_money_execution":False,"strategy_mutation_authority":False,"membership_mutation_authority":False,"threshold_mutation_authority":False,"paper_entry_authority":False}

