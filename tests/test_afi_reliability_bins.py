import json
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest
from app.backtest.forecast_evaluation import (
    ForecastEvidenceRefused,
    probability_reliability,
)
from app.backtest.forecast_report import (
    reliability_diagnostics,
    render_accountability_report,
)
from test_afi_paired_comparison import row


def test_fixed_bin_edges_and_probability_one():
    result=probability_reliability([(0,0),(.1,1),(.999,1),(1,1)])
    assert [(b['bin'],b['n']) for b in result['calibration_bins']]==[(0,1),(1,1),(9,2)]
    assert result['probability_n']==4


def test_weighted_gap_uses_actual_probability_denominator():
    result=probability_reliability([(.1,0),(.1,0),(.1,0),(.9,0)])
    assert result['expected_calibration_error']==pytest.approx(.3)
    assert result['brier']==pytest.approx(.21) and result['uninformative_half_probability_brier']==.25


@pytest.mark.parametrize('pair',[(True,1),(.2,True),(-.1,0),(1.1,1),(float('nan'),0),(.5,2)])
def test_malformed_probability_pairs_refuse(pair):
    with pytest.raises(ForecastEvidenceRefused):probability_reliability([pair])


def test_empty_bins_and_absent_probabilities_are_unknown():
    result=reliability_diagnostics([row(5,probability_up=None)])['cohorts'][0]
    assert result['probability_n']==0 and result['no_probability_n']==1 and result['expected_calibration_error'] is None
    assert len(result['calibration_bins'])==10 and all(b['status']=='EMPTY' and b['mean_probability'] is None for b in result['calibration_bins'])
    assert result['calibration_bins'][-1]['upper_inclusive'] is True
    assert not result['calibration_bins'][0]['upper_inclusive']


def test_partial_legacy_probability_subset_has_explicit_denominators():
    values=[row(5,probability_up=.8),row(5,2,probability_up=None),row(5,3),row(5,4,probability_up=.4,status='FORECAST_ONLY',actual=None)]
    before=deepcopy(values);cohort=reliability_diagnostics(values)['cohorts'][0]
    assert (cohort['resolved_n'],cohort['pending_n'],cohort['probability_n'],cohort['unrecorded_probability_n'],cohort['no_probability_n'])==(3,1,1,1,1)
    assert cohort['brier']==pytest.approx(.04) and cohort['status']=='PARTIAL_LEGACY_INPUTS' and values==before


def test_repeated_targets_cannot_establish_calibrated_reliability():
    values=[row(5,probability_up=.5,forecast_sha256=f'{i+1000:064x}',issued_at=f'2026-10-01T00:{i+1:02d}:00Z') for i in range(20)]
    result=reliability_diagnostics(values);cohort=result['cohorts'][0];populated=[b for b in cohort['calibration_bins'] if b['n']]
    assert cohort['probability_n']==20 and cohort['distinct_target_n']==1 and cohort['status']=='OVERLAPPING_TARGET_EVIDENCE'
    assert populated[0]['status']=='OVERLAPPING_TARGET_EVIDENCE'
    for flag in ('calibration_established','independent_samples_established','predictive_skill_established','production_approved','trading_authority'):assert result[flag] is False


def test_model_manifest_and_interval_contexts_are_not_pooled():
    values=[row(5,probability_up=.8),row(10,probability_up=.8),
            row(5,2,probability_up=.8,forecast_dataset_manifest_sha256='9'*64),
            row(5,3,probability_up=.8,interval={'lower':100,'upper':104,'level':.8})]
    result=reliability_diagnostics(values);assert len(result['cohorts'])==4 and all(c['probability_n']==1 for c in result['cohorts'])


def test_duplicate_forecasts_and_equivalent_utc_cases_refuse():
    a=row(5,probability_up=.8)
    with pytest.raises(ForecastEvidenceRefused):reliability_diagnostics([a,deepcopy(a)])
    b={**a,'forecast_sha256':'9'*64,'issued_at':'2026-10-01T01:01:00+01:00'}
    with pytest.raises(ForecastEvidenceRefused):reliability_diagnostics([a,b])


