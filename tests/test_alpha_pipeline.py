import json,httpx
from datetime import datetime,timezone
from app.services.alpha_pipeline import run_source
NOW=datetime(2026,10,5,12,tzinfo=timezone.utc)

def transport(body):
    def handler(req):
        return httpx.Response(200,headers={"content-type":"text/html"},text=body,request=req)
    return httpx.MockTransport(handler)

def test_manual_pipeline_fetches_extracts_and_ingests_supported_fed_event(tmp_path):
    html="<a href='/newsevents/pressreleases/monetary20261005a.htm'>FOMC issues monetary policy statement</a>"
    result=run_source("federal_reserve",telemetry_path=tmp_path/"fetch",raw_path=tmp_path/"raw",event_path=tmp_path/"events",now=NOW,transport=transport(html))
    assert result["candidate_count"]==1 and result["accepted_count"]==1
    assert result["execution_authority"] is False and result["automatic_worker"] is False

def test_response_body_is_not_written_to_fetch_telemetry(tmp_path):
    marker="UNTRUSTED_FIXTURE_MARKER"
    result=run_source("federal_reserve",telemetry_path=tmp_path/"fetch",raw_path=tmp_path/"raw",event_path=tmp_path/"events",now=NOW,transport=transport(marker))
    assert result["candidate_count"]==0
    assert marker not in (tmp_path/"fetch").read_text()
    row=json.loads((tmp_path/"fetch").read_text().splitlines()[0])
    assert "_body" not in row and "body_sha256" in row

def test_sec_without_supported_time_or_relevance_stays_unpersisted(tmp_path):
    html="<a href='/newsroom/press-releases/2026-100'>SEC announces enforcement settlement with Example Corp</a>"
    result=run_source("sec",telemetry_path=tmp_path/"fetch",raw_path=tmp_path/"raw",event_path=tmp_path/"events",now=NOW,transport=transport(html))
    assert result["candidate_count"]==0 and result["accepted_count"]==0
    assert not (tmp_path/"events").exists()
