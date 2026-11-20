"""Compare source-reproduced descriptive replays; never infer model skill."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from html import escape

from app.backtest.forecast_artifacts import publish_research_text
from app.backtest.forecast_dataset import _json
from app.backtest.forecast_report import BundleReader
from app.investment.offline_research import ResearchInputRefused

from scripts.observation_runtime.research_replay import STATES, encoded, fingerprint
from scripts.observation_runtime.research_replay_export import (
    _read_artifact,
    verify_replay,
)

METRICS=('observed_change_percent','session_momentum_percent','relative_volume','premarket_gap_percent')


def _verified(root,name,pin):
    verify_replay(bundle_root=root,manifest_name=name,expected_manifest_sha256=pin)
    reader=BundleReader(root)
    raw=_read_artifact(reader,name)
    if hashlib.sha256(raw).hexdigest()!=pin:
        raise ResearchInputRefused('Replay manifest changed after verification')
    manifest=_json(raw)
    return _json(_read_artifact(reader,manifest['report']))


def compare_exports(*,left_root,left_manifest,left_pin,right_root,right_manifest,right_pin):
    """Read-only; every source is reproduced before any comparison is returned.

    Manifest identities bind sources; they are not authentication or independent
    truth. Reordered/unequal decision plans are refused, never silently joined.
    """
    left=_verified(left_root,left_manifest,left_pin)
    right=_verified(right_root,right_manifest,right_pin)
    clocks=lambda report:[row['decision_at'] for row in report['cases']]
    if left['symbol']!=right['symbol'] or clocks(left)!=clocks(right):
        raise ResearchInputRefused('Paired comparison requires identical symbol and exact decision clocks')
    matrix={a:{b:0 for b in STATES} for a in STATES}
    pairs=[];comparable=0;same=0
    for a,b in zip(left['cases'],right['cases'],strict=True):
        matrix[a['status']][b['status']]+=1
        both=a['status']==b['status']=='DESCRIPTIVE_RESEARCH_ONLY'
        comparable+=both
        aid=a.get('vintage_decision_sha256',a['decision_sha256'])
        bid=b.get('vintage_decision_sha256',b['decision_sha256'])
        unchanged=aid==bid;same+=unchanged
        metrics={}
        for key in METRICS:
            av=a['report']['analysis'].get(key) if both else None
            bv=b['report']['analysis'].get(key) if both else None
            delta=bv-av if av is not None and bv is not None else None
            if delta is not None and not math.isfinite(delta):
                raise ResearchInputRefused('Non-finite descriptive difference cannot be published')
            metrics[key]={'left':av,'right':bv,'right_minus_left':delta,
                          'availability':('BOTH_OBSERVED' if av is not None and bv is not None else
                            'LEFT_ONLY' if av is not None else 'RIGHT_ONLY' if bv is not None else 'UNAVAILABLE')}
        pairs.append({'decision_at':a['decision_at'],'left_decision_sha256':aid,
                      'right_decision_sha256':bid,'left_status':a['status'],
                      'right_status':b['status'],'same_evidence':unchanged,'both_descriptive':both,'metrics':metrics})
    return {'schema':'ATLAS_DESCRIPTIVE_COMPARISON_V1','mode':'SYNTHETIC_REPLAY','symbol':left['symbol'],
            'left_manifest_sha256':left_pin,'right_manifest_sha256':right_pin,
            'planned_pair_n':len(pairs),'both_descriptive_n':comparable,'not_both_descriptive_n':len(pairs)-comparable,
            'same_evidence_n':same,'changed_evidence_n':len(pairs)-same,'status_pair_counts':matrix,'pairs':pairs,
            'comparison_policy':'IDENTICAL_SYMBOL_EXACT_ORDERED_CLOCKS_NO_DROPPED_DECISIONS',
            'sources_reproduced':True,'source_archives_required':True,'source_authenticated':False,
            'predictive_skill_established':False,'network_authorized':False,'startup_authorized':False,
            'recovery_authorized':False,'trading_authorized':False}


def render_comparison(report):
    rows=[]
    for row in report['pairs']:
        values=(row['decision_at'],row['left_status'],row['right_status'],row['same_evidence'],
                row['metrics']['observed_change_percent']['right_minus_left'])
        rows.append('<tr>'+''.join('<td>'+escape('Unknown' if v is None else str(v))+'</td>' for v in values)+'</tr>')
    return ("<!doctype html><html lang='en'><meta charset='utf-8'><title>Atlas paired descriptive replay</title>"
            '<h1>Paired descriptive replay</h1><p>Synthetic research; no forecasting skill, winner, order, or P&amp;L. '
            'Both original source archives are required for reproduction. Refusals are not dropped.</p>'
            '<p>Planned pairs: '+str(report['planned_pair_n'])+'; both descriptive: '+str(report['both_descriptive_n'])+
            '</p><table><tr><th>Clock</th><th>Left state</th><th>Right state</th><th>Same evidence</th>'
            '<th>Observed change difference (percentage points)</th></tr>'+''.join(rows)+'</table></html>')


def browser_comparison(report):
    text=encoded(report).decode()
    result=encoded({'schema':'ATLAS_DESCRIPTIVE_COMPARISON_BROWSER_V1','report_json':text,
                    'payload_sha256':hashlib.sha256(text.encode()).hexdigest()}).decode()
    if len(result.encode())>1_000_000:raise ResearchInputRefused('Bounded comparison browser export required')
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description='Offline source-verified paired descriptive replay; no live access')
    for side in ('left','right'):
        for field in ('root','manifest','pin'):parser.add_argument('--'+side+'-'+field,required=True)
    parser.add_argument('--output-root',required=True)
    args=parser.parse_args(argv)
    try:
        report=compare_exports(**{key:value for key,value in vars(args).items() if key!='output_root'})
        # Preflight every output size before any publication. Preserve partial
        # evidence if a later publication/readback fails; never report success.
        texts=[(encoded(report).decode(),'.json'),(render_comparison(report),'.html'),(browser_comparison(report),'.json')]
        if any(len(text.encode())>2_000_000 for text,_ in texts):
            raise ResearchInputRefused('Comparison output exceeds immutable publisher budget')
        outputs=[]
        for text,extension in texts:
            path=publish_research_text(args.output_root,text,extension=extension)
            if path.name!=hashlib.sha256(text.encode()).hexdigest()+extension or path.read_text(encoding='utf-8')!=text:
                raise ResearchInputRefused('Comparison publication/readback uncertain; preserve evidence')
            outputs.append(path.name)
    except (OSError,ValueError,TypeError,KeyError,OverflowError) as error:
        print(json.dumps({'status':'REFUSED','error_type':type(error).__name__,'trading_authorized':False}))
        return 2
    print(json.dumps({'status':'OFFLINE_COMPARISON_EXPORTED','report':outputs[0],'dashboard':outputs[1],
                      'browser_export':outputs[2],
                      'report_sha256':fingerprint(report),'planned_pair_n':report['planned_pair_n'],
                      'trading_authorized':False},sort_keys=True));return 0


if __name__=='__main__':raise SystemExit(main())
