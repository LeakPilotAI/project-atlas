"""Read-only quality of explicitly retained replay windows, never feed authority."""
from __future__ import annotations

from datetime import timedelta
from html import escape
from math import isfinite

from app.investment.offline_research import (
    ET,
    ResearchInputRefused,
    aware,
    equity_session,
    symbol_identity,
    validated_candles,
)

from scripts.observation_runtime.contracts import canonical_uuid, digest, encoded
from scripts.observation_runtime.history import EVENTS, SessionHistory


def _lifecycle(rows, expected_head, now):
    if rows is None:
        if expected_head is not None:
            raise ResearchInputRefused("Lifecycle head without records")
        return {"status": "NOT_SUPPLIED", "authenticated": False}
    if type(rows) is not list or len(rows) > 2048:
        raise ResearchInputRefused("Bounded lifecycle evidence required")
    previous, prior_time, ids = '0' * 64, 0.0, set()
    active, uncertain = None, False
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'event_id','session_id','event','payload','observed_at','previous','digest'}:
            raise ResearchInputRefused("Malformed lifecycle record")
        canonical_uuid(row['event_id']);canonical_uuid(row['session_id'])
        stamp = row['observed_at']
        if (row['event'] not in EVENTS or type(stamp) not in (float, int) or not isfinite(stamp)
                or not prior_time <= stamp <= now.timestamp() or row['event_id'] in ids
                or row['previous'] != previous or row['digest'] != digest({k:v for k,v in row.items() if k!='digest'})):
            raise ResearchInputRefused("Contradictory lifecycle evidence")
        if not isinstance(row['payload'], dict):
            raise ResearchInputRefused("Malformed lifecycle payload")
        event, payload = row['event'], row['payload']
        keys = {'SESSION_START':{'release_id','profile','configuration_id'},'DATA_SOURCE':{'source_id'},
                'HEALTH':{'state'},'GRACEFUL_SHUTDOWN':{'outcome'},'INTERRUPTED':{'reason'},
                'RECOVERY_REQUIRED':{'reason'}}[event]
        if set(payload)!=keys or len(encoded(payload))>4096:
            raise ResearchInputRefused("Unsupported lifecycle payload")
        if event=='SESSION_START':
            if active is not None or uncertain or payload['profile']!='OBSERVATION_ONLY':
                raise ResearchInputRefused("Contradictory session start")
            active=row['session_id']
        elif active!=row['session_id'] or (uncertain and event not in {'INTERRUPTED','RECOVERY_REQUIRED'}):
            raise ResearchInputRefused("No corresponding unambiguous recorded session")
        if event=='GRACEFUL_SHUTDOWN':
            if payload['outcome']!='COMPLETE':
                raise ResearchInputRefused("Unconfirmed graceful shutdown")
            active=None
        if event in {'INTERRUPTED','RECOVERY_REQUIRED'}:
            if payload['reason'] not in {'PROCESS_INTERRUPTED','UNKNOWN_EXIT','PUBLICATION_FAILED','EVIDENCE_EXPIRED'}:
                raise ResearchInputRefused("Unknown non-clearing reason")
            uncertain=True
        if event=='HEALTH' and payload['state'] not in {'READY','DEGRADED','UNAVAILABLE'}:
            raise ResearchInputRefused("Unknown recorded health")
        previous, prior_time = row['digest'], stamp
        ids.add(row['event_id'])
    if expected_head != previous:
        raise ResearchInputRefused("Explicit lifecycle head mismatch")
    active, uncertain, seen = SessionHistory._state(rows)
    return {"status": "RECOVERY_REQUIRED" if uncertain else "OPEN_RECORDED_SESSION" if active else
                      "RECORDED_COMPLETE" if seen else "NO_SESSION_RECORDS",
            "record_n": len(rows), "expected_head": previous, "authenticated": False,
            "live_process_state_verified": False}


def validate_replay_observation(row, *, symbol, cutoff):
    """Shared validation only; does not select or merge correction vintages."""
    if not isinstance(row, dict):
        raise ResearchInputRefused("Malformed quality observation")
    if set(row)!={'symbol','asset_class','currency','source','data_mode','price_kind','interval_seconds',
                  'timestamp','bar_end','observed_at','session','open','high','low','close','volume'}:
        raise ResearchInputRefused("Unexpected observation fields")
    stamp, receipt, end = (aware(row.get(k)) for k in ('timestamp','observed_at','bar_end'))
    if (row.get('symbol') != symbol or row.get('data_mode') != 'SYNTHETIC_REPLAY'
            or row.get('source') != 'YAHOO_CHART_SHAPED_FIXTURE'
            or row.get('price_kind') != 'COMPLETED_MINUTE_BAR_CLOSE'
            or row.get('asset_class') not in {'US_EQUITY','US_ETF'} or row.get('currency') != 'USD'
            or type(row.get('interval_seconds')) is not int or row['interval_seconds'] != 60
            or end != stamp + timedelta(minutes=1) or not end <= receipt <= cutoff
            or row.get('session') != equity_session(stamp)):
        raise ResearchInputRefused("Observation time/provenance contradiction")
    validated_candles(symbol,[{'timestamp':stamp, **{k.title():row.get(k) for k in ('open','high','low','close','volume')}}],now=cutoff)
    return stamp, receipt


