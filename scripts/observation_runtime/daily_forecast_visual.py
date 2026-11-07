"""Scriptless daily price/forecast companion, never a live feed or action UI."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math

from app.backtest.forecast_artifacts import publish_research_text
from app.backtest.forecast_dataset import _json
from app.backtest.forecast_report import BundleReader, _prepare_forecast_batch
from app.investment.offline_research import ResearchInputRefused, aware

from scripts.observation_runtime.chart_archive import FLAGS, _read
from scripts.observation_runtime.daily_availability import daily_availability
from scripts.observation_runtime.daily_forecast_batch import (
    verify_daily_forecast_receipt,
)


def _cell(value):
    return html.escape(str(value), quote=True)


def _known_history(review, model):
    latest = {}
    for row in review.observations:
        if row.asset_id != model.asset_id or row.observed_at > model.issued_at or row.available_at > model.issued_at:
            continue
        prior = latest.get(row.observed_at)
        if prior is None or row.available_at > prior.available_at:
            latest[row.observed_at] = row
    rows = [latest[key] for key in sorted(latest)]
    if not rows:
        raise ResearchInputRefused('No issue-time known history available')
    return rows[-128:], len(rows)



def _action_context(review, model):
    """Display only same-asset receipts known at issue; never adjust source prices."""
    actions = _json(review.payload_bytes)['actions']
    if not actions:
        return ''  # Preserve existing artifacts when no action evidence was supplied.
    known = [row for row in actions if row['asset_id'] == model.asset_id
             and aware(row['available_at']) <= model.issued_at]
    known.sort(key=lambda row: (aware(row['effective_at']), row['action_id']))
    rows = []
    for row in known[:128]:
        status = ('Effective by issue' if aware(row['effective_at']) <= model.issued_at
                  else 'Announced; effective after issue')
        values = (row['action_id'], row['kind'], status, row['effective_at'],
                  row['available_at'], row['amount'], row['economic_unit'],
                  row['source_id'], row['source_sha256'])
        rows.append('<tr>'+''.join('<td>'+_cell(value)+'</td>' for value in values)+'</tr>')
    return f"""<aside class="notice"><h3>Corporate-action receipts known at forecast issue</h3>
