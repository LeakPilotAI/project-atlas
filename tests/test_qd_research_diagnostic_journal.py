import json
import pytest
from scripts.observation_runtime.qd_research_diagnostic_journal import journal_diagnostic, inspect_diagnostic_journal

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


def test_journal_inspection_detects_complete_append(tmp_path):
    path=tmp_path/'journal.jsonl'
    journal_diagnostic(sample(),path=path)
    journal_diagnostic(sample(),path=path)
    report=inspect_diagnostic_journal(path=path)
    assert report['completed_records']==2
    assert report['paper_fill_authorized'] is False

@pytest.mark.parametrize('damage',['truncated','invalid_json','authority','empty'])
def test_journal_inspection_refuses_corruption(tmp_path,damage):
    path=tmp_path/'journal.jsonl'
    journal_diagnostic(sample(),path=path)
    if damage=='truncated': path.write_bytes(path.read_bytes()[:-1])
    elif damage=='invalid_json': path.write_bytes(path.read_bytes()+b'not-json\n')
    elif damage=='empty': path.write_bytes(b'')
    else:
        record=json.loads(path.read_text());record['paper_fill_authorized']=True
        path.write_text(json.dumps(record)+'\n')
    with pytest.raises(ValueError): inspect_diagnostic_journal(path=path)
