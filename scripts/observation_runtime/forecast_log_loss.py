"""Opt-in recorded-probability log loss; no fitting, clipping or trading authority."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from html import escape
from statistics import fmean

from app.backtest.forecast_artifacts import publish_research_text
from app.backtest.forecast_dataset import _fields, _json
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_report import (
    BundleReader,
    _cohort,
    _report_time,
    reliability_diagnostics,
    render_accountability_report,
)


def _key(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def _group(row):
    interval=row.get('interval')
    binding='UNRECORDED' if 'interval' not in row else 'NONE' if interval is None else 'FLOAT64:'+struct.pack('>d',interval['level']).hex()
    return {**_cohort(row),'interval_binding':binding}


def log_loss_diagnostics(rows, *, minimum_samples=20):
    source=reliability_diagnostics(rows,minimum_samples=minimum_samples)
    groups={_key(c['cohort']):[] for c in source['cohorts']}
    for row in rows:groups[_key(_group(row))].append(row)
    cohorts=[]
    for context in source['cohorts']:
        cases=[];losses=[];infinite=zero=up=flat=0
        for row in groups[_key(context['cohort'])]:
            probability=row.get('probability_up');state='UNRECORDED' if 'probability_up' not in row else 'NONE' if probability is None else 'RECORDED'
            actual_up=actual_flat=loss=None
            outcome_state='PENDING' if row['status']!='RESOLVED' else 'UNRECORDED_PROBABILITY' if state=='UNRECORDED' else 'NO_PROBABILITY' if state=='NONE' else 'FINITE'
            if row['status']=='RESOLVED' and state=='RECORDED':
                actual_up=row['actual']>row['reference'];actual_flat=row['actual']==row['reference'];up+=actual_up;flat+=actual_flat
                if (actual_up and probability==0) or (not actual_up and probability==1):
                    outcome_state='INFINITE';infinite+=1
                else:
                    loss=max(0.0,-math.log(probability) if actual_up else -math.log1p(-probability));losses.append(loss);zero+=loss==0
            cases.append({'forecast_sha256':row['forecast_sha256'],'issued_at':row['issued_at'],'target_at':row['target_at'],
                'forecast_status':row['status'],'probability_state':state,'probability_up':probability,
                'actual_up':actual_up,'actual_flat':actual_flat,'loss_state':outcome_state,'log_loss':loss})
        n=context['probability_n']
        if len(losses)+infinite!=n:raise ForecastEvidenceRefused('Log-loss denominator mismatch')
        mean=fmean(losses) if losses and not infinite else None;baseline=math.log(2) if n else None
        underflow=mean==0 and any(value>0 for value in losses)
        if underflow:mean=None
        cohorts.append({**{k:context[k] for k in ('cohort','forecast_n','resolved_n','pending_n','probability_n','distinct_target_n',
                'unrecorded_probability_n','no_probability_n','input_status','status')},
            'finite_loss_n':len(losses),'infinite_loss_n':infinite,'zero_loss_n':zero,'actual_up_n':up,'flat_outcome_n':flat,
            'loss_state':'UNAVAILABLE' if not n else 'INFINITE' if infinite else 'UNAVAILABLE_NUMERIC_RANGE' if underflow else 'FINITE','mean_log_loss':mean,
            'half_probability_mean_log_loss':baseline,'mean_log_loss_minus_baseline':mean-baseline if mean is not None else None,
            'cases':cases})
    return {'schema':'AFI_LOG_LOSS_DIAGNOSTICS_V1','minimum_samples':minimum_samples,
        'input_scope':'CALLER_SUPPLIED_ACCOUNTABILITY_ROWS','denominator_scope':'RESOLVED_RECORDED_PROBABILITIES_ONLY',
        'binary_event':'PRICE_STRICTLY_ABOVE_REFERENCE; FLAT_IS_NOT_UP','logarithm_base':'NATURAL',
        'epsilon_clipping_applied':False,'cohorts':cohorts,'original_forecast_history_verified':False,
        'independent_samples_established':False,'calibration_established':False,'predictive_skill_established':False,'winner_established':False,
        'production_approved':False,'trading_authority':False,'startup_authorized':False,'network_authorized':False,'recovery_authorized':False}


def render_log_loss(report):
    rows=[]
    for c in report['cohorts']:
        k=c['cohort'];values=(k['asset_id'],k['model'],k['horizon'],c['resolved_n'],c['pending_n'],c['probability_n'],
            c['unrecorded_probability_n'],c['no_probability_n'],c['distinct_target_n'],c['infinite_loss_n'],
            c['loss_state'],c['mean_log_loss'],c['half_probability_mean_log_loss'],c['status'])
        rows.append('<tr>'+''.join('<td>'+escape('Unavailable' if v is None else str(v))+'</td>' for v in values)+'</tr>')
    heads=('Asset','Model','Horizon','Resolved','Pending','Recorded probability','Unrecorded','None','Distinct targets',
           'Impossible events','Loss state','Mean log loss','Half-probability baseline','Sample status')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Atlas probability log loss</title>'
        '<h1>Recorded probability log loss</h1><p>Synthetic diagnostic only. No calibration, skill or trading permission.</p>'
        '<p>Natural log. No epsilon clipping. An impossible event makes the cohort loss infinite, shown with an explicit count and unavailable numeric mean. Pending and missing probabilities are never zero losses. Flat is not UP.</p>'
        '<table><tr>'+''.join('<th>'+h+'</th>' for h in heads)+'</tr>'+''.join(rows)+'</table></html>')


def export_log_loss(*,bundle_root,request_name,output_root):
    reader=BundleReader(bundle_root);request=_json(reader.read(request_name))
    paired=type(request) is dict and request.get('schema')=='AFI_LOG_LOSS_REQUEST_V2'
    _fields(request,'schema report expected_report_sha256 minimum_samples'+(' model_pairs' if paired else ''))
    if request['schema'] not in ('AFI_LOG_LOSS_REQUEST_V1','AFI_LOG_LOSS_REQUEST_V2'):raise ForecastEvidenceRefused('Explicit log-loss request required')
    raw=reader.read(request['report']);identity=hashlib.sha256(raw).hexdigest()
    if len(raw)>1_000_000 or type(request['expected_report_sha256']) is not str or identity!=request['expected_report_sha256']:
        raise ForecastEvidenceRefused('Exact bounded source report commitment required')
    original=_json(raw);render_accountability_report(original)  # Reconcile full supplied report/row evidence, without writes.
    if paired:
        from scripts.observation_runtime.forecast_paired_log_loss import (
            render_paired_log_loss,
            with_paired_log_loss,
        )
        diagnostic=with_paired_log_loss(original['rows'],asof=_report_time(original['asof']),model_pairs=request['model_pairs'],minimum_samples=request['minimum_samples'])
    else:diagnostic=log_loss_diagnostics(original['rows'],minimum_samples=request['minimum_samples'])
    text=_key(diagnostic);html=render_log_loss(diagnostic)
    if paired:html=html.removesuffix('</html>')+render_paired_log_loss(diagnostic['paired_log_loss_diagnostics'])+'</html>'
    envelope={'schema':'AFI_LOG_LOSS_BROWSER_V2' if paired else 'AFI_LOG_LOSS_BROWSER_V1','source_report_json':raw.decode('utf-8'),'source_report_sha256':identity,
              'diagnostics_json':text,'diagnostics_sha256':hashlib.sha256(text.encode()).hexdigest()}
    if paired:envelope['model_pairs']=request['model_pairs']
    browser=_key(envelope)+'\n'
    if len(browser.encode())>1_000_000 or len(html.encode())>2_000_000:raise ForecastEvidenceRefused('Log-loss export output bound exceeded')
    planned=[(text+'\n','.json'),(html,'.html'),(browser,'.json')];paths=[];published=[]
    for content,extension in planned:
        path=publish_research_text(output_root,content,extension=extension)
        if path.read_bytes()!=content.encode():raise ForecastEvidenceRefused('Log-loss publication uncertain; preserve partial evidence')
        paths.append(path.name)
        published.append((path,content))
    for path,content in published:
        if path.read_bytes()!=content.encode():raise ForecastEvidenceRefused('Final log-loss readback failed; preserve outputs')
    return {'status':'OFFLINE_LOG_LOSS_EXPORTED','diagnostics':paths[0],'dashboard':paths[1],'browser_export':paths[2],
            'source_report_sha256':identity,'forecast_writes_performed':0,'outcome_appends_performed':0,
            'production_approved':False,'trading_authority':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description='Explicit offline probability log-loss companion; no forecast/outcome writes')
    parser.add_argument('--bundle-root',required=True);parser.add_argument('--request',required=True);parser.add_argument('--output-root',required=True)
    args=parser.parse_args(argv)
    try:result=export_log_loss(bundle_root=args.bundle_root,request_name=args.request,output_root=args.output_root)
    except (ValueError,OSError,TypeError,KeyError,OverflowError):parser.exit(2,'Log-loss evidence/publication refused; preserve partial outputs.\n')
    print(json.dumps(result,sort_keys=True));return 0


if __name__=='__main__':raise SystemExit(main())
