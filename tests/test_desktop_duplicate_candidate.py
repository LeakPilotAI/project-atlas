from app.services.paper_financial_replay import number
from test_quality_dips_autonomous_paper import candidate, entry, monitor, setup


def test_used_signal_refuses_before_effect_without_unknown(tmp_path):
    n=setup(tmp_path);b=candidate(n)
    assert entry(n)['filled']
    assert monitor(n,b,'exit','101',{'classification':'THESIS_BROKEN'})['filled']
    before=n.engine.ledger.snapshot()
    outcome=entry(n,'same-candidate-second-command')
    assert not outcome['filled'] and outcome['reason']=='CANDIDATE_ORIGIN_ALREADY_USED'
    assert n.engine.ledger.snapshot()==before and n.engine.status()=='RUNNING'
    assert number(before['positions'][next(iter(before['positions']))]['remaining'])==0
