import copy
import sqlite3
from datetime import timedelta

import pytest
from app.investment.offline_research import ResearchInputRefused
from test_retained_research import chart, populate

from scripts.observation_runtime import research_replay
from scripts.observation_runtime.market_replay import ReplayStore
from scripts.observation_runtime.research_replay import replay_research


def inputs():
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db);now,reference=populate(store)
        cutoff=now+timedelta(minutes=5)
        archive=store.history('SPY',now=cutoff)
    decisions=[now.replace(minute=30,second=0),now,cutoff]
    return archive,[reference],decisions


def test_all_decisions_remain_in_denominator_with_exact_vintage():
    archive,refs,decisions=inputs();before=copy.deepcopy((archive,refs,decisions))
    result=replay_research(archive,refs,decisions)
    assert result['planned_decision_n']==3
    assert [c['status'] for c in result['cases']]==['REFUSED','DESCRIPTIVE_RESEARCH_ONLY','REFUSED']
    assert result['status_counts']['REFUSED']==2 and result['status_counts']['DESCRIPTIVE_RESEARCH_ONLY']==1
    assert result['cases'][1]['report']['analysis']['relative_volume']==2
    assert result['cases'][0]['refusal_reason']=='DESCRIPTIVE_ANALYSIS_REFUSED'
    assert before==(archive,refs,decisions)
    assert result['trading_authorized'] is False and result['predictive_skill_established'] is False


def test_latest_available_reference_correction_never_changes_earlier_decision():
    archive,refs,decisions=inputs();first=decisions[1]
    correction={**refs[0],'available_at':(first+timedelta(seconds=20)).isoformat(),'previous_close':102}
    clocks=[first,first+timedelta(seconds=30)]
    original=replay_research(archive,refs,clocks)
    revised=replay_research(archive,refs+[correction],clocks)
    assert revised['cases'][0]==original['cases'][0]
    assert revised['cases'][1]['reference_sha256']!=original['cases'][1]['reference_sha256']
    assert revised['cases'][1]['report']['analysis']['previous_close']==102


def test_future_bar_values_cannot_change_earlier_per_decision_evidence():
    archive,refs,decisions=inputs();clock=decisions[1]
    with sqlite3.connect(':memory:') as db:
        store=ReplayStore(db)
        for raw in (999,1200):
            payload=chart([clock.replace(second=0)],price=raw)
            if raw==999:
                store.ingest(payload,observed_at=clock+timedelta(minutes=2),asset_class='US_ETF')
                future=store.history('SPY',now=decisions[-1])['rows'][0]
                one={**archive,'rows':archive['rows']+[future]}
            else:
                future={**future,'close':raw,'high':raw}
                two={**archive,'rows':archive['rows']+[future]}
    a=replay_research(one,refs,[clock]);b=replay_research(two,refs,[clock])
    assert a['cases']==b['cases']
    assert a['archive_sha256']!=b['archive_sha256']


def test_missing_reference_and_empty_history_are_explicit_not_negative_returns():
    archive,refs,decisions=inputs()
    missing=replay_research(archive,[],decisions)
    assert missing['status_counts']['INSUFFICIENT_REFERENCE']==3
    empty=replay_research({**archive,'rows':[]},refs,decisions)
    assert empty['status_counts']['INSUFFICIENT_HISTORY']==3
    assert all(c['report']['analysis'] is None for c in empty['cases'])


@pytest.mark.parametrize('fault',['duplicate_clock','clock_order','future_clock','truncated','duplicate_bar','reference_tie','future_reference','authority'])
def test_ambiguous_plans_refuse_before_results(fault):
    archive,refs,decisions=inputs()
    if fault=='duplicate_clock':decisions.append(decisions[-1])
    elif fault=='clock_order':decisions.reverse()
    elif fault=='future_clock':decisions[-1]+=timedelta(seconds=1)
    elif fault=='truncated':archive['more_retained_rows']=True
    elif fault=='duplicate_bar':archive['rows'].append(copy.deepcopy(archive['rows'][0]))
    elif fault=='reference_tie':refs.append({**refs[0],'previous_close':101})
    elif fault=='future_reference':refs[0]['available_at']=(decisions[-1]+timedelta(seconds=1)).isoformat()
    else:archive['network_authorized']=True
    with pytest.raises(ValueError):replay_research(archive,refs,decisions)


def test_budget_refuses_before_analysis_and_never_partially_selects_cases(monkeypatch):
    archive,refs,decisions=inputs()
    monkeypatch.setattr(research_replay,'MAX_ROW_DECISIONS',1)
    def forbidden(*args,**kwargs):raise AssertionError('analysis started despite budget refusal')
    monkeypatch.setattr(research_replay,'retained_research',forbidden)
    with pytest.raises(ResearchInputRefused,match='budget'):replay_research(archive,refs,decisions)
