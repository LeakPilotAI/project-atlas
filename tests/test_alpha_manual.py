import httpx,pytest
from datetime import datetime,timezone
from app.services.alpha_manual import manual_run,MANUAL_SOURCES
NOW=datetime(2026,10,5,12,tzinfo=timezone.utc)

def transport(body):
    return httpx.MockTransport(lambda req:httpx.Response(200,headers={"content-type":"text/html"},text=body,request=req))

def test_allowlist_is_exact_and_excludes_non_announcement_source():
    assert MANUAL_SOURCES==("federal_reserve","sec")
    with pytest.raises(ValueError): manual_run("hyperliquid_docs",persist=False,now=NOW)

def test_manual_fed_persists_only_supported_candidate(tmp_path):
    html="<a href='/newsevents/pressreleases/monetary20261005a.htm'>FOMC issues monetary policy statement</a>"
    r=manual_run("federal_reserve",persist=True,telemetry_path=tmp_path/"fetch",raw_path=tmp_path/"raw",event_path=tmp_path/"events",now=NOW,transport=transport(html))
    assert r["accepted_count"]==1 and len(r["event_ids"])==1
    assert r["execution_authority"] is False and r["paper_entry_authority"] is False
    assert r["strategy_mutation_authority"] is False and r["threshold_mutation_authority"] is False

def test_manual_dry_run_does_not_persist(tmp_path):
    html="<a href='/newsevents/pressreleases/monetary20261005a.htm'>FOMC issues monetary policy statement</a>"
    r=manual_run("federal_reserve",persist=False,telemetry_path=tmp_path/"fetch",raw_path=tmp_path/"raw",event_path=tmp_path/"events",now=NOW,transport=transport(html))
    assert r["candidate_count"]==1 and r["accepted_count"]==0
    assert not (tmp_path/"events").exists()

def test_cooldown_cannot_be_bypassed_by_manual_run(tmp_path):
    html="<a href='/newsevents/pressreleases/monetary20261005a.htm'>FOMC issues monetary policy statement</a>"
    kw=dict(persist=False,telemetry_path=tmp_path/"fetch",raw_path=tmp_path/"raw",event_path=tmp_path/"events",transport=transport(html))
    first=manual_run("federal_reserve",now=NOW,**kw)
    second=manual_run("federal_reserve",now=NOW,**kw)
    assert first["fetch_outcome"]=="FETCHED" and second["fetch_outcome"]=="COOLDOWN"
    assert second["candidate_count"]==0