def test_probability_evidence_survives_unrelated_price_square_overflow():
    value=row(5,forecast_point=1e200,probability_up=.8)
    result=reliability_diagnostics([value])['cohorts'][0];assert result['brier']==pytest.approx(.04)


@pytest.mark.parametrize('partial',[False,True])
def test_backend_browser_reliability_parity(partial):
    values=[row(5,probability_up=.1),row(5,2,probability_up=1),row(10,probability_up=.6)]
    if partial:del values[0]['probability_up']
    expected=reliability_diagnostics(values)
    viewer=Path(__file__).resolve().parents[1]/'frontend/offline/forecast-accountability/view.cjs'
    script="const v=require(process.argv[1]);console.log(JSON.stringify(v.reliabilityDiagnostics(JSON.parse(process.argv[2]))));"
    checked=subprocess.run(['C:/Program Files/nodejs/node.exe','-e',script,str(viewer),json.dumps(values)],capture_output=True,text=True,timeout=10,check=True)
    from app.backtest.forecast_report import _same_score
    assert _same_score(expected,json.loads(checked.stdout))


def test_actual_published_report_renders_reliability_without_rewriting_evidence():
    path=Path(__file__).parent/'fixtures/afi-probability-baseline-v1/corrected-browser.json';raw=path.read_bytes()
    report=json.loads(json.loads(raw)['report_json']);html=render_accountability_report(report)
    assert 'Probability reliability evidence' in html and 'Weighted bin gap' in html
    assert path.read_bytes()==raw


@pytest.mark.parametrize('holdout',[False,True])
def test_actual_replay_and_holdout_html_keep_bin_denominators(holdout):
    from html.parser import HTMLParser

    from app.backtest.forecast_baselines import PROBABILITY_METHOD
    from app.backtest.forecast_dashboard import (
        render_probability_holdout,
        render_probability_replay,
    )
    from app.backtest.forecast_replay import freeze_probability_protocol
    from test_afi_baselines import ASOF, ASSET, history
    from test_afi_replay import issue

    class Rows(HTMLParser):
        def __init__(self):super().__init__();self.rows=[];self.current=[];self.text=None
        def handle_starttag(self,tag,attrs):
            if tag=='tr':self.current=[]
            if tag=='td':self.text=''
        def handle_data(self,data):
            if self.text is not None:self.text+=data
        def handle_endtag(self,tag):
            if tag=='td':self.current.append(self.text);self.text=None
            if tag=='tr':self.rows.append(self.current)
    review=history();issues=[issue(25),issue(26)]
    if holdout:
        protocol=freeze_probability_protocol(review,asset_id=ASSET,selection_issues=[issue(20),issue(21)],holdout_issues=issues,
                       frozen_at=issue(24),evidence_asof=ASOF,lookback=5)
        html=render_probability_holdout(review,protocol,expected_protocol_sha256=protocol['protocol_sha256'],evidence_asof=ASOF)
        assert 'Frozen-protocol probability holdout' in html
    else:html=render_probability_replay(review,asset_id=ASSET,issued_times=issues,evidence_asof=ASOF,probability_method=PROBABILITY_METHOD,lookback=5)
    parsed=Rows();parsed.feed(html);bins=[row for row in parsed.rows if len(row)==13]
    assert len(bins)==10 and sum(int(row[7]) for row in bins)==2
    assert all(row[2]=='2' and row[3]=='2' for row in bins)
    for entry in bins:
        if entry[7]=='0':assert entry[9]==entry[10]=='Unavailable' and entry[12]=='EMPTY'
    gap=sum(int(row[7])*abs(float(row[9])-float(row[10])) for row in bins if row[7]!='0')/2
    assert all(float(row[11])==pytest.approx(gap) for row in bins)
