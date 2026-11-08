import json
import pytest
from scripts.observation_runtime.qd_research_diagnostic_journal import journal_diagnostic

def sample():
    return {"schema":"ATLAS_QD_REPEATED_PRICES_ONLY_V1", "symbols":["MSFT","SPY"],
            "rounds_completed":2,"refused_count":1,
            "operational_source_accepted":False,"paper_fill_authorized":False,
            "live_order_authorized":False,"results":[{"secret":"never journal this"}]}

def test_append_only_sanitized_records(tmp_path):
    path=tmp_path/"research.jsonl"
    for _ in range(2):
        journal_diagnostic(sample(),path=path,timestamp="2026-11-07T00:00:00+00:00")
    lines=path.read_text().splitlines()
    assert len(lines)==2 and all(json.loads(line)["refused_count"]==1 for line in lines)
    assert "secret" not in path.read_text()
    assert all(json.loads(line)["paper_fill_authorized"] is False for line in lines)

@pytest.mark.parametrize("field,value",[("paper_fill_authorized",True),
    ("operational_source_accepted",True),("live_order_authorized",True),
    ("refused_count",-1),("rounds_completed",4),("symbols",["SPY","SPY"])])
def test_refusal_never_creates_journal(tmp_path,field,value):
    result=sample();result[field]=value
    path=tmp_path/"research.jsonl"
    with pytest.raises(ValueError):
        journal_diagnostic(result,path=path)
    assert not path.exists()

def test_refuse_symlink(tmp_path):
    destination=tmp_path/"destination"
    destination.write_text("preserve")
    link=tmp_path/"link"
    try: link.symlink_to(destination)
    except OSError: pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError): journal_diagnostic(sample(),path=link)
    assert destination.read_text()=="preserve"
