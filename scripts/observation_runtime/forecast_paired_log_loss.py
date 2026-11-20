"""Matched-case probability log loss. No clipping, pooled model errors or winner."""
from __future__ import annotations

import math
from html import escape
from statistics import fmean

from app.backtest.forecast_report import _pair_us, paired_probability_diagnostics

from scripts.observation_runtime.forecast_log_loss import log_loss_diagnostics

PRECISION=32*2**-52


def _mean(cases,side):
    if not cases:return 'UNAVAILABLE',None
    if any(c[side+'_loss_state']=='INFINITE' for c in cases):return 'INFINITE',None
    values=[c[side+'_log_loss'] for c in cases];mean=fmean(values)
    if mean==0 and any(v>0 for v in values):return 'UNAVAILABLE_NUMERIC_RANGE',None
    return 'FINITE',mean


def _difference(a,b,pa,pb):
    if a['loss_state']=='INFINITE' and b['loss_state']=='INFINITE':return 'UNDEFINED_BOTH_INFINITE',None
    if a['loss_state']=='INFINITE':return 'POSITIVE_INFINITY',None
    if b['loss_state']=='INFINITE':return 'NEGATIVE_INFINITY',None
    delta=a['log_loss']-b['log_loss']
    if pa!=pb and abs(delta)<=PRECISION*max(abs(a['log_loss']),abs(b['log_loss'])):
        return 'UNAVAILABLE_NUMERIC_RANGE',None
    return 'FINITE',delta


def paired_log_loss_diagnostics(rows, *, asof, model_pairs=None,minimum_samples=20):
    source=paired_probability_diagnostics(rows,asof=asof,model_pairs=model_pairs,minimum_samples=minimum_samples)
    single=log_loss_diagnostics(rows,minimum_samples=minimum_samples)
    by_hash={r['forecast_sha256']:r for r in rows}
    scores={c['forecast_sha256']:c for group in single['cohorts'] for c in group['cases']};comparisons=[]
    for original in source['comparisons']:
        pair={k:original[k] for k in ('a','b','shared_n','a_only_n','b_only_n','pending_shared_n','outcome_conflict_n',
            'reference_conflict_n','missing_provenance_n','unassessed_shared_n','point_paired_n','probability_paired_n',
            'missing_probability_n','a_missing_probability_n','b_missing_probability_n','both_missing_probability_n',
            'distinct_target_n','actual_up_n','flat_outcome_n','status')}
        cases=[];targets=set()
        for case in original['cases']:
            item={k:case[k] for k in ('case_id','a_forecast_sha256','b_forecast_sha256','status','a_probability_state','b_probability_state')}
            item.update(actual_up=None,a_loss_state=None,b_loss_state=None,a_log_loss=None,b_log_loss=None,
                        difference_state='UNAVAILABLE',a_minus_b_log_loss=None)
            if case['status']=='PROBABILITY_PAIRED':
                a,b=(scores[case[k]] for k in ('a_forecast_sha256','b_forecast_sha256'))
                pa,pb=(by_hash[case[k]]['probability_up'] for k in ('a_forecast_sha256','b_forecast_sha256'))
                state,delta=_difference(a,b,pa,pb);targets.add(_pair_us(by_hash[case['a_forecast_sha256']]['target_at']))
                item.update(status='LOG_LOSS_PAIRED',actual_up=a['actual_up'],a_loss_state=a['loss_state'],b_loss_state=b['loss_state'],
                    a_log_loss=a['log_loss'],b_log_loss=b['log_loss'],difference_state=state,a_minus_b_log_loss=delta)
            cases.append(item)
        paired=[c for c in cases if c['status']=='LOG_LOSS_PAIRED'];n=len(paired)
        if n!=original['probability_paired_n']:raise ValueError('Paired log-loss denominator mismatch')
        a_state,a_mean=_mean(paired,'a');b_state,b_mean=_mean(paired,'b')
        counts={s:sum(c['difference_state']==s for c in paired) for s in ('FINITE','POSITIVE_INFINITY','NEGATIVE_INFINITY','UNDEFINED_BOTH_INFINITE','UNAVAILABLE_NUMERIC_RANGE')}
        delta=None
        if not n:state='UNAVAILABLE'
        elif a_state==b_state=='INFINITE':state='UNDEFINED_BOTH_INFINITE'
        elif a_state=='INFINITE':state='POSITIVE_INFINITY'
        elif b_state=='INFINITE':state='NEGATIVE_INFINITY'
        elif a_state!='FINITE' or b_state!='FINITE' or counts['UNAVAILABLE_NUMERIC_RANGE']:state='UNAVAILABLE_NUMERIC_RANGE'
        else:
            values=[c['a_minus_b_log_loss'] for c in paired];delta=fmean(values);scale=max(fmean(abs(v) for v in values),a_mean,b_mean)
            if any(values) and abs(delta)<=PRECISION*scale:state='UNAVAILABLE_NUMERIC_RANGE';delta=None
            else:state='FINITE'
        pair.update(a_loss_state=a_state,b_loss_state=b_state,a_mean_log_loss=a_mean,b_mean_log_loss=b_mean,
            a_infinite_loss_n=sum(c['a_loss_state']=='INFINITE' for c in paired),b_infinite_loss_n=sum(c['b_loss_state']=='INFINITE' for c in paired),
            finite_difference_n=counts['FINITE'],positive_infinite_difference_n=counts['POSITIVE_INFINITY'],
            negative_infinite_difference_n=counts['NEGATIVE_INFINITY'],undefined_difference_n=counts['UNDEFINED_BOTH_INFINITE'],
            numeric_range_difference_n=counts['UNAVAILABLE_NUMERIC_RANGE'],difference_state=state,a_minus_b_mean_log_loss=delta,
            half_probability_mean_log_loss=math.log(2) if n else None,cases=cases)
        if len(targets)!=pair['distinct_target_n']:raise ValueError('Paired log-loss target count mismatch')
        comparisons.append(pair)
    return {'schema':'AFI_PAIRED_LOG_LOSS_DIAGNOSTICS_V1',**{k:source[k] for k in ('asof','minimum_samples','status','selection_mode','model_n','possible_pair_n')},
        'comparisons':comparisons,'binary_event':source['binary_event'],'logarithm_base':'NATURAL','epsilon_clipping_applied':False,
        'difference_policy':'PAIRED_CASE_MEAN_NEAR_ZERO_REFUSAL_32_EPS','missing_inputs_not_inferred':True,
        'independent_samples_established':False,'winner_established':False,'calibration_established':False,
        'predictive_skill_established':False,'production_approved':False,'trading_authority':False}


