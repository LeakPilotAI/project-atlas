from datetime import UTC, datetime
from html.parser import HTMLParser

import pytest
from app.backtest.forecast_baselines import fit_baseline
from app.backtest.forecast_comparison import compare_forecasts, scenario_research
from app.backtest.forecast_dashboard import render_dashboard
from app.backtest.forecast_dataset import review_dataset
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from test_afi_baselines import ASOF, fit, history
from test_afi_dataset_integrity import encode, fixture


def equity_entry():
    import hashlib
    m,p=fixture();raw=encode(p);m["content_sha256"]=hashlib.sha256(raw).hexdigest()
    r=review_dataset(encode(m),raw,asof=ASOF)
    model=fit_baseline(r,asset_id="US_EQUITY:AAPL",issued_at=datetime(2026,10,19,20,1,tzinfo=UTC),evidence_asof=ASOF,lookback=2)
    return r,model


def test_multi_market_comparison_keeps_units_and_pending_outcomes_separate():
    crypto=history();r=compare_forecasts([(crypto,fit(crypto)),equity_entry()],evidence_asof=ASOF)
    assert {x["asset_class"] for x in r["rows"]}=={"CRYPTO","US_EQUITY"}
    assert {x["status"] for x in r["rows"]}=={"RESOLVED_SYNTHETIC","PENDING"}
    assert r["pooled_price_error"] is None and r["ranking"] is None
    assert all(x["accuracy_status"]=="INSUFFICIENT_EVIDENCE" for x in r["rows"])
    assert not r["predictive_skill_established"]


def test_duplicate_or_unbounded_comparison_refuses():
    r=history();entry=(r,fit(r))
    for entries in ([],[entry,entry],[entry]*65,[{"review":r}]):
        with pytest.raises(ForecastEvidenceRefused):compare_forecasts(entries,evidence_asof=ASOF)


def scenario(**changes):
    opts={"base_year":2026,"milestones":[2030,2040,2050],"annual_assumptions":{"bear":-.02,"base":.02,"bull":.05}}
    return scenario_research(**{**opts,**changes})


def test_long_horizon_scenarios_are_assumptions_and_never_price_guarantees():
    s=scenario();assert s==scenario()
    assert [r["year"] for r in s["milestones"]]==[2030,2040,2050]
    assert s["unit"]=="ILLUSTRATIVE_INDEX_NOT_ASSET_PRICE" and s["probabilities"] is None
    assert not s["coverage_guarantee"] and not s["trading_authority"]
    for r in s["milestones"]:
        v=r["conditional_index"];assert v["bear"]<v["base"]<v["bull"]


@pytest.mark.parametrize("change",[{"base_year":True},{"milestones":[2020]},{"milestones":[2030,2030]},
                                    {"milestones":[2200]},{"annual_assumptions":{"bear":.1,"base":0,"bull":.2}},
                                    {"annual_assumptions":{"bear":-1,"base":0,"bull":.2}},
                                    {"annual_assumptions":{"bear":0,"base":0,"bull":float('nan')}}])
def test_invalid_or_overconfident_scenario_inputs_refuse(change):
    with pytest.raises(ForecastEvidenceRefused):scenario(**change)


class AuditHTML(HTMLParser):
    def __init__(self):super().__init__();self.tags=[];self.attrs=[];self.text=[]
    def handle_starttag(self,tag,attrs):self.tags.append(tag);self.attrs.extend(attrs)
    def handle_data(self,data):self.text.append(data)


def test_dashboard_is_scriptless_accessible_escaped_and_honest():
    r=history();html=render_dashboard([(r,fit(r)),equity_entry()],evidence_asof=ASOF,title='<script>alert("x")</script>')
    parser=AuditHTML();parser.feed(html)
    assert not set(parser.tags)&{"script","iframe","form","button","img","link"}
    assert "caption" in parser.tags and ("scope","col") in parser.attrs
    assert not any(k.startswith('on') or k in ('src','href') for k,v in parser.attrs)
    text=' '.join(parser.text)
    assert "Production NO-GO" in text and "synthetic fixtures only" in text and "PENDING" in text
    assert '&lt;script&gt;' in html and '<script>' not in html
    assert 'default-src' in html and 'viewport' in html and 'overflow-x:auto' in html
