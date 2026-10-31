"""Human-readable coverage companion derived only from verified holdout evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from html import escape

from app.backtest.forecast_artifacts import publish_research_text
from app.backtest.forecast_report import BundleReader
from app.investment.offline_research import ResearchInputRefused

from scripts.observation_runtime.chart_archive import FLAGS
from scripts.observation_runtime.daily_probability_replay import (
    diagnose_daily_probability_holdout,
)


def render_daily_holdout_coverage(*, bundle_root, companion_name, expected_companion_sha256):
    diagnostic = diagnose_daily_probability_holdout(bundle_root=bundle_root, companion_name=companion_name,
                                                   expected_companion_sha256=expected_companion_sha256)

    def cell(value):
        return escape(str(value), quote=True)

    def row(values):
        return '<tr>'+''.join('<td>'+cell(value)+'</td>' for value in values)+'</tr>'

    states = ''.join(row((state['status'], state['n'], state['meaning'])) for state in diagnostic['states'])
    reasons = ''.join(row((reason['reason'], reason['n'])) for reason in diagnostic['refusal_reasons'])
    if not reasons:
        reasons = '<tr><td colspan="2">No requested case was refused.</td></tr>'
    counts = diagnostic['counts']
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>Atlas holdout evidence coverage</title><style>body{{background:#09111c;color:#e8f1fc;font:16px/1.6 system-ui;margin:auto;max-width:1100px;padding:24px}}table{{border-collapse:collapse;width:100%}}th,td{{padding:12px;border:1px solid #486078;text-align:left;vertical-align:top}}.scroll{{overflow:auto}}.pin{{overflow-wrap:anywhere}}aside{{border:1px solid #e88994;padding:16px}}</style></head><body><main>
<h1>Holdout evidence coverage</h1><aside><h2>Synthetic evidence - production NO-GO</h2><p>Coverage describes supplied records, not real market performance, provider authorization, calibration or independently unseen custody. No startup, recovery, trading or notification authority is granted.</p></aside>
<p>Asset {cell(diagnostic['asset_id'])}; point model {cell(diagnostic['method'])}; lookback {cell(diagnostic['lookback'])}.</p>
<p>Evidence cutoff {cell(diagnostic['evidence_asof'])}; outcome cutoff {cell(diagnostic['outcome_asof'])}. These are fixed report clocks, not current feed freshness.</p>
<h2>Every requested case remains accounted for</h2><p>Requested {counts['requested_n']} = refused {counts['refused_n']} + issued {counts['issued_n']}. Issued {counts['issued_n']} = resolved {counts['resolved_n']} + unscored {counts['unscored_n']}.</p>
<div class="scroll" tabindex="0"><table><caption>Distinct case states and their evidence requirements</caption><thead><tr><th scope="col">State</th><th scope="col">Cases</th><th scope="col">Meaning</th></tr></thead><tbody>{states}</tbody></table></div>
<h2>Why forecasts were refused</h2><div class="scroll" tabindex="0"><table><caption>Exact source or fitting refusal, grouped without dropping cases</caption><thead><tr><th scope="col">Reason</th><th scope="col">Cases</th></tr></thead><tbody>{reasons}</tbody></table></div>
<p>Distinct resolved targets {diagnostic['distinct_resolved_targets']}; sample status {cell(diagnostic['sample_status'])}. Pending and missing labels are never zero-error outcomes. Refusal is not a failed prediction. Repeated targets and small samples do not establish independent accuracy.</p>
<h2>Retained commitments</h2><p class="pin">Holdout companion {cell(diagnostic['companion'])}<br>Report {cell(diagnostic['report'])}<br>Daily source {cell(diagnostic['daily_export'])}<br>Logical protocol {cell(diagnostic['protocol_sha256'])}</p>
<p>The original holdout report remains the per-case scoring record. This companion adds explanations; it does not retune, recompute an alternative score or authenticate historical execution. Native browser acceptance NOT_ESTABLISHED.</p></main></body></html>'''


def publish_daily_holdout_coverage(*, bundle_root, companion_name, expected_companion_sha256, output_root):
    if BundleReader(bundle_root).root != BundleReader(output_root).root:
        raise ResearchInputRefused('Retain coverage companion in the explicit isolated evidence bundle')
    text = render_daily_holdout_coverage(bundle_root=bundle_root, companion_name=companion_name,
                                         expected_companion_sha256=expected_companion_sha256)
    path = publish_research_text(output_root, text, extension='.html')
    if path.read_bytes() != text.encode():
        raise ResearchInputRefused('Coverage publication read-back mismatch')
    return {'status': 'SYNTHETIC_HOLDOUT_COVERAGE_PUBLISHED', 'html': path.name,
            'html_sha256': hashlib.sha256(text.encode()).hexdigest(), 'companion': companion_name,
            'native_browser_acceptance': 'NOT_ESTABLISHED', **FLAGS}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Scriptless verified synthetic holdout coverage; no browser or service')
    parser.add_argument('--bundle-root', required=True)
    parser.add_argument('--companion', required=True)
    parser.add_argument('--expected-companion-sha256', required=True)
    parser.add_argument('--output-root', required=True)
    args = parser.parse_args(argv)
    try:
        result = publish_daily_holdout_coverage(bundle_root=args.bundle_root, companion_name=args.companion,
            expected_companion_sha256=args.expected_companion_sha256, output_root=args.output_root)
    except (ValueError, OSError, TypeError, KeyError, OverflowError):
        parser.exit(2, 'Holdout coverage refused or incomplete; preserve sources and partial evidence.\n')
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
