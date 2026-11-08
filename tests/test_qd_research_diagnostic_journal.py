import json
import pytest
from scripts.observation_runtime.qd_research_diagnostic_journal import journal_diagnostic, inspect_diagnostic_journal, plan_interrupted_journal_recovery, export_recoverable_journal, verify_recovery_export

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


def test_recovery_plan_preserves_complete_journal(tmp_path):
    path=tmp_path/'journal.jsonl'
    journal_diagnostic(sample(),path=path)
    original=path.read_bytes()
    plan=plan_interrupted_journal_recovery(path=path)
    assert plan['status']=='ALREADY_COMPLETE'
    assert path.read_bytes()==original

def test_recovery_plan_isolates_trailing_fragment_without_mutation(tmp_path):
    path=tmp_path/'journal.jsonl'
    journal_diagnostic(sample(),path=path)
    path.write_bytes(path.read_bytes()+b'{"interrupted":')
    original=path.read_bytes()
    plan=plan_interrupted_journal_recovery(path=path)
    assert plan['status']=='TRAILING_FRAGMENT_REQUIRES_OPERATOR_REVIEW'
    assert plan['recoverable_records']==1
    assert plan['trailing_fragment_bytes']==len(b'{"interrupted":')
    assert plan['mutation_authorized'] is False
    assert path.read_bytes()==original

@pytest.mark.parametrize('corrupt', ['no_complete_record','malformed_complete_line','complete_corrupt_prefix'])
def test_recovery_plan_refuses_nonrecoverable_history(tmp_path,corrupt):
    path=tmp_path/'journal.jsonl'
    if corrupt=='no_complete_record': path.write_bytes(b'{"unfinished":')
    elif corrupt=='malformed_complete_line': path.write_bytes(b'not-json\n')
    else: path.write_bytes(b'not-json\n{"unfinished":')
    original=path.read_bytes()
    with pytest.raises(ValueError): plan_interrupted_journal_recovery(path=path)
    assert path.read_bytes()==original


def test_export_verified_prefix_preserves_damaged_source(tmp_path):
    src=tmp_path/'damaged.jsonl'; dst=tmp_path/'recovered.jsonl'
    journal_diagnostic(sample(),path=src)
    valid=src.read_bytes()
    src.write_bytes(valid+b'{"partial":')
    damaged=src.read_bytes()
    result=export_recoverable_journal(source=src,destination=dst)
    assert result['completed_records']==1
    assert result['resume_authorized'] is False
    assert src.read_bytes()==damaged and dst.read_bytes()==valid
    assert inspect_diagnostic_journal(path=dst)['completed_records']==1

def test_export_refuses_existing_destination(tmp_path):
    src=tmp_path/'damaged.jsonl';dst=tmp_path/'existing.jsonl'
    journal_diagnostic(sample(),path=src)
    src.write_bytes(src.read_bytes()+b'{"partial":')
    dst.write_text('preserve')
    with pytest.raises(ValueError): export_recoverable_journal(source=src,destination=dst)
    assert dst.read_text()=='preserve'

def test_export_refuses_corrupt_completed_prefix(tmp_path):
    src=tmp_path/'damaged.jsonl';dst=tmp_path/'export.jsonl'
    src.write_bytes(b'bad-json\n{"partial":')
    with pytest.raises(ValueError): export_recoverable_journal(source=src,destination=dst)
    assert not dst.exists()

def test_export_refuses_complete_source(tmp_path):
    src=tmp_path/'complete.jsonl';dst=tmp_path/'export.jsonl'
    journal_diagnostic(sample(),path=src)
    with pytest.raises(ValueError): export_recoverable_journal(source=src,destination=dst)
    assert not dst.exists()


def test_recovery_receipt_verifies_exact_export(tmp_path):
    src=tmp_path/'damaged.jsonl';dst=tmp_path/'export.jsonl'
    journal_diagnostic(sample(),path=src)
    src.write_bytes(src.read_bytes()+b'{"partial":')
    receipt=export_recoverable_journal(source=src,destination=dst)
    verified=verify_recovery_export(source=src,destination=dst,receipt=receipt)
    assert verified['status']=='VERIFIED_FOR_OPERATOR_REVIEW'
    assert verified['resume_authorized'] is False

@pytest.mark.parametrize('mutate',['source','destination','receipt'])
def test_recovery_receipt_refuses_tampering(tmp_path,mutate):
    src=tmp_path/'damaged.jsonl';dst=tmp_path/'export.jsonl'
    journal_diagnostic(sample(),path=src)
    src.write_bytes(src.read_bytes()+b'{"partial":')
    receipt=export_recoverable_journal(source=src,destination=dst)
    if mutate=='source': src.write_bytes(src.read_bytes()+b'X')
    elif mutate=='destination': dst.write_bytes(dst.read_bytes()+b'X')
    else: receipt['export_sha256']='0'*64
    with pytest.raises(ValueError): verify_recovery_export(source=src,destination=dst,receipt=receipt)
