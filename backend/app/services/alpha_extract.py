from html.parser import HTMLParser
from urllib.parse import urljoin,urlparse
import hashlib
from app.services.alpha_ingestion import SOURCE_REGISTRY, ingest

SUPPORTED={"federal_reserve","sec"}
TERMS={"REGULATORY":("enforcement","charges","settlement","rulemaking","regulation"),"MACRO":("federal funds","interest rate","monetary policy","fomc","inflation")}

class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.rows=[]; self.href=None; self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower()=="a": self.href=dict(attrs).get("href"); self.parts=[]
    def handle_data(self,data):
        if self.href is not None: self.parts.append(data)
    def handle_endtag(self,tag):
        if tag.lower()=="a" and self.href is not None:
            title=" ".join(" ".join(self.parts).split())
            if title: self.rows.append((self.href,title))
            self.href=None; self.parts=[]

def classify(title):
    low=title.lower()
    for kind,terms in TERMS.items():
        if any(term in low for term in terms): return kind
    return "OTHER"

def extract(source_id,body,retrieved_at,base_url):
    if source_id not in SUPPORTED: return []
    source=SOURCE_REGISTRY[source_id]
    if (urlparse(base_url).hostname or "").lower()!=source.domain.lower(): raise ValueError("source-domain mismatch")
    parser=Links(); parser.feed(body or ""); out={}
    for href,title in parser.rows:
        url=urljoin(base_url,href); host=(urlparse(url).hostname or "").lower(); path=urlparse(url).path.lower()
        if host!=source.domain.lower(): continue
        fed_valid=(source_id=="federal_reserve" and "/newsevents/pressreleases/" in path and "-press-fomc.htm" not in path and any(ch.isdigit() for ch in path.rsplit("/",1)[-1]))
        valid=fed_valid or (source_id=="sec" and ("/newsroom/press-releases/" in path or "/news/press-release/" in path))
        kind=classify(title)
        if not valid or kind=="OTHER": continue
        eid=hashlib.sha256((source_id+"|"+url+"|"+title).encode()).hexdigest()[:24]
        out[eid]={"event_id":eid,"source_id":source_id,"url":url,"retrieved_at":retrieved_at,"published_at":None,"title":title,"summary":title,"event_type":kind,"symbols":[],"entities":[]}
    return list(out.values())

def promote(source_id,body,retrieved_at,base_url,raw_path=None,event_path=None,now=None):
    candidates=extract(source_id,body,retrieved_at,base_url); results=[]; kwargs={}
    if raw_path is not None: kwargs["raw_path"]=raw_path
    if event_path is not None: kwargs["event_path"]=event_path
    for candidate in candidates: results.append(ingest(candidate,now=now,**kwargs))
    return {"candidate_count":len(candidates),"accepted_count":sum(bool(x.get("accepted")) for x in results),"results":results,"authority":False}
