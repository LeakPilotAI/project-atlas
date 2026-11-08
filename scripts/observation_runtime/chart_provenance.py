"""Source-bound chart semantics diagnostic; explicit synthetic bytes only, no transport."""
from __future__ import annotations

import hashlib
import html
import json
from datetime import UTC, datetime

from app.backtest.forecast_dataset import _json
from app.investment.offline_research import ResearchInputRefused, aware, number

from scripts.observation_runtime.market_replay import normalize_chart
from scripts.observation_runtime.quality_report import _publish_outputs


def chart_provenance(raw, *, observed_at, asset_class, expected_sha256):
    if type(raw) is not bytes or not 1<=len(raw)<=1_000_000:
        raise ResearchInputRefused('Bounded explicit chart fixture bytes required')
    identity=hashlib.sha256(raw).hexdigest()
    if type(expected_sha256) is not str or identity!=expected_sha256:
        raise ResearchInputRefused('Exact source commitment required')
    payload=_json(raw)
    rows=normalize_chart(payload,observed_at=observed_at,asset_class=asset_class,diagnostic_only=True)
    result=payload['chart']['result'][0];meta=result['meta'];indicators=result['indicators']
    delay=None
    if 'exchangeDataDelayedBy' in meta:
        delay=meta['exchangeDataDelayedBy']
        if type(delay) is not int or not 0<=delay<=86400:
            raise ResearchInputRefused('Malformed optional chart delay metadata')
    adjusted=None
    if 'adjclose' in indicators:
        series=indicators['adjclose']
        if type(series) is not list or len(series)!=1 or type(series[0]) is not dict or set(series[0])!={'adjclose'}:
            raise ResearchInputRefused('Explicit aligned adjusted-close series required')
        adjusted=series[0]['adjclose']
        if type(adjusted) is not list or len(adjusted)!=len(rows):
            raise ResearchInputRefused('Adjusted-close alignment required')
        adjusted={datetime.fromtimestamp(ts,UTC).isoformat():number(value,'adjusted close')
                  for ts,value in zip(result['timestamp'],adjusted,strict=True)}
    observations=[{'timestamp':r['timestamp'],'session':r['session'],'bar_close':r['close'],
                  'reported_adjusted_close':None if adjusted is None else adjusted[r['timestamp']]}
                  for r in rows]
    report={'schema':'ATLAS_CHART_PROVENANCE_V1','mode':'SYNTHETIC_REPLAY',
            'source_sha256':identity,'observed_at':aware(observed_at).isoformat(),
            'symbol':rows[0]['symbol'],'asset_class':asset_class,'bar_n':len(rows),
            'price_basis':'CHART_QUOTE_CLOSE_NOT_VERIFIED_UNADJUSTED',
            'adjustment_basis':'UNVERIFIED','adjusted_series':'ABSENT' if adjusted is None else 'PRESENT_NOT_AUTHENTICATED',
            'provider_reported_delay':delay,'provider_delay_unit':'UNVERIFIED',
            'live_status':'NOT_ESTABLISHED','source_authenticated':False,'network_authorized':False,
            'startup_authorized':False,'recovery_authorized':False,'trading_authorized':False,
            'rows':observations}
    if len(json.dumps(report,allow_nan=False).encode())>1_000_000:
        raise ResearchInputRefused('Diagnostic output bound exceeded')
    return report


def render_chart_provenance(report):
    """Only a computed diagnostic is renderable; never accepts arbitrary raw HTML."""
    escape=lambda value:html.escape(str(value),quote=True)
    body=''.join('<tr>'+''.join('<td>'+escape(row[key])+'</td>' for key in
            ('timestamp','session','bar_close','reported_adjusted_close'))+'</tr>' for row in report['rows'])
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Chart source diagnostic</title>'
            '<h1>Synthetic chart source diagnostic</h1><p>No live status, adjustment basis or provider rights established.</p>'
            '<p>Source SHA-256: '+escape(report['source_sha256'])+'</p><p>Reported delay (unit unverified): '
            +escape(report['provider_reported_delay'])+'</p><table><tr><th>Event UTC</th><th>Session</th>'
            '<th>Chart close</th><th>Reported adjusted close (unverified)</th></tr>'+body+'</table></html>')


def export_chart_provenance(raw, *, observed_at,asset_class,expected_sha256,output_root):
    report=chart_provenance(raw,observed_at=observed_at,asset_class=asset_class,expected_sha256=expected_sha256)
    return _publish_outputs(report,{'schema':'ATLAS_CHART_PROVENANCE_EXPORT_V1',
        'source_sha256':report['source_sha256'],'source_authenticated':False,
        'network_authorized':False,'startup_authorized':False,'recovery_authorized':False,
        'trading_authorized':False},output_root,render_chart_provenance)
