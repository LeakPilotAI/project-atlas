from html.parser import HTMLParser
from urllib.parse import urljoin,urlparse
import hashlib,re
from datetime import datetime,timezone
from app.services.alpha_ingestion import SOURCE_REGISTRY, ingest

SUPPORTED={"federal_reserve","sec"}
TERMS={"REGULATORY":("enforcement","charges","settlement","rulemaking","regulation","proposal","proposes","exemption","custody"),"MACRO":("federal funds","interest rate","monetary policy","fomc","inflation")}
RELEVANCE_TERMS=("crypto","digital asset","bitcoin","ethereum","stablecoin","tokenized","tokenization","market structure","securities market","monetary policy","fomc","federal funds","interest rate","inflation")
ENTITY_TERMS=(("bitcoin","Bitcoin"),("ethereum","Ethereum"),("stablecoin","Stablecoins"),("crypto asset","Crypto Assets"),("digital asset","Digital Assets"),("tokenized","Tokenized Securities"),("tokenization","Tokenized Securities"),("market structure","Market Structure"),("fomc","FOMC"),("federal funds","Federal Funds Rate"),("interest rate","Interest Rates"),("inflation","Inflation"))
MAX_AGE_HOURS=168
DATE_PATTERNS=(re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b"),re.compile(r"(20\d{2})(\d{2})(\d{2})[a-z]?"))

def relevant(title):
    low=title.lower(); return any(term in low for term in RELEVANCE_TERMS)

def entities_for(title):
    low=title.lower(); return sorted({entity for term,entity in ENTITY_TERMS if term in low})

def _utc(value):
    try:
        dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError,TypeError): return None

def publication_from_url(url):
    leaf=urlparse(url).path.rsplit("/",1)[-1]
    for pat in DATE_PATTERNS:
        m=pat.search(leaf)
        if m:
            try:return datetime(int(m.group(1)),int(m.group(2)),int(m.group(3)),tzinfo=timezone.utc).isoformat()
            except ValueError:return None
    return None

class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.rows=[]; self.href=None; self.parts=[]; self.in_tr=False; self.row_time=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs); tag=tag.lower()
        if tag=="tr": self.in_tr=True; self.row_time=None
        elif tag=="time" and self.in_tr and attrs.get("datetime"): self.row_time=attrs["datetime"]
        elif tag=="a": self.href=attrs.get("href"); self.parts=[]
    def handle_data(self,data):
        if self.href is not None: self.parts.append(data)
    def handle_endtag(self,tag):
        tag=tag.lower()
        if tag=="a" and self.href is not None:
            title=" ".join(" ".join(self.parts).split())
            if title: self.rows.append((self.href,title,self.row_time))
            self.href=None; self.parts=[]
        elif tag=="tr": self.in_tr=False; self.row_time=None

def classify(title):
    low=title.lower()
    for kind,terms in TERMS.items():
        if any(term in low for term in terms): return kind
    return "OTHER"

def _published(source_id,url,row_time):
    if source_id=="sec" and row_time:
        dt=_utc(row_time); return dt.isoformat() if dt else None
    return publication_from_url(url)

def _fresh(published,retrieved_at):
    p=_utc(published); r=_utc(retrieved_at)
    if p is None or r is None: return False
    age=(r-p).total_seconds()/3600
    return -0.1<=age<=MAX_AGE_HOURS

def extract(source_id,body,retrieved_at,base_url):
    if source_id not in SUPPORTED: return []
    source=SOURCE_REGISTRY[source_id]
    if (urlparse(base_url).hostname or "").lower()!=source.domain.lower(): raise ValueError("source-domain mismatch")
    parser=Links(); parser.feed(body or ""); out={}
    for href,title,row_time in parser.rows:
        url=urljoin(base_url,href); host=(urlparse(url).hostname or "").lower(); path=urlparse(url).path.lower()
        if host!=source.domain.lower(): continue
        fed_valid=(source_id=="federal_reserve" and "/newsevents/pressreleases/" in path and "-press-fomc.htm" not in path and any(ch.isdigit() for ch in path.rsplit("/",1)[-1]))
        valid=fed_valid or (source_id=="sec" and ("/newsroom/press-releases/" in path or "/news/press-release/" in path))
        kind=classify(title); published=_published(source_id,url,row_time)
        if not valid or kind=="OTHER" or not relevant(title) or published is None or not _fresh(published,retrieved_at): continue
        eid=hashlib.sha256((source_id+"|"+url+"|"+title).encode()).hexdigest()[:24]
        out[eid]={"event_id":eid,"source_id":source_id,"url":url,"retrieved_at":retrieved_at,"published_at":published,"title":title,"summary":title,"event_type":kind,"symbols":[],"entities":entities_for(title)}
    return list(out.values())

def diagnose(source_id,body,retrieved_at,base_url):
    source=SOURCE_REGISTRY.get(source_id); counts={"accepted":0,"off_domain":0,"unsupported_path":0,"unsupported_event_type":0,"irrelevant_topic":0,"missing_publication_time":0,"stale_or_future":0}
    if source is None or source_id not in SUPPORTED:return {"counts":counts,"candidates":[]}
    if (urlparse(base_url).hostname or "").lower()!=source.domain.lower():raise ValueError("source-domain mismatch")
    parser=Links(); parser.feed(body or ""); accepted=extract(source_id,body,retrieved_at,base_url); counts["accepted"]=len(accepted)
    for href,title,row_time in parser.rows:
        url=urljoin(base_url,href); host=(urlparse(url).hostname or "").lower(); path=urlparse(url).path.lower()
        if host!=source.domain.lower():counts["off_domain"]+=1; continue
        fed_valid=(source_id=="federal_reserve" and "/newsevents/pressreleases/" in path and "-press-fomc.htm" not in path and any(ch.isdigit() for ch in path.rsplit("/",1)[-1]))
        valid=fed_valid or (source_id=="sec" and ("/newsroom/press-releases/" in path or "/news/press-release/" in path))
        if not valid:counts["unsupported_path"]+=1; continue
        if classify(title)=="OTHER":counts["unsupported_event_type"]+=1; continue
        if not relevant(title):counts["irrelevant_topic"]+=1; continue
        published=_published(source_id,url,row_time)
        if published is None:counts["missing_publication_time"]+=1; continue
        if not _fresh(published,retrieved_at):counts["stale_or_future"]+=1
    return {"counts":counts,"candidates":accepted,"execution_authority":False,"paper_entry_authority":False}

def promote(source_id,body,retrieved_at,base_url,raw_path=None,event_path=None,now=None):
    candidates=extract(source_id,body,retrieved_at,base_url); results=[]; kwargs={}
    if raw_path is not None: kwargs["raw_path"]=raw_path
    if event_path is not None: kwargs["event_path"]=event_path
    for candidate in candidates: results.append(ingest(candidate,now=now,**kwargs))
    return {"candidate_count":len(candidates),"accepted_count":sum(bool(x.get("accepted")) for x in results),"results":results,"authority":False}