<p>Showing {min(len(known), 128)} of {len(known)} supplied same-asset actions available by issue time. Later receipts and other assets are excluded. An empty list does not establish complete corporate-action coverage.</p>
<p>Prices remain unadjusted. Dividends are excluded from price returns; no reinvestment or total-return performance is implied. A split ratio is new shares per old share, not a price multiplier. Source hashes establish supplied-byte consistency, not independent truth or reconciliation.</p>
<div class="scroll" tabindex="0"><table><caption>Caller-recorded action provenance; effective and receipt times are distinct</caption><thead><tr><th scope="col">Action</th><th scope="col">Kind</th><th scope="col">Issue-time status</th><th scope="col">Effective</th><th scope="col">Receipt</th><th scope="col">Amount</th><th scope="col">Economic unit</th><th scope="col">Source</th><th scope="col">Source SHA256</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></aside>"""


def _chart(rows, forecast, interval, number):
    horizon = forecast.get('horizon')
    if type(horizon) is not str or horizon not in ('1D', '5D'):
        raise ResearchInputRefused('Explicit supported cash-session projection horizon required')
    steps = 1 if horizon == '1D' else 5
    values = [row.value for row in rows]+[forecast['reference_price'], forecast['point']]
    if interval is not None:
        values += [forecast['lower'], forecast['upper']]
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in values):
        raise ResearchInputRefused('Finite nonnegative chart values required')
    lo, hi = min(values), max(values)
    scale = max(abs(lo), abs(hi), 1.0)
    span = hi/scale-lo/scale

    def y(value):
        fraction = .5 if span == 0 else (value/scale-lo/scale)/span
        return 205-170*fraction

    def x(index):
        return 55+750*index/(len(rows)-1+steps)

    points = ' '.join(f'{x(i):.2f},{y(row.value):.2f}' for i, row in enumerate(rows))
    target_x = x(len(rows)-1+steps)
    description = (f"{len(rows)} observed cash-session closes known by the issue time, followed by an unobserved forecast {steps} cash sessions after the reference. "
                   'Cash observations are spaced equally; horizontal spacing is not elapsed time. Full values are in the table below.')
    parts = [f'<svg viewBox="0 0 880 255" role="img" aria-labelledby="chart-title-{number} chart-description-{number}">',
             f'<title id="chart-title-{number}">Issue-time historical prices and forecast</title>',
             f'<desc id="chart-description-{number}">{_cell(description)}</desc>',
             '<path d="M55 25V205H825" class="axis"/>',
             f'<text x="5" y="35">{hi:.6g}</text><text x="5" y="205">{lo:.6g}</text>',
             f'<polyline class="history" points="{points}"/>',
             f'<path class="projection" d="M{x(len(rows)-1):.2f} {y(rows[-1].value):.2f}L{target_x:.2f} {y(forecast["point"]):.2f}"/>']
    if interval is not None:
        parts += [f'<path class="interval" d="M{target_x:.2f} {y(forecast["lower"]):.2f}V{y(forecast["upper"]):.2f}"/>']
    parts += [f'<circle class="point" cx="{target_x:.2f}" cy="{y(forecast["point"]):.2f}" r="5"/>',
              f'<text x="55" y="235">{_cell(rows[0].observed_at.date())}</text>',
              '<text x="740" y="235">Forecast only</text></svg>']
    return ''.join(parts)


def render_daily_forecast_visual(*, bundle_root, receipt_name, expected_receipt_sha256,
                                 title='Daily forecast evidence', availability_budget_seconds=None):
    if type(title) is not str or not 1 <= len(title) <= 120 or any(ord(char) < 32 for char in title):
        raise ResearchInputRefused('Bounded plain-text title required')
    verify_daily_forecast_receipt(bundle_root=bundle_root, receipt_name=receipt_name,
                                  expected_receipt_sha256=expected_receipt_sha256)
    reader = BundleReader(bundle_root)
    receipt = json.loads(_read(reader, receipt_name))
    _, asof, prepared, ledger = _prepare_forecast_batch(reader, receipt['batch_plan'])
    panels, diagnostics = [], {}
    for number, ((review, model, interval, _probability, _source), item) in enumerate(zip(prepared, ledger, strict=True)):
        # Forecast bytes were independently refitted by receipt verification.
        raw = _read(reader, item['artifact'])
        artifact = json.loads(raw)
        forecast = artifact['forecast']
        rows, total = _known_history(review, model)
        records = ''.join('<tr>'+''.join('<td>'+_cell(value)+'</td>' for value in (
            row.observed_at.isoformat(), row.available_at.isoformat(), row.value, row.revision))+'</tr>' for row in rows)
        interval_text = ('Not fitted' if interval is None else
                         f"{forecast['lower']:.12g} to {forecast['upper']:.12g}; nominal {forecast['interval_level']:.0%}; coverage unverified")
        availability_markup = ''
        if availability_budget_seconds is not None:
            spec = receipt['request']['forecasts'][number]
            identity = spec['daily_export']
            if identity not in diagnostics:
                diagnostics[identity] = daily_availability(bundle_root=bundle_root, binding_name=identity,
                    expected_binding_sha256=spec['expected_daily_export_sha256'], asof=asof,
                    max_first_receipt_age_seconds=availability_budget_seconds)
            diagnostic = diagnostics[identity]
            availability_markup = f'''<aside class="notice" aria-labelledby="availability-{number}"><h3 id="availability-{number}">Source receipt chronology at the report cutoff</h3>
<p>Pattern {_cell(diagnostic['receipt_pattern'])}. {diagnostic['observation_n']} supplied closes; {diagnostic['price_revision_n']} later price revisions. Median first receipt age {_cell(diagnostic['first_receipt_age']['median_seconds'])} seconds; nearest-rank95th percentile {_cell(diagnostic['first_receipt_age']['p95_seconds'])} seconds.</p>
<p>{diagnostic['first_receipt_budget_exceeded_n']} first receipts exceed the caller's {diagnostic['first_receipt_budget_seconds']} second diagnostic budget. Latest cash close age {_cell(diagnostic['latest_cash_close_age_seconds'])} seconds; time since last supplied receipt {_cell(diagnostic['time_since_last_supplied_receipt_seconds'])} seconds.</p>
<p>These are calendar elapsed ages of caller-recorded receipts, not vendor latency, provider health, coverage or live freshness. This section uses report-cutoff evidence; the price chart still excludes anything unknown at its issue time. Provider freshness NOT_ESTABLISHED.</p></aside>'''
        panels.append(f'''<section class="panel" aria-labelledby="asset-{number}"><h2 id="asset-{number}">{_cell(model.asset_id)} · {_cell(model.method)}</h2>
<p>Issued {_cell(model.issued_at.isoformat())} · target {_cell(forecast['target_at'])} · horizon {_cell(model.horizon)} · USD · regular-session daily closes</p>
<p>Reference {_cell(forecast['reference_price'])}; forecast {_cell(forecast['point'])}. Interval: {_cell(interval_text)}.</p>
{_chart(rows, forecast, interval, number)}{availability_markup}{_action_context(review, model)}
<p>Showing {len(rows)} of {total} issue-time known closes. Later observations and revisions are excluded from this chart. Horizontal spacing counts observed cash sessions, not elapsed time. Dashed line and marker are forecasts, not observed prices.</p>
<details><summary>Equivalent price data and receipt times</summary><div class="scroll" tabindex="0"><table><caption>Only values available at issue time; UTC timestamps</caption><thead><tr><th scope="col">Cash close</th><th scope="col">Caller receipt</th><th scope="col">Price (USD)</th><th scope="col">Revision</th></tr></thead><tbody>{records}</tbody></table></div></details>
<p class="provenance">Dataset manifest {_cell(review.manifest_sha256)}<br>Forecast {_cell(item['artifact'])}</p></section>''')
    # Detect ordinary changes during construction, not malicious writer exclusion.
    verify_daily_forecast_receipt(bundle_root=bundle_root, receipt_name=receipt_name,
                                  expected_receipt_sha256=expected_receipt_sha256)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>{_cell(title)}</title><style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;background:#080e17;color:#e7eef7;font:16px/1.6 system-ui,sans-serif}}main{{max-width:1250px;margin:auto;padding:clamp(18px,4vw,50px)}}h1{{font-size:clamp(28px,5vw,44px)}}.notice,.panel{{padding:22px;border:1px solid #3c526d;border-radius:14px;margin:24px 0;background:#101b2b}}.notice{{border-color:#e37786;background:#29151e}}svg{{width:100%;height:auto}}svg text{{fill:#c8d7e8;font-size:12px}}.axis{{fill:none;stroke:#718499}}.history{{fill:none;stroke:#59dfd0;stroke-width:2}}.projection{{fill:none;stroke:#ffc773;stroke-width:2;stroke-dasharray:6 5}}.interval{{fill:none;stroke:#ffc773;stroke-width:6;opacity:.55}}.point{{fill:#ffc773}}.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:9px;border-bottom:1px solid #34435a;text-align:left;white-space:nowrap}}summary{{cursor:pointer}}.provenance{{overflow-wrap:anywhere;font-size:13px;color:#b1c4d9}}a{{color:inherit}}
</style></head><body><main><p>PROJECT ATLAS / SUPPLIED OFFLINE EVIDENCE</p><h1>{_cell(title)}</h1>
<section class="notice"><h2>Synthetic fixtures · production NO-GO</h2><p>No live feed, provider authorization, orders or recovery permission. Availability is a caller-recorded receipt, not authenticated vendor publication. No source completeness, real skill, calibration, coverage or hardware durability is established.</p></section>
<p>Evidence cutoff {_cell(asof.isoformat())}. Each chart has its own issue-time cutoff. Source closes are unadjusted; known unmapped corporate actions refuse. Histories are shown separately per forecast; prices and errors are never pooled across assets.</p>
{''.join(panels)}<footer class="provenance">Caller-retained receipt {_cell(receipt_name)}. Supplied bytes are reproducible; actual historical execution and independent source truth are not attested. Native browser acceptance remains unestablished.</footer></main></body></html>'''


def publish_daily_forecast_visual(*, bundle_root, receipt_name, expected_receipt_sha256, output_root,
                                  title='Daily forecast evidence', availability_budget_seconds=None):
    if BundleReader(bundle_root).root != BundleReader(output_root).root:
        raise ResearchInputRefused('Retain visual companion with the explicit isolated source bundle')
    rendered = render_daily_forecast_visual(bundle_root=bundle_root, receipt_name=receipt_name,
                                             expected_receipt_sha256=expected_receipt_sha256, title=title,
                                             availability_budget_seconds=availability_budget_seconds)
    path = publish_research_text(output_root, rendered, extension='.html')
    if path.read_bytes() != rendered.encode():
        raise ResearchInputRefused('Daily visual publication read-back mismatch')
    return {'status': 'SYNTHETIC_DAILY_VISUAL_PUBLISHED', 'html': path.name,
            'html_sha256': hashlib.sha256(rendered.encode()).hexdigest(), 'receipt': receipt_name,
            'native_browser_acceptance': 'NOT_ESTABLISHED', **FLAGS}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Scriptless synthetic daily forecast visual; no browser or service startup')
    parser.add_argument('--bundle-root', required=True)
    parser.add_argument('--receipt', required=True)
    parser.add_argument('--expected-receipt-sha256', required=True)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--title', default='Daily forecast evidence')
    parser.add_argument('--availability-budget-seconds', type=int)
    args = parser.parse_args(argv)
    try:
        result = publish_daily_forecast_visual(bundle_root=args.bundle_root, receipt_name=args.receipt,
                                               expected_receipt_sha256=args.expected_receipt_sha256,
                                               output_root=args.output_root, title=args.title,
                                               availability_budget_seconds=args.availability_budget_seconds)
    except (ValueError, OSError, TypeError, KeyError, OverflowError):
        parser.exit(2, 'Daily visual refused or incomplete; retain all input and partial evidence.\n')
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
