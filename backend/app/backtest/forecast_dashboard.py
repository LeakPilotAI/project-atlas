"""Standalone scriptless fixture dashboard; no production API/UI integration."""
from __future__ import annotations

from html import escape

from app.backtest.forecast_comparison import compare_forecasts, scenario_research
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_replay import evaluate_probability_holdout, replay_baselines


def render_dashboard(entries, *, evidence_asof, title="Atlas Forecast Intelligence", source_review=None,
                     legacy_error_layout=False):
    report = compare_forecasts(entries,evidence_asof=evidence_asof,source_review=source_review)
    def cell(value):return escape(str(value),quote=True) if value is not None else "Unavailable"
    rows=[]
    for row in report["rows"]:
        interval=(f"{row['lower']} - {row['upper']} / nominal level {row['interval_level']} (unverified coverage)"
                  if row["interval_level"] is not None else "Not fitted")
        if legacy_error_layout and row['interval_level'] is not None:
            interval=(f"{row['lower']:.2f} - {row['upper']:.2f} / nominal level "
                      f"{row['interval_level']} (unverified coverage)")
        reference=f"{row['reference']:.2f}" if legacy_error_layout else row['reference']
        point=f"{row['point']:.2f}" if legacy_error_layout else row['point']
        change=(f"{row['implied_change_percent']:+.2f}%" if legacy_error_layout
                else f"{row['implied_change_percent']:+}%")
        values=[row["asset_id"],row["method"],row["horizon"],
                    row["issued_at"],row["target_at"],row["currency"],reference,point,
                    change,interval,row['probability_up'],row['probability_method'],row["actual"],row["status"]]
        if not legacy_error_layout:values.extend((row['absolute_error'],row['relative_error_percent']))
        values.extend((row["training_n"],row["dataset_version"],row["accuracy_status"]))
        rows.append('<tr>'+''.join(f'<td>{cell(v)}</td>' for v in values)+'</tr>')
    headings=["Asset","Model","Horizon","Issued (UTC)","Target (UTC)","Currency","Reference","Forecast point",
              "Implied change","Interval","P(UP) baseline","Probability method","Observed outcome","Outcome state"]
    if not legacy_error_layout:headings.extend(("Absolute error (price units)","Absolute percentage error (%)"))
    headings.extend(("Training n","Dataset version","Accuracy evidence"))
    provenance=''.join('<li>'+cell(r['asset_id'])+' / manifest '+cell(r['manifest_sha256'])+' / forecast '+cell(r['forecast_sha256'])+' / source '+cell(r['source_binding'])+' '+cell(r['release_source_sha256'])+'</li>' for r in report['rows'])
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>'''+cell(title)+'''</title><style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#080e17;color:#e7eef7;font:16px/1.55 system-ui,sans-serif}
main{max-width:1600px;margin:auto;padding:clamp(20px,4vw,60px)}h1{font-size:clamp(28px,4vw,46px);line-height:1.1;margin-bottom:12px}
.eyebrow{color:#57ded1;letter-spacing:.12em;font-size:13px}.notice{padding:20px;border:1px solid #e37786;background:#29151e;border-radius:12px}
.panel{margin-top:28px;padding:22px;background:#101b2b;border:1px solid #314258;border-radius:14px}.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px}caption{text-align:left;color:#bcccdc;padding-bottom:18px}th,td{text-align:left;padding:12px;border-bottom:1px solid #34435a;white-space:nowrap}
th{color:#8ce8df}td{font-variant-numeric:tabular-nums}ul{overflow-wrap:anywhere}footer{color:#b0bfd0;margin-top:24px}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style></head><body><main><div class="eyebrow">PROJECT ATLAS / OFFLINE RESEARCH</div><h1>'''+cell(title)+'''</h1>
<p>Explicit evidence. Honest uncertainty. No execution authority.</p><section class="notice" aria-label="Safety and evidence status">
<strong>Production NO-GO - synthetic fixtures only</strong><p>No demonstrated forecasting skill or calibrated coverage. Empirical P(UP), if requested, is a smoothed historical next-close frequency, not a calibrated probability; flat is not UP. PAPER, live orders, Discord and recovery actions are unavailable.</p></section>
<section class="panel" aria-label="Forecast comparison"><div class="scroll" tabindex="0" aria-label="Scrollable forecast table">
<table><caption>'''+cell(report['asof'])+''' - percentage changes are predictions, not realized returns or confidence. '''+('' if legacy_error_layout else "Absolute errors use each asset's price units; percentage error uses its observed outcome as denominator. Pending errors are unavailable, not zero. Neither metric is PAPER profit. ")+'''Assets and currencies are not pooled or ranked.</caption><thead><tr>'''+''.join('<th scope="col">'+cell(h)+'</th>' for h in headings)+'''</tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></div></section>
<section class="panel"><h2>Provenance</h2><ul>'''+provenance+'''</ul><p>Manifest hashes establish supplied-byte consistency, not provider rights or archive authenticity. Dataset availability and missing-history refusals remain explicit.</p></section>
<footer>This scriptless report has no network calls, order controls, forms or live connection. Reproduce from the pinned dataset and model artifacts. Official AFI milestones remain PENDING.</footer>
</main></body></html>'''


def render_probability_replay(review, *, asset_id, issued_times, evidence_asof, probability_method,
                              method='NO_CHANGE', lookback=20, horizon='1D', outcome_asof=None, source_review=None):
    """Recompute explicit replay before rendering; never trust imported metrics."""
    if probability_method is None:raise ForecastEvidenceRefused('Explicit probability replay required')
    report=replay_baselines(review,asset_id=asset_id,issued_times=issued_times,evidence_asof=evidence_asof,
                            probability_method=probability_method,method=method,lookback=lookback,horizon=horizon,
                            outcome_asof=outcome_asof,source_review=source_review)
    def cell(value):return escape(str(value),quote=True) if value is not None else 'Unavailable'
    rows=[]
    for case in report['cases']:
        values=[case['issued_at'],case.get('target_at'),case['status'],case.get('probability_up'),case.get('actual_up'),
                case.get('brier'),case.get('source_revision'),case.get('source_available_at'),
                case.get('training_available_through'),case.get('training_sha256'),case.get('reason')]
        rows.append('<tr>'+''.join('<td>'+cell(v)+'</td>' for v in values)+'</tr>')
    metrics=report['probability_diagnostics']
    reliability_rows=[];outcomes={o.forecast_id:o for o in report['outcomes']}
    for cohort in report['score']['cohorts']:
        identity=cohort['cohort'];populated={b['bin']:b for b in cohort['calibration_bins']}
        sample=[f for f in report['forecasts'] if f.forecast_id in outcomes and f.probability_up is not None
                and all(getattr(f,k,None)==v for k,v in identity.items())]
        distinct=len({f.target_at for f in sample})
        for index in range(10):
            points=[f for f in sample if min(int(f.probability_up*10),9)==index];n=len(points);targets=len({f.target_at for f in points});b=populated.get(index)
            state='EMPTY' if not n else 'INSUFFICIENT_EVIDENCE' if n<20 else 'OVERLAPPING_TARGET_EVIDENCE' if targets<20 else 'DIAGNOSTIC_ONLY'
            values=[identity['asset_id'],identity['model_id'],cohort['probability_n'],distinct,index/10,(index+1)/10,index==9,n,targets,
                    b['mean_probability'] if b else None,b['observed_up_fraction'] if b else None,cohort['expected_calibration_error'],state]
            reliability_rows.append('<tr>'+''.join('<td>'+cell(v)+'</td>' for v in values)+'</tr>')
    reliability_html='<section><h2>Probability reliability evidence</h2><p>Ten fixed bins: lower inclusive, upper exclusive except probability1. Empty bins are unavailable, not zero error. The weighted bin gap uses recorded resolved probabilities only. Sparse bins and repeated targets do not establish calibration, independence or market skill.</p>'
    if not reliability_rows:reliability_html+='<p>No resolved recorded probability cohort is available. No bin error is inferred.</p>'
    reliability_html+='<div class="scroll" tabindex="0"><table><caption>Contexts remain separate; no pooling across models or assets.</caption><thead><tr>'+''.join('<th scope="col">'+cell(v)+'</th>' for v in ['Asset','Model','Probability denominator','Distinct targets','Bin lower','Bin upper','Upper inclusive','Bin count','Bin distinct targets','Mean probability','Observed UP fraction','Weighted bin gap','Bin evidence'])+'</tr></thead><tbody>'+''.join(reliability_rows)+'</tbody></table></div></section>'
    counts=' / '.join(cell(k)+': '+cell(report[k]) for k in ('requested_n','issued_n','refused_n','resolved_n','pending_target_n','pending_publication_n','missing_outcome_n'))
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Atlas offline probability replay</title><style>body{margin:0;background:#09111c;color:#e8f1fc;font:16px/1.5 system-ui,sans-serif}main{max-width:1500px;margin:auto;padding:24px}.notice{border:1px solid #e38891;padding:18px}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%}td,th{padding:12px;border-bottom:1px solid #405168;text-align:left;white-space:nowrap}p{overflow-wrap:anywhere}</style></head><body><main><h1>Offline probability walk-forward replay</h1>
<section class="notice"><strong>Production NO-GO — synthetic evidence only</strong><p>Each requested case refits only issue-time-known closes. Fixed smoothing is not calibrated probability. No retuning, independent samples, market skill, profitability or trading authority is established.</p></section>
<p>'''+counts+'''</p><p>Asset: '''+cell(asset_id)+''' / method: '''+cell(report['probability_method'])+''' / point model: '''+cell(method)+''' / lookback: '''+cell(lookback)+'''</p>
<p>Evidence cutoff: '''+cell(report['asof'])+''' / outcome vintage: '''+cell(report['outcome_asof'])+'''</p>
<p>Resolved probability cases: '''+cell(metrics['probability_n'])+''' / distinct targets: '''+cell(metrics['distinct_target_n'])+''' / Brier: '''+cell(metrics['brier'])+''' / paired uninformative baseline: '''+cell(metrics['uninformative_baseline_brier'])+''' / error ratio: '''+cell(metrics['ratio_to_baseline'])+''' / '''+cell(metrics['status'])+'''</p>
<div class="scroll" tabindex="0"><table><caption>Pending and missing labels are not zero-error outcomes. Refused requests remain in the requested denominator. Flat is not UP. Corrections are evaluated at the explicit outcome vintage, never additional samples.</caption><thead><tr>'''+''.join('<th scope="col">'+cell(v)+'</th>' for v in ['Issued','Target','State','P(UP)','Actual UP','Brier','Revision','Label available','Training available through','Training commitment','Refusal reason'])+'''</tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></div>
'''+reliability_html+'''<p>Dataset commitment: '''+cell(report['dataset_sha256'])+''' / manifest: '''+cell(report['manifest_sha256'])+''' / source archive: '''+cell(report['release_source_sha256'])+'''</p><p>Supplied-byte consistency is not independent provenance or provider authorization. This scriptless file makes no network requests or orders.</p></main></body></html>'''


def render_probability_holdout(review, protocol, *, expected_protocol_sha256, evidence_asof,
                                outcome_asof=None, source_review=None):
    """Reconstruct protocol and replay; format no imported success assertions."""
    from datetime import datetime

    from app.backtest.forecast_baselines import PROBABILITY_METHOD
    evaluated=evaluate_probability_holdout(review,protocol,expected_protocol_sha256=expected_protocol_sha256,
                    evidence_asof=evidence_asof,outcome_asof=outcome_asof,source_review=source_review)
    selected=evaluated['protocol']['selection']
    html=render_probability_replay(review,asset_id=selected['asset_id'],
                    issued_times=[datetime.fromisoformat(t) for t in evaluated['protocol']['holdout_issues']],
                    evidence_asof=evidence_asof,probability_method=PROBABILITY_METHOD,method=selected['selected_method'],
                    lookback=selected['lookback'],outcome_asof=outcome_asof,source_review=source_review)
    title='<h1>Frozen-protocol probability holdout</h1><p>Protocol: '+escape(expected_protocol_sha256,quote=True)+'</p><p>Fixed pre-freeze point selection; no holdout probability tuning. Local algorithmic partition checks do not establish independently unseen data or external custody.</p>'
    return html.replace('<h1>Offline probability walk-forward replay</h1>',title)


def render_scenarios(*, base_year, milestones, annual_assumptions):
    """Scriptless conditional paths; no statistical forecast or market-price claim."""
    report = scenario_research(base_year=base_year, milestones=milestones, annual_assumptions=annual_assumptions)
    def cell(value):
        return escape(str(value), quote=True)
    rows = ''.join('<tr>'+''.join('<td>'+cell(value)+'</td>' for value in
                   [row['year'], row['years'], *[row['conditional_index'][key] for key in ('bear','base','bull')]])+'</tr>'
                   for row in report['milestones'])
    assumptions = ''.join('<li>'+cell(key)+': '+cell(report['annual_assumptions'][key])+'</li>' for key in ('bear','base','bull'))
    limitations = ''.join('<li>'+cell(value)+'</li>' for value in report['limitations'])
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; base-uri \'none\'; form-action \'none\'">'
            '<title>Atlas conditional scenario research</title></head><body><main>'
            '<h1>Conditional scenarios, not forecasts</h1><p>Production NO-GO. No trading authority.</p>'
            '<p>Illustrative index, not an asset price. No probabilities or coverage guarantee. '
            'Long-term uncertainty is unquantified.</p><h2>Explicit annual assumptions</h2><ul>'+assumptions+'</ul>'
            '<p>Base year: '+cell(base_year)+'. Base index: 100.</p><table><caption>Assumption-driven compound paths</caption>'
            '<thead><tr>'+''.join('<th scope="col">'+cell(v)+'</th>' for v in ('Year','Years','Bear index','Base index','Bull index'))+
            '</tr></thead><tbody>'+rows+'</tbody></table><h2>Limitations</h2><ul>'+limitations+'</ul>'
            '<p>Scenario commitment: '+cell(report['scenario_sha256'])+'</p></main></body></html>')
