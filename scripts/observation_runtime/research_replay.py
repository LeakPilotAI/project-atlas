"""Bounded point-in-time descriptive replay; no forecasts, orders or provider I/O."""
from __future__ import annotations

import hashlib
import json
from html import escape
from itertools import pairwise

from app.investment.offline_research import (
    ET,
    ResearchInputRefused,
    aware,
    equity_session,
    previous_session,
)

from scripts.observation_runtime.retained_research import (
    retained_research,
    unavailable_research,
    validate_reference,
)
from scripts.observation_runtime.session_quality import session_quality

STATES=('DESCRIPTIVE_RESEARCH_ONLY','INSUFFICIENT_REFERENCE','INSUFFICIENT_HISTORY','REFUSED')
MAX_ROW_DECISIONS=200000


def encoded(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def fingerprint(value):return hashlib.sha256(encoded(value)).hexdigest()


def replay_research(archive, references, decisions):
    """Replay all declared clocks. A refusal remains in the planned denominator.

    Complete *supplied retained* input is required; monitoring completeness and
    provider authenticity are never inferred. Bar revisions are not supported.
    """
    if (not isinstance(archive,dict) or type(archive.get('rows')) is not list or len(archive['rows'])>10000
            or type(references) is not list or len(references)>512
            or type(decisions) is not list or not 1<=len(decisions)<=128):
        raise ResearchInputRefused('Bounded explicit replay archive, references and clocks required')
    archive=json.loads(encoded(archive));references=json.loads(encoded(references))
    cutoff=aware(archive.get('asof'))
    session_quality(archive,now=cutoff,max_rows=10000)
    if archive['more_retained_rows']:
        raise ResearchInputRefused('Truncated retained archive cannot establish earlier visibility')
    symbol=archive['symbol'];rows=archive['rows'];prepared=[];seen=set()
    for row in rows:
        stamp=aware(row['timestamp'])
        if stamp in seen:raise ResearchInputRefused('Repeated/revised bars require a separate vintage contract')
        seen.add(stamp);prepared.append((stamp,aware(row['observed_at']),row))
    prepared.sort(key=lambda item:item[0])
    clocks=[aware(clock) for clock in decisions]
    if any(clock>cutoff for clock in clocks) or any(a>=b for a,b in pairwise(clocks)):
        raise ResearchInputRefused('Unique increasing decision clocks must not exceed archive cutoff')
    for clock in clocks:equity_session(clock)
    vintages={};ref_ids=set()
    for reference in references:
        available=validate_reference(reference,symbol=symbol,cutoff=cutoff,
                                     asset_class=rows[0]['asset_class'] if rows else None)
        key=(reference['previous_session_date'],available)
        identity=fingerprint(reference)
        if key in vintages or identity in ref_ids:
            raise ResearchInputRefused('Duplicate or tied reference vintages cannot be selected safely')
        vintages[key]=reference;ref_ids.add(identity)
    work=sum(sum(receipt<=clock for _,receipt,_ in prepared) for clock in clocks)
    if work>MAX_ROW_DECISIONS:raise ResearchInputRefused('Replay row-decision budget exceeded')
    cases=[];counts={state:0 for state in STATES}
    for index,clock in enumerate(clocks):
        visible=[row for _,receipt,row in prepared if receipt<=clock]
        history={**archive,'asof':clock.isoformat(),'rows':visible,'more_retained_rows':False}
        reference=None
        reason=None;stage='REFERENCE_SELECTION'
        try:
            expected_date=previous_session(clock.astimezone(ET).date()).isoformat()
            eligible=[(available,row) for (day,available),row in vintages.items() if day==expected_date and available<=clock]
            if eligible:reference=max(eligible,key=lambda item:item[0])[1]
            stage='DESCRIPTIVE_ANALYSIS'
            report=(retained_research(history,reference,now=clock,max_history_rows=10000) if reference is not None else
                    unavailable_research(symbol,now=clock,status='INSUFFICIENT_REFERENCE'))
        except (ValueError,TypeError,KeyError,OverflowError):
            report=unavailable_research(symbol,now=clock,status='REFUSED')
            reason=stage+'_REFUSED'
        state=report['status'];counts[state]+=1
        identity={'symbol':symbol,'decision_at':clock.isoformat(),'visible_history_sha256':fingerprint(history),
                  'reference_sha256':fingerprint(reference) if reference is not None else None,'report_sha256':fingerprint(report)}
        cases.append({'index':index,**identity,'decision_sha256':fingerprint(identity),'visible_bar_n':len(visible),
                      'status':state,'refusal_reason':reason,'report':report})
    return {'schema':'ATLAS_DESCRIPTIVE_REPLAY_V1','mode':'SYNTHETIC_REPLAY','symbol':symbol,
            'archive_asof':cutoff.isoformat(),'archive_sha256':fingerprint(archive),'references_sha256':fingerprint(references),
            'reference_vintage_n':len(references),'planned_decision_n':len(clocks),'status_counts':counts,'cases':cases,
            'row_decision_work':work,'reference_policy':'LATEST_AVAILABLE_EXPECTED_PREVIOUS_SESSION_NO_TIE',
            'bar_revisions_supported':False,'source_authenticated':False,'monitoring_completeness_verified':False,
            'predictive_skill_established':False,'network_authorized':False,'startup_authorized':False,
            'recovery_authorized':False,'trading_authorized':False}


def render_replay(report):
    rows=[]
    for case in report['cases']:
        analysis=case['report']['analysis']
        values=(case['decision_at'],case['status'],case['visible_bar_n'],case['reference_sha256'],
                analysis['observed_change_percent'] if analysis else None,
                analysis['relative_volume'] if analysis else None)
        rows.append('<tr>'+''.join('<td>'+escape('Unknown' if value is None else str(value))+'</td>' for value in values)+'</tr>')
    return ("<!doctype html><html lang='en'><meta charset='utf-8'><title>Atlas descriptive replay</title>"
            '<h1>Point-in-time descriptive replay</h1><p>Synthetic research only, not forecasting skill, '
            'monitoring completeness, labels, trades or P&amp;L. Refusals remain in the planned denominator.</p>'
            '<p>Planned decisions: '+str(report['planned_decision_n'])+'</p><table><tr>'
            '<th>Decision clock</th><th>State</th><th>Visible bars</th><th>Reference hash</th>'
            '<th>Observed change</th><th>Relative volume</th></tr>'+''.join(rows)+'</table></html>')


def browser_replay(report):
    """Exact UTF-8 payload verification avoids cross-language float re-encoding."""
    text=encoded(report).decode()
    envelope={'schema':'ATLAS_DESCRIPTIVE_REPLAY_BROWSER_V1','report_json':text,
              'payload_sha256':hashlib.sha256(text.encode()).hexdigest()}
    result=encoded(envelope).decode()
    if len(result.encode())>1000000:raise ResearchInputRefused('Bounded browser replay export required')
    return result
