"""Existing non-analyst contract and ratio evidence tests; no new estimator."""
import json
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal

import pytest
from app.investment.enums import DataQuality
from app.investment.free_research_providers import FreeResearchBundle
from app.investment.models import MeasuredValue
from app.investment.quality_dips_v2_valuation import build_normalization_window
from app.investment.sec_edgar_research import valuation
from app.services.quality_dips_research_only import project_explicit_research
from test_free_research_pipeline import NOW, bars, client, facts, normalized
from test_quality_dips_valuation_admission import current_row


@pytest.mark.parametrize('method', ['HISTORICAL_MULTIPLE', 'SECTOR_RELATIVE', 'DCF', 'OWNER_EARNINGS', 'MANUAL_RESEARCH'])
def test_explicit_nonanalyst_evidence_uses_original_v3_rules(method):
    row = current_row()
    for source in row['valuation_sources']:
        source['provenance'] = method
    result = project_explicit_research([row], now=NOW)[0]['quality_dips_v2']
    assert result['normalization_value'] == {'conservative':130, 'base':140, 'optimistic':150}
    assert all(s['provenance'] == method for s in result['valuation_provenance'])
    v3 = result['quality_dips_v3']
    assert v3['fair_value_anchor'] == 140 and v3['entry_ladder']['ready']
    assert [r['limit_price'] for r in v3['entry_ladder']['levels']] == [119, 112, 105, 98]
    assert v3['live_capital_allowed'] is False


@pytest.mark.parametrize('damage', ['fundamentals', 'valuation', 'thesis', 'evidence'])
def test_nonanalyst_estimates_do_not_bypass_other_entry_gates(damage):
    row = current_row()
    if damage in ('fundamentals', 'valuation'): row['components'][damage] = 10
    elif damage == 'thesis': row['thesis'] = 'BROKEN'
    else: row['evidence_quality'] = 'LOW'
    out = project_explicit_research([row], now=NOW)[0]['quality_dips_v2']['quality_dips_v3']
    assert not out['entry_ladder']['ready'] and out['blockers']


def price(now=NOW):
    return MeasuredValue.of(20, source='ALPACA_IEX', timestamp=now, retrieved_at=now)


def test_aged_fundamentals_cannot_remain_fresh_because_flag_was_not_restamped():
    funds = normalized()
    later = NOW+timedelta(days=50)
    out = valuation(funds, price(later), now=later)
    assert not out['pe'].availability and not out['ps'].availability


@pytest.mark.parametrize('damage', ['issuer', 'period', 'source', 'effective_time', 'future_receipt', 'numeric_proof', 'missing_proof'])
def test_mismatched_financial_proof_does_not_publish_current_ratio(damage):
    funds = normalized()
    fact = funds['earnings']
    note = json.loads(fact.notes)
    if damage == 'issuer': note['cik'] = '0000000001'
    elif damage == 'period': note['period_end'] = '2026-06-30'
    elif damage == 'source': fact.source = 'UNVERIFIED_FOREIGN_DATA'
    elif damage == 'effective_time': fact.effective_timestamp = NOW+timedelta(seconds=1)
    elif damage == 'future_receipt': fact.retrieved_at = NOW+timedelta(seconds=1)
    elif damage == 'numeric_proof': note['exact_decimal'] = '999999'
    elif damage == 'missing_proof': note = {}
    fact.notes = json.dumps(note)
    out = valuation(funds, price(), now=NOW)
    assert not out['pe'].availability and not out['earnings_yield'].availability
    # A bad earnings field must not erase independently valid cash-flow evidence.
    assert out['price_to_fcf'].availability


@pytest.mark.parametrize('damage', ['missing_earnings', 'negative_earnings', 'negative_fcf', 'missing_shares'])
def test_unusable_reported_inputs_do_not_generate_estimates(damage):
    funds = normalized()
    if damage.startswith('missing_'): funds.pop('earnings' if damage.endswith('earnings') else 'shares_outstanding')
    else:
        key = 'earnings' if damage.endswith('earnings') else 'free_cash_flow'
        funds[key].value = -abs(funds[key].value)
        proof = json.loads(funds[key].notes)
        proof['exact_decimal'] = str(funds[key].value)
        funds[key].notes = json.dumps(proof)
    original = deepcopy(funds)
    out = valuation(funds, price(), now=NOW)
    field = 'price_to_fcf' if damage == 'negative_fcf' else 'pe'
    assert not out[field].availability
    assert all(not out[name].availability for name in ('target_low_price','target_mean_price','target_high_price'))
    assert funds == original


def test_method_label_alone_does_not_certify_history_or_dispersion():
    # Characterize the existing formatter, NOT acceptance of a new method.
    # There is no history-series schema or dispersion limit in this contract.
    sources = [{'value':v,'provenance':'HISTORICAL_MULTIPLE','as_of':NOW.isoformat()}
               for v in (1, 100, 10000)]
    out = build_normalization_window(sources, now=NOW)
    assert out['complete'] and out['source_count'] == 3
    assert out['live_capital_allowed'] is False
    assert 'history_verified' not in out


@pytest.mark.parametrize('damage', ['wrong_units', 'ambiguous_json', 'stale_shares', 'missing_timestamp'])
def test_share_evidence_cannot_create_a_market_cap_basis(damage):
    funds = normalized()
    share = funds['shares_outstanding']
    proof = json.loads(share.notes)
    if damage == 'wrong_units':
        proof['evidence'][0]['units'] = 'USD'
        share.notes = json.dumps(proof)
    elif damage == 'ambiguous_json': share.notes = '{"cik":"0000789019","cik":"0000000001"}'
    elif damage == 'stale_shares':
        share.timestamp = share.effective_timestamp = NOW-timedelta(days=60)
        share.quality = DataQuality.FRESH  # A copied quality label is not proof.
    else: share.timestamp = share.effective_timestamp = None
    out = valuation(funds, price(), now=NOW)
    assert not any(v.availability for v in out.values())


def test_extreme_positive_multiple_is_not_clipped_into_a_cheap_stock():
    from app.investment.scoring import score_valuation
    payload = facts()
    for row in payload['facts']['us-gaap']['NetIncomeLoss']['units']['USD']:
        row['val'] = str(Decimal(str(row['val'])) / 10000)
    funds = normalized(payload)
    out = valuation(funds, price(), now=NOW)
    assert out['pe'].value == pytest.approx(200 / .0046)
    assert score_valuation({'pe':out['pe']})[0] == 15
    assert not out['target_mean_price'].availability


def test_old_reference_flag_cannot_publish_market_cap_from_bundle(tmp_path):
    def response(url):
        if '/assets/' in url:
            return {'symbol':'MSFT','id':'SYNTHETIC-ASSET','class':'us_equity',
                    'status':'active','tradable':True,'fractionable':True,'exchange':'NASDAQ'}
        if '/bars?' in url: return bars()
        if '/calendar?' in url: return [{'date':'2026-10-28','open':'09:30','close':'16:00'}]
        if 'company_tickers' in url: return {'0':{'cik_str':789019,'ticker':'MSFT'}}
        return facts()
    c,_,_,_=client(tmp_path,response=response)
    bundle=FreeResearchBundle(client=c,now=lambda:NOW,
        reference_price=lambda _:price(NOW-timedelta(minutes=16)))
    result=bundle.load('MSFT')
    assert not result['fundamentals']['market_cap'].availability
    assert not any(v.availability for v in result['valuation'].values())
    assert result['paper_eligible'] is False