def with_paired_log_loss(rows, *, asof,model_pairs=None,minimum_samples=20):
    return {**log_loss_diagnostics(rows,minimum_samples=minimum_samples),'schema':'AFI_LOG_LOSS_DIAGNOSTICS_V2',
        'paired_log_loss_diagnostics':paired_log_loss_diagnostics(rows,asof=asof,model_pairs=model_pairs,minimum_samples=minimum_samples)}


def render_paired_log_loss(report):
    import json
    rows=[]
    for p in report['comparisons']:
        a,b=json.loads(p['a']),json.loads(p['b'])
        values=(a['asset_id'],a['model']+' / '+str(a.get('lookback')),b['model']+' / '+str(b.get('lookback')),
                p['shared_n'],p['point_paired_n'],p['probability_paired_n'],p['pending_shared_n'],p['missing_probability_n'],
                p['outcome_conflict_n'],p['distinct_target_n'],p['a_loss_state'],p['b_loss_state'],p['a_mean_log_loss'],p['b_mean_log_loss'],
                p['difference_state'],p['a_minus_b_mean_log_loss'],p['status'])
        rows.append('<tr>'+''.join('<td>'+escape('Unavailable' if v is None else str(v))+'</td>' for v in values)+'</tr>')
    heads=('Asset','A','B','Shared','Point paired','Probability paired','Pending','Missing probabilities','Outcome conflicts','Distinct targets',
           'A state','B state','A mean','B mean','Difference state','A minus B mean','Sample evidence')
    return ('<h2>Matched-case logarithmic loss</h2><p>Shared compatible outcomes only. Both infinite is undefined, never a tie. '
      'Unstable near-zero differences remain unavailable; no winner, calibration or independent-sample claim.</p><table><tr>'+
      ''.join('<th>'+v+'</th>' for v in heads)+'</tr>'+''.join(rows)+'</table>')
