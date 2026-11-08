"""E37 governed manual Alpha run surface. Research-only and source-allowlisted."""
from datetime import datetime,timezone
from app.services.alpha_pipeline import run_source

MANUAL_SOURCES=("federal_reserve","sec")

def manual_run(source_id,*,persist=True,telemetry_path=None,raw_path=None,event_path=None,now=None,transport=None):
    if source_id not in MANUAL_SOURCES:
        raise ValueError("source_id is not enabled for manual Alpha runs")
    kwargs={"persist":bool(persist),"now":now or datetime.now(timezone.utc),"transport":transport}
    if telemetry_path is not None: kwargs["telemetry_path"]=telemetry_path
    if raw_path is not None: kwargs["raw_path"]=raw_path
    if event_path is not None: kwargs["event_path"]=event_path
    result=run_source(source_id,**kwargs)
    result["version"]="e37-manual-alpha-v1"
    result["manual_source_allowlist"]=list(MANUAL_SOURCES)
    result["persist_requested"]=bool(persist)
    result["execution_authority"]=False
    result["paper_entry_authority"]=False
    result["strategy_mutation_authority"]=False
    result["threshold_mutation_authority"]=False
    result["membership_mutation_authority"]=False
    result["automatic_worker"]=False
    result["live_capital_allowed"]=False
    return result
