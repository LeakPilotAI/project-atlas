import json
from app.services.alpha_operator import diagnostics

def test_operator_diagnostics_are_read_only(tmp_path):
    tele=tmp_path/"fetch.jsonl"
    tele.write_text(json.dumps({"source_id":"sec","finished_at":"2026-10-05T12:00:00+00:00","outcome":"FETCHED","http_status":200,"parse_result":"NO_SUPPORTED_CLAIM"})+"\n")
    body=diagnostics(tele)
    assert body["ok"] is True and body["sources"]["sec"]["last_outcome"]=="FETCHED"
    assert body["execution_authority"] is False
    assert body["paper_entry_authority"] is False
    assert body["automatic_worker"] is False
    assert body["live_capital_allowed"] is False
