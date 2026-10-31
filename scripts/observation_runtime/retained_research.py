"""Retained synthetic bars to existing descriptive analysis, never execution."""
from __future__ import annotations

from datetime import date, datetime, time
from html import escape
from math import isfinite

from app.investment.market_hours import session_bounds
from app.investment.offline_research import (
    ET,
    ResearchInputRefused,
    aware,
    close_reference,
    equity_session,
    number,
    symbol_identity,
    validated_candles,
)

from scripts.observation_runtime.r7e47cp_market_signals import analyze_market
from scripts.observation_runtime.session_quality import session_quality


def unavailable_research(symbol, *, now, status):
    if status not in {'INSUFFICIENT_REFERENCE','INSUFFICIENT_HISTORY','REFUSED'}:
        raise ResearchInputRefused('Unknown research refusal state')
    return {'schema':'ATLAS_RETAINED_RESEARCH_V1','mode':'SYNTHETIC_REPLAY','symbol':symbol_identity(symbol),
            'asof':aware(now).isoformat(),'status':status,'analysis':None,'sessions':[],
            'source_authenticated':False,'corporate_actions_reconciled':False,'startup_authorized':False,
            'recovery_authorized':False,'network_authorized':False,'trading_authorized':False}


def validate_reference(previous_close, *, symbol, cutoff, asset_class=None):
    """Validate shape/publication timing without selecting a decision's close date."""
    current=aware(cutoff)
    expected={'symbol','previous_close','previous_session_date','source','available_at','currency','asset_class','data_mode'}
    if (not isinstance(previous_close,dict) or set(previous_close)!=expected
            or previous_close['symbol']!=symbol or previous_close['currency']!='USD'
            or previous_close['data_mode']!='SYNTHETIC_REPLAY'
            or previous_close['asset_class'] not in ('US_EQUITY','US_ETF')
            or (asset_class is not None and previous_close['asset_class']!=asset_class)
            or type(previous_close['previous_close']) not in (float,int)
            or not isinstance(previous_close['source'],str) or not 1<=len(previous_close['source'])<=128
            or not previous_close['source'].strip() or previous_close['source'].strip().upper()=='UNKNOWN'):
        raise ResearchInputRefused('Explicit dated reference identity required')
    number(previous_close['previous_close'],'previous close')
    available=aware(previous_close['available_at'])
    day=date.fromisoformat(previous_close['previous_session_date'])
    bounds=session_bounds(datetime.combine(day,time(12),ET))
    if bounds is None or not bounds[1]<=available<=current:
        raise ResearchInputRefused('Previous close unavailable at decision clock')
    return available


def retained_research(history, previous_close, *, now, minimum_baseline_sessions=5, max_history_rows=1000):
    current=aware(now)
    quality=session_quality(history,now=current,max_rows=max_history_rows)
    rows=history['rows'];symbol=history['symbol']
    available=validate_reference(previous_close,symbol=symbol,cutoff=current,
                                 asset_class=rows[0]['asset_class'] if rows else None)
    close_reference(previous_close,observation_time=current)
    if not rows:
        return unavailable_research(symbol,now=current,status='INSUFFICIENT_HISTORY')
    stamps=[aware(row['timestamp']) for row in rows]
    if len(set(stamps))!=len(stamps):
        raise ResearchInputRefused('Duplicate retained candles cannot become extra research samples')
    candles=[{'timestamp':aware(row['timestamp']),**{key.title():row[key] for key in ('open','high','low','close','volume')}} for row in rows]
    candles=validated_candles(symbol,candles,now=current)
    result=analyze_market(symbol,candles,previous_close,now=current,minimum_baseline_sessions=minimum_baseline_sessions)
    if any(value is not None and not isfinite(value) for value in
           (result['price'],result['previous_close'],result['change_from_previous_close_percent'],result['premarket_gap_percent'],
            result['session_momentum_percent'],result['relative_volume'])):
        raise ResearchInputRefused('Derived research metric is not finite')
    latest=aware(result['timestamp']);today=latest.astimezone(ET).date();sessions=[]
    for session in ('PRE_MARKET','REGULAR','AFTER_HOURS'):
        observed=[row for row in candles if row['timestamp'].astimezone(ET).date()==today and equity_session(row['timestamp'])==session]
        sessions.append({'session':session,'observed_bar_n':len(observed),
                         'observed_volume':sum(row['Volume'] for row in observed) if observed else None,
                         'coverage':'OBSERVED_BARS_ONLY' if observed else 'NO_OBSERVATIONS'})
    if any(row['observed_volume'] is not None and row['observed_volume']>2**53-1 for row in sessions):
        raise ResearchInputRefused('Observed volume exceeds portable integer limit')
    analysis={'bar_close':result['price'],'bar_timestamp':result['timestamp'],'session':result['session'],
              'price_kind':'COMPLETED_MINUTE_BAR_CLOSE_NOT_EXECUTABLE',
              'previous_close':result['previous_close'],'previous_session_date':result['previous_session_date'],
              'reference_source':previous_close['source'],'reference_available_at':available.isoformat(),
              'observed_change_percent':result['change_from_previous_close_percent'],
              'session_momentum_percent':result['session_momentum_percent'],
              'relative_volume':result['relative_volume'],'relative_volume_status':result['relative_volume_status'],
              'baseline_sessions':result['baseline_sessions'],'baseline_minimum_sessions':result['baseline_minimum_sessions'],
              'volume_window_completed_minutes':result['volume_window_completed_minutes'],
              'rvol_window_policy':'EXISTING_ANALYZER_EXCLUDES_LATEST_BAR',
              'freshness_policy':'EXISTING_ANALYZER_BAR_START_TTL_180_SECONDS',
              'history_window_truncated':quality['history_window_truncated']}
    if result['premarket_gap_percent'] is not None:
        analysis['premarket_gap_percent']=result['premarket_gap_percent']
    return {**unavailable_research(symbol,now=current,status='REFUSED'),'status':'DESCRIPTIVE_RESEARCH_ONLY',
            'analysis':analysis,'sessions':sessions}


def render_retained_research(report):
    body='<p>State: '+escape(report['status'])+'</p>'
    if report['analysis'] is not None:
        body+='<dl>'+''.join('<dt>'+escape(k.replace('_',' '))+'</dt><dd>'+escape('Unknown' if v is None else str(v))+'</dd>' for k,v in report['analysis'].items())+'</dl>'
        body+='<table><tr><th>Session</th><th>Observed bars</th><th>Observed volume</th><th>Coverage</th></tr>'
        for row in report['sessions']:
            body+='<tr>'+''.join('<td>'+escape('Unknown' if row[k] is None else str(row[k]))+'</td>' for k in ('session','observed_bar_n','observed_volume','coverage'))+'</tr>'
        body+='</table>'
    return ("<!doctype html><html lang='en'><meta charset='utf-8'><title>Atlas retained research</title>"
            '<h1>Retained research: '+escape(report['symbol'])+'</h1><p>Synthetic descriptive evidence only. '
            'Not a forecast, executable quote, trading permission or authenticated/corporate-action-adjusted result.</p>'
            '<p>Decision clock: '+escape(report['asof'])+'</p>'+body+'</html>')
