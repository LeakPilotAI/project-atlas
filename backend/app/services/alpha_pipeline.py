"""E35 bounded manual Alpha pipeline. No startup worker and no trading authority."""
from datetime import datetime,timezone
from pathlib import Path
from app.services.alpha_fetch import fetch_once,FETCH_LOG
from app.services.alpha_extract import diagnose,promote

def run_source(source_id,*,telemetry_path=FETCH_LOG,raw_path=None,event_path=None,now=None,transport=None,persist=True):
    now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    fetched=fetch_once(source_id,telemetry_path=Path(telemetry_path),now=now,transport=transport,include_body=True)
    body=fetched.pop("_body",None)
    result={"source_id":source_id,"fetch_outcome":fetched.get("outcome"),"fetch":fetched,
            "diagnostics":None,"candidate_count":0,"accepted_count":0,"execution_authority":False,
            "paper_entry_authority":False,"automatic_worker":False}
    if fetched.get("outcome")!="FETCHED" or body is None:return result
    report=diagnose(source_id,body,now.isoformat(),fetched["url"])
    result["diagnostics"]=report["counts"]; result["candidate_count"]=len(report["candidates"])
    if persist and report["candidates"]:
        kwargs={}
        if raw_path is not None:kwargs["raw_path"]=Path(raw_path)
        if event_path is not None:kwargs["event_path"]=Path(event_path)
        stored=promote(source_id,body,now.isoformat(),fetched["url"],now=now,**kwargs)
        result["accepted_count"]=stored["accepted_count"]
    return result