def session_quality(history, *, now, max_age_seconds=180, lifecycle=None, lifecycle_expected_head=None, max_rows=1000):
    """Measure only supplied completed bars and first receipt of repeated events.

    Local byte/chain consistency is not provider authenticity, monitored-window
    completeness, a missed market event or startup/recovery permission.
    """
    current = aware(now)
    if (type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 900
            or not isinstance(history, dict)
            or history.get('schema') != 'ATLAS_MARKET_REPLAY_HISTORY_V1'
            or history.get('mode') != 'SYNTHETIC_REPLAY'
            or history.get('network_authorized') is not False
            or history.get('trading_enabled') is not False
            or history.get('scope') != 'BOUNDED_RETAINED_BARS_NOT_FULL_SESSION'
            or type(history.get('more_retained_rows')) is not bool):
        raise ResearchInputRefused("Explicit denied-authority replay history required")
    if set(history)!={'schema','mode','symbol','asof','network_authorized','trading_enabled','rows','more_retained_rows','scope'}:
        raise ResearchInputRefused("Unexpected history fields")
    current_session=equity_session(current)
    symbol = symbol_identity(history.get('symbol'))
    cutoff = aware(history.get('asof'))
    if cutoff > current:
        raise ResearchInputRefused("Future history observation window")
    rows = history.get('rows')
    if type(max_rows) is not int or not 1<=max_rows<=10000 or type(rows) is not list or len(rows) > max_rows:
        raise ResearchInputRefused("Bounded historical bars required")
    retained, repeated = {}, 0
    for row in rows:
        stamp, receipt = validate_replay_observation(row,symbol=symbol,cutoff=cutoff)
        identity = {k:v for k,v in row.items() if k!='observed_at'}
        if stamp in retained:
            old, old_receipt = retained[stamp]
            if identity != old:
                raise ResearchInputRefused("Conflicting repeated observation")
            retained[stamp] = (old,min(receipt,old_receipt));repeated += 1
        else:
            retained[stamp] = (identity,receipt)
    groups = {}
    if len({row['asset_class'] for row,_ in retained.values()})>1:
        raise ResearchInputRefused("Conflicting asset class history")
    for stamp,(row,receipt) in sorted(retained.items()):
        key = (stamp.astimezone(ET).date().isoformat(),row['session'])
        groups.setdefault(key,[]).append((stamp,row,receipt))
    windows = []
    for (day,session), items in sorted(groups.items(),key=lambda item:item[1][0][0]):
        first, latest = items[0][0], items[-1][0]
        expected = int((latest-first).total_seconds()/60)+1
        age = (current-aware(items[-1][1]['bar_end'])).total_seconds()
        in_current = current_session==session and current.astimezone(ET).date().isoformat()==day
        delays = [(receipt-aware(row['bar_end'])).total_seconds() for _,row,receipt in items]
        windows.append({'exchange_date':day,'session':session,'first_bar':first.isoformat(),'last_bar':latest.isoformat(),
                        'observed_bar_n':len(items),'missing_minutes_between_observed_bars':expected-len(items),
                        'receipt_delay_min_seconds':min(delays),'receipt_delay_max_seconds':max(delays),
                        'latest_completed_bar_age_seconds':age,
                        'status':'FRESH_AT_REPORT_CLOCK' if in_current and 0<=age<=max_age_seconds else
                                 'STALE_AT_REPORT_CLOCK' if in_current else 'PAST_SESSION',
                        'scope':'FIRST_TO_LAST_OBSERVED_BAR_NOT_FULL_SESSION'})
    lifecycle_state = _lifecycle(lifecycle,lifecycle_expected_head,current)
    return {'schema':'ATLAS_SESSION_QUALITY_V1','mode':'SYNTHETIC_REPLAY','symbol':symbol,
            'asof':current.isoformat(),'source_asof':cutoff.isoformat(),
            'current_market_session':current_session,'freshness_threshold_seconds':max_age_seconds,
            'status':'OBSERVED_WINDOWS_ONLY' if windows else 'NO_OBSERVATIONS',
            'observed_bar_n':len(retained),'repeated_receipt_n':repeated,'windows':windows,
            'history_window_truncated':history['more_retained_rows'],'lifecycle':lifecycle_state,
            'provider_freshness_verified':False,'session_completeness_verified':False,
            'missed_market_events_established':False,'network_authorized':False,
            'startup_authorized':False,'recovery_authorized':False,'trading_authorized':False}


def render_session_quality(report):
    """Read-only HTML for already validated report output, no scripts or actions."""
    fields=('exchange_date','session','first_bar','last_bar','observed_bar_n',
            'missing_minutes_between_observed_bars','receipt_delay_max_seconds',
            'latest_completed_bar_age_seconds','status')
    rows=''.join('<tr>'+''.join('<td>'+escape(str(row[key]))+'</td>' for key in fields)+'</tr>'
                 for row in report['windows'])
    return ("<!doctype html><html lang='en'><meta charset='utf-8'><title>Atlas session quality</title>"
            '<h1>Replay session quality: '+escape(report['symbol'])+'</h1>'
            '<p>Synthetic replay only. No live-feed, startup, recovery or trading permission.</p>'
            '<p>Report clock: '+escape(report['asof'])+'; source clock: '+escape(report['source_asof'])+'</p>'
            '<p>Evidence: '+escape(report['status'])+'; recorded lifecycle: '+escape(report['lifecycle']['status'])+'</p>'
            '<table><caption>Gaps only between observed bars, not missed market events or full-session coverage.</caption>'
            '<tr>'+''.join('<th>'+escape(key.replace('_',' '))+'</th>' for key in fields)+'</tr>'+rows+'</table>'
            '<p>Repeated receipts: '+str(report['repeated_receipt_n'])+'; history truncated: '
            +str(report['history_window_truncated'])+'</p></html>')
