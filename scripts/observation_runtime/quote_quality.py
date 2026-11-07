"""Quality of supplied synthetic quote references; no transport or price authority."""
from __future__ import annotations

from html import escape
from math import isfinite

from app.investment.offline_research import (
    ET,
    ResearchInputRefused,
    aware,
    equity_session,
    symbol_identity,
)

STATES=('FRESH','STALE','DELAYED','UNAVAILABLE','NOT_YET_OBSERVED')
FIELDS={'symbol','asset_class','currency','timestamp','observed_at','price','session','provider_reported_delay',
        'provider_delay_unit','source','data_mode','price_kind','status','age_seconds','reference_price'}


def quote_quality(rows, *, now, max_age_seconds=30):
    """Keep event staleness separate from nonzero, unit-unverified vendor delay."""
    current=aware(now);session=equity_session(current)
    if (type(rows) is not list or not 1<=len(rows)<=100 or type(max_age_seconds) is not int
            or not 1<=max_age_seconds<=120):
        raise ResearchInputRefused('Bounded explicit quote-quality input required')
    output=[];seen=set();counts={state:0 for state in STATES}
    for row in rows:
        if not isinstance(row,dict):raise ResearchInputRefused('Malformed quote reference')
        symbol=symbol_identity(row.get('symbol'));state=row.get('status')
        if symbol!=row.get('symbol') or symbol in seen or state not in STATES:
            raise ResearchInputRefused('Unique canonical quote states required')
        seen.add(symbol)
        item={'symbol':symbol,'status':state,'event_time':None,'receipt_time':None,'event_age_seconds':None,
              'receipt_delay_seconds':None,'reported_delay_value':None,'reported_delay_unit':None,
              'event_stale_at_report_clock':None,'scope':'LATEST_SUPPLIED_REFERENCE_ONLY'}
        if state in {'UNAVAILABLE','NOT_YET_OBSERVED'}:
            if set(row)!={'symbol','status','price'} or row['price'] is not None:
                raise ResearchInputRefused('Unavailable quote exposed data')
        else:
            if (set(row)!=FIELDS or row['data_mode']!='SYNTHETIC_REPLAY' or row['currency']!='USD'
                    or row['asset_class'] not in {'US_EQUITY','US_ETF'}
                    or row['source']!='YAHOO_QUOTE_RESPONSE_SHAPED_FIXTURE'
                    or row['price_kind']!='REFERENCE_QUOTE_NOT_EXECUTABLE'
                    or row['provider_delay_unit']!='UNVERIFIED_FIXTURE_METADATA'):
                raise ResearchInputRefused('Quote identity/provenance mismatch')
            event,receipt=aware(row['timestamp']),aware(row['observed_at'])
            if not event<=receipt<=current or row['session']!=equity_session(event) or row['session']=='CLOSED':
                raise ResearchInputRefused('Quote event/receipt contradiction')
            age=(current-event).total_seconds();delay=row['provider_reported_delay']
            stale=(age>max_age_seconds or session!=row['session']
                   or current.astimezone(ET).date()!=event.astimezone(ET).date())
            if (type(delay) is not int or not 0<=delay<=86400
                    or type(row['age_seconds']) not in (float,int) or not isfinite(row['age_seconds'])
                    or abs(row['age_seconds']-age)>0.000001
                    or type(row['reference_price']) not in (float,int) or not isfinite(row['reference_price'])
                    or row['reference_price']<=0):
                raise ResearchInputRefused('Quote age/delay/reference contradiction')
            expected='DELAYED' if delay else 'STALE' if stale else 'FRESH'
            price_valid=(type(row['price']) in (float,int) and row['price']==row['reference_price']) if state=='FRESH' else row['price'] is None
            if state!=expected or not price_valid:
                raise ResearchInputRefused('Quote current-price/status contradiction')
            item.update(event_time=event.isoformat(),receipt_time=receipt.isoformat(),event_age_seconds=age,
                        receipt_delay_seconds=(receipt-event).total_seconds(),reported_delay_value=delay,
                        reported_delay_unit='UNVERIFIED_FIXTURE_METADATA',event_stale_at_report_clock=stale)
        counts[state]+=1;output.append(item)
    return {'schema':'ATLAS_QUOTE_QUALITY_V1','mode':'SYNTHETIC_REPLAY','asof':current.isoformat(),
            'current_market_session':session,'freshness_threshold_seconds':max_age_seconds,
            'rows':sorted(output,key=lambda item:item['symbol']),'status_counts':counts,
            'provider_service_health':'NOT_OBSERVED','provider_freshness_verified':False,
            'monitoring_completeness_verified':False,'network_authorized':False,'startup_authorized':False,
            'recovery_authorized':False,'trading_authorized':False}


def render_quote_quality(report):
    fields=('symbol','status','event_time','receipt_time','event_age_seconds','receipt_delay_seconds',
            'reported_delay_value','reported_delay_unit','event_stale_at_report_clock')
    rows=''.join('<tr>'+''.join('<td>'+escape('Unknown' if row[k] is None else str(row[k]))+'</td>' for k in fields)+'</tr>' for row in report['rows'])
    headings=('Symbol','State at replay clock','Event time','Receipt time','Event age (seconds)',
              'Recorded receipt delay (seconds)','Vendor delay value','Vendor delay unit (unverified)',
              'Event stale at report clock')
    return ("<!doctype html><html lang='en'><meta charset='utf-8'><title>Atlas quote quality</title>"
            '<h1>Offline quote-reference quality</h1><p>Synthetic replay only; no executable prices, '
            'live-feed entitlement or provider-service health proof.</p><p>Report clock: '+escape(report['asof'])+'</p>'
            '<table><caption>Vendor delay values have unverified units. Receipt delay is recorded receipt minus event time.</caption>'
            '<tr>'+''.join('<th>'+escape(k)+'</th>' for k in headings)+'</tr>'+rows+'</table></html>')
