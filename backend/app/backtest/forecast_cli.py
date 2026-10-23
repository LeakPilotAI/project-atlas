"""Explicit-input offline synthetic AFI CLI. Never starts a runtime or provider."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

from app.backtest.forecast_artifacts import publish_forecast, publish_research_text, read_forecast
from app.backtest.forecast_baselines import PROBABILITY_METHOD, canonical, fingerprint, fit_baseline
from app.backtest.forecast_dashboard import (
    render_dashboard,
    render_probability_holdout,
    render_probability_replay,
)
from app.backtest.forecast_dataset import MAX_BYTES, _json, review_dataset
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_replay import (
    evaluate_probability_holdout,
    freeze_probability_protocol,
    replay_baselines,
)
from app.backtest.forecast_source import (
    OPTIONAL_FILES,
    REQUIRED_FILES,
    review_source,
    review_source_archive,
)


def _read(path, *, limit=MAX_BYTES):
    path = Path(path)
    if path.is_symlink() or path.is_junction() or not path.is_file():
        raise ForecastEvidenceRefused("Explicit regular offline input file required")
    with path.open("rb") as handle:
        raw = handle.read(limit+1)
    if len(raw)>limit:
        raise ForecastEvidenceRefused("Offline input exceeds bound")
    return raw


def source_from_paths(manifest_path, source_root):
    raw = _read(manifest_path)
    manifest = _json(raw)
    root = Path(source_root).absolute()
    if not root.is_dir() or any(p.is_symlink() or p.is_junction() for p in (root,*root.parents)):
        raise ForecastEvidenceRefused("Existing unlinked source root required")
    if type(manifest) is not dict or type(manifest.get("files")) is not list or not len(REQUIRED_FILES)<=len(manifest["files"])<=14:
        raise ForecastEvidenceRefused("Bounded explicit source manifest required")
    files = {}
    total = 0
    for row in manifest["files"]:
        if type(row) is not dict or type(row.get("path")) is not str or row["path"] not in REQUIRED_FILES | OPTIONAL_FILES:
            raise ForecastEvidenceRefused("Unapproved source path")
        path = root/row["path"]
        if any(p.is_symlink() or p.is_junction() for p in path.parents):
            raise ForecastEvidenceRefused("Linked source path refused")
        files[row["path"]] = _read(path,limit=1_000_000)
        total += len(files[row["path"]])
        if total>10_000_000:
            raise ForecastEvidenceRefused("Source archive read budget exhausted")
    return review_source(raw,files)


def run(*, manifest, records, output_root, asset_id, issued_at, evidence_asof, method="NO_CHANGE", lookback=20, horizon="1D", source_manifest=None, source_root=None, source_archive=None, interval_path=None, probability_method=None):
    """COMPLETE only after artifact and dashboard durability/read-back checks.

    Caller must create an isolated output directory. Partial output survives
    errors and identical retries never overwrite existing evidence.
    """
    if (source_manifest is None) != (source_root is None):
        raise ForecastEvidenceRefused("Both source manifest and root are required")
    if source_archive is not None and source_manifest is not None:
        raise ForecastEvidenceRefused("Choose one explicit source binding method")
    source_review = (review_source_archive(_read(source_archive)) if source_archive is not None else
                     source_from_paths(source_manifest,source_root) if source_manifest is not None else None)
    review = review_dataset(_read(manifest), _read(records), asof=evidence_asof)
    model = fit_baseline(review, asset_id=asset_id, issued_at=issued_at, evidence_asof=evidence_asof,
                         method=method, lookback=lookback, horizon=horizon, source_review=source_review)
    # Explicit frozen calibration only: never fit/retune an interval during publication.
    interval = _json(_read(interval_path)) if interval_path is not None else None
    html = render_dashboard([(review,model,interval,probability_method)] if probability_method is not None else [(review,model,interval)] if interval is not None else [(review,model)], evidence_asof=evidence_asof, source_review=source_review)
    artifact = publish_forecast(output_root, review, model, evidence_asof=evidence_asof, source_review=source_review, interval=interval, probability_method=probability_method)
    read_forecast(artifact, review, evidence_asof=evidence_asof, source_review=source_review)
    dashboard = publish_research_text(output_root, html, extension=".html")
    if hashlib.sha256(dashboard.read_bytes()).hexdigest()!=dashboard.stem:
        raise ForecastEvidenceRefused("Dashboard read-back integrity failure")
    return {"status":"OFFLINE_SYNTHETIC_COMPLETE",**({"probability_method":probability_method,"probability_calibrated":False} if probability_method is not None else {}),**({"interval_binding":"EXPLICIT_FROZEN_SYNTHETIC_ONLY"} if interval is not None else {}),"forecast_artifact":artifact.name,"dashboard":dashboard.name,
            "manifest_sha256":review.manifest_sha256,"dataset_sha256":review.content_sha256,
            "source_binding":"SUPPLIED_ARCHIVE_BYTES_VERIFIED" if source_review else "UNBOUND_LEGACY_DIAGNOSTIC",
            "release_source_sha256":source_review.release_sha256 if source_review else None,
            "production_approved":False,"trading_authority":False,"predictive_skill_established":False}


def run_probability_replay(*, manifest, records, output_root, asset_id, issues, evidence_asof, probability_method,
                           method='NO_CHANGE', lookback=20, horizon='1D', outcome_asof=None,
                           source_manifest=None, source_root=None, source_archive=None):
    """Explicit synthetic issue-list replay with checked append-only publication."""
    if (source_manifest is None)!=(source_root is None) or (source_archive is not None and source_manifest is not None):
        raise ForecastEvidenceRefused('One complete explicit source binding required')
    source_review=(review_source_archive(_read(source_archive)) if source_archive is not None else
                   source_from_paths(source_manifest,source_root) if source_manifest is not None else None)
    review=review_dataset(_read(manifest),_read(records),asof=evidence_asof)
    values=_json(_read(issues))
    if type(values) is not list or not 1<=len(values)<=128 or any(type(v) is not str for v in values):
        raise ForecastEvidenceRefused('Bounded explicit aware replay issue list required')
    times=[datetime.fromisoformat(v) for v in values]
    arguments={'asset_id':asset_id,'issued_times':times,'evidence_asof':evidence_asof,'probability_method':probability_method,
               'method':method,'lookback':lookback,'horizon':horizon,'outcome_asof':outcome_asof,'source_review':source_review}
    if probability_method is None:raise ForecastEvidenceRefused('Probability replay must be explicitly selected')
    report=replay_baselines(review,**arguments)
    snapshot={**report,'forecasts':[asdict(f) for f in report['forecasts']],'outcomes':[asdict(o) for o in report['outcomes']]}
    snapshot['report_sha256']=fingerprint(snapshot)
    raw=json.dumps(snapshot,default=canonical,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n'
    html=render_probability_replay(review,**arguments)
    published=publish_research_text(output_root,raw,extension='.json')
    dashboard=publish_research_text(output_root,html,extension='.html')
    for path in (published,dashboard):
        if hashlib.sha256(path.read_bytes()).hexdigest()!=path.stem:raise ForecastEvidenceRefused('Replay publication read-back failed')
    return {'status':'OFFLINE_SYNTHETIC_REPLAY_COMPLETE','report':published.name,'dashboard':dashboard.name,
            **{k:report[k] for k in ('requested_n','issued_n','refused_n','resolved_n','unscored_n','pending_target_n','pending_publication_n','missing_outcome_n')},
            'production_approved':False,'trading_authority':False,'calibration_established':False,'predictive_skill_established':False}


def _protocol_dataset(manifest,records,evidence_asof,source_manifest,source_root,source_archive):
    if (source_manifest is None)!=(source_root is None) or (source_archive is not None and source_manifest is not None):
        raise ForecastEvidenceRefused('One complete explicit source binding required')
    source=(review_source_archive(_read(source_archive)) if source_archive is not None else
            source_from_paths(source_manifest,source_root) if source_manifest is not None else None)
    return review_dataset(_read(manifest),_read(records),asof=evidence_asof),source


def run_probability_protocol(*,manifest,records,output_root,asset_id,plan,evidence_asof,
                             source_manifest=None,source_root=None,source_archive=None):
    """Publish an explicit local freeze; never claim independent timestamp custody."""
    review,source=_protocol_dataset(manifest,records,evidence_asof,source_manifest,source_root,source_archive)
    specification=_json(_read(plan))
    if (type(specification) is not dict or set(specification)!={'selection_issues','holdout_issues','frozen_at','lookback','embargo_seconds'}
            or type(specification['frozen_at']) is not str or type(specification['embargo_seconds']) not in (int,float)):
        raise ForecastEvidenceRefused('Complete exact probability freeze plan required')
    for field in ('selection_issues','holdout_issues'):
        if type(specification[field]) is not list or not 1<=len(specification[field])<=128 or any(type(t) is not str for t in specification[field]):
            raise ForecastEvidenceRefused('Bounded explicit aware plan cases required')
    protocol=freeze_probability_protocol(review,asset_id=asset_id,
                selection_issues=[datetime.fromisoformat(t) for t in specification['selection_issues']],
                holdout_issues=[datetime.fromisoformat(t) for t in specification['holdout_issues']],
                frozen_at=datetime.fromisoformat(specification['frozen_at']),evidence_asof=evidence_asof,
                lookback=specification['lookback'],embargo=timedelta(seconds=specification['embargo_seconds']),source_review=source)
    path=publish_research_text(output_root,json.dumps(protocol,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n',extension='.json')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=path.stem:raise ForecastEvidenceRefused('Protocol publication read-back failed')
    return {'status':'OFFLINE_SYNTHETIC_PROTOCOL_COMPLETE','protocol':path.name,'protocol_sha256':protocol['protocol_sha256'],
            'holdout_n':len(protocol['holdout_issues']),'independently_unseen':False,'production_approved':False,'trading_authority':False}


def run_probability_holdout(*,manifest,records,output_root,asset_id,protocol_path,expected_protocol_sha256,evidence_asof,
                            outcome_asof=None,source_manifest=None,source_root=None,source_archive=None):
    review,source=_protocol_dataset(manifest,records,evidence_asof,source_manifest,source_root,source_archive)
    protocol=_json(_read(protocol_path))
    evaluated=evaluate_probability_holdout(review,protocol,expected_protocol_sha256=expected_protocol_sha256,
                    evidence_asof=evidence_asof,outcome_asof=outcome_asof,source_review=source)
    if evaluated['protocol']['selection']['asset_id']!=asset_id:raise ForecastEvidenceRefused('Requested asset conflicts with frozen protocol')
    replay=evaluated['replay'];snapshot={**evaluated,'replay':{**replay,'forecasts':[asdict(f) for f in replay['forecasts']],'outcomes':[asdict(o) for o in replay['outcomes']]}}
    snapshot['report_sha256']=fingerprint(snapshot)
    html=render_probability_holdout(review,protocol,expected_protocol_sha256=expected_protocol_sha256,evidence_asof=evidence_asof,outcome_asof=outcome_asof,source_review=source)
    path=publish_research_text(output_root,json.dumps(snapshot,default=canonical,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n',extension='.json')
    dashboard=publish_research_text(output_root,html,extension='.html')
    for p in (path,dashboard):
        if hashlib.sha256(p.read_bytes()).hexdigest()!=p.stem:raise ForecastEvidenceRefused('Holdout publication read-back failed')
    return {'status':'OFFLINE_SYNTHETIC_HOLDOUT_COMPLETE','report':path.name,'dashboard':dashboard.name,
            'protocol_sha256':expected_protocol_sha256,'requested_n':replay['requested_n'],'resolved_n':replay['resolved_n'],
            'refused_n':replay['refused_n'],'retuning_allowed':False,'independently_unseen':False,'calibration_established':False,
            'production_approved':False,'trading_authority':False,'predictive_skill_established':False}


def run_scenarios(*, plan_path, output_root):
    """Publish explicit local assumption research, never a calibrated forecast."""
    from app.backtest.forecast_comparison import scenario_research
    from app.backtest.forecast_dashboard import render_scenarios

    raw = _read(plan_path, limit=32768)
    plan = _json(raw)
    if type(plan) is not dict or set(plan) != {'schema','base_year','milestones','annual_assumptions'} or plan['schema'] != 'AFI_ASSUMPTION_SCENARIO_REQUEST_V1':
        raise ForecastEvidenceRefused('Exact assumption scenario request required')
    arguments = {key:plan[key] for key in ('base_year','milestones','annual_assumptions')}
    report = scenario_research(**arguments)
    html = render_scenarios(**arguments)
    paths = [publish_research_text(output_root,json.dumps(report,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n',extension='.json'),
             publish_research_text(output_root,html,extension='.html')]
    for path in paths:
        if hashlib.sha256(path.read_bytes()).hexdigest() != path.stem:
            raise ForecastEvidenceRefused('Scenario publication read-back failed')
    return {'status':'OFFLINE_CONDITIONAL_SCENARIOS_COMPLETE','report':paths[0].name,'dashboard':paths[1].name,
            'request_sha256':hashlib.sha256(raw).hexdigest(),'scenario_sha256':report['scenario_sha256'],
            'predictive_skill_established':False,'production_approved':False,'trading_authority':False}


def _scenario_main(argv):
    parser = argparse.ArgumentParser(description='Offline assumption scenarios, not forecasts')
    parser.add_argument('--plan',required=True)
    parser.add_argument('--output-root',required=True)
    args = parser.parse_args(argv)
    try:
        result = run_scenarios(plan_path=args.plan,output_root=args.output_root)
    except (ValueError,OSError,OverflowError):
        print(json.dumps({'status':'REFUSED','message':'Scenario input or publication refused; preserve partial evidence.',
                          'production_approved':False,'trading_authority':False}))
        return 2
    print(json.dumps(result,sort_keys=True))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] == 'scenarios':
        return _scenario_main(argv[1:])
    parser=argparse.ArgumentParser(description="Atlas synthetic offline forecast research; no runtime/provider/trading access")
    for flag in ("manifest","records","output-root","asset","asof"):
        parser.add_argument("--"+flag,required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--issued-at')
    mode.add_argument('--replay-issues',help='Explicit JSON list of aware issue timestamps; probability opt-in required')
    mode.add_argument('--freeze-probability-plan',help='Explicit synthetic selection/holdout plan; publishes a local protocol')
    mode.add_argument('--probability-protocol',help='Evaluate exact planned holdout using an existing frozen probability protocol')
    parser.add_argument('--expected-protocol-sha256',help='Caller-retained protocol digest; required for holdout evaluation')
    parser.add_argument('--outcome-asof',help='Explicit replay label-vintage cutoff; never later than asof')
    parser.add_argument("--interval",help="Explicit frozen synthetic calibration JSON; never fitted automatically")
    parser.add_argument('--probability-method',choices=[PROBABILITY_METHOD],help='Explicit synthetic next-close frequency baseline; not calibrated')
    parser.add_argument("--source-archive")
    parser.add_argument("--source-manifest")
    parser.add_argument("--source-root")
    parser.add_argument("--method",choices=["NO_CHANGE","ENDPOINT_DRIFT"])
    parser.add_argument("--lookback",type=int)
    parser.add_argument("--horizon",choices=["1D","5D"])
    args=parser.parse_args(argv)
    try:
        if args.freeze_probability_plan is not None or args.probability_protocol is not None:
            if any(v is not None for v in (args.method,args.lookback,args.horizon,args.probability_method,args.interval)):
                raise ForecastEvidenceRefused('Protocol parameters cannot be overridden')
            shared={'manifest':args.manifest,'records':args.records,'output_root':args.output_root,'asset_id':args.asset,
                    'evidence_asof':datetime.fromisoformat(args.asof),'source_manifest':args.source_manifest,'source_root':args.source_root,'source_archive':args.source_archive}
            if args.freeze_probability_plan is not None:
                if args.expected_protocol_sha256 is not None or args.outcome_asof is not None:raise ForecastEvidenceRefused('Freeze plan does not accept evaluation overrides')
                result=run_probability_protocol(**shared,plan=args.freeze_probability_plan)
            else:
                result=run_probability_holdout(**shared,protocol_path=args.probability_protocol,expected_protocol_sha256=args.expected_protocol_sha256,
                            outcome_asof=datetime.fromisoformat(args.outcome_asof) if args.outcome_asof else None)
        elif args.replay_issues is not None:
            if args.expected_protocol_sha256 is not None:raise ForecastEvidenceRefused('Protocol pin applies only to holdout evaluation')
            if args.interval is not None:raise ForecastEvidenceRefused('Replay does not silently reuse an interval calibration')
            result=run_probability_replay(manifest=args.manifest,records=args.records,output_root=args.output_root,asset_id=args.asset,
                        issues=args.replay_issues,evidence_asof=datetime.fromisoformat(args.asof),probability_method=args.probability_method,
                        method=args.method or 'NO_CHANGE',lookback=args.lookback if args.lookback is not None else 20,horizon=args.horizon or '1D',
                        outcome_asof=datetime.fromisoformat(args.outcome_asof) if args.outcome_asof else None,
                        source_manifest=args.source_manifest,source_root=args.source_root,source_archive=args.source_archive)
        else:
            if args.expected_protocol_sha256 is not None:raise ForecastEvidenceRefused('Protocol pin applies only to holdout evaluation')
            if args.outcome_asof is not None:raise ForecastEvidenceRefused('Outcome vintage applies only to replay')
            result=run(manifest=args.manifest,records=args.records,output_root=args.output_root,asset_id=args.asset,
                   issued_at=datetime.fromisoformat(args.issued_at),evidence_asof=datetime.fromisoformat(args.asof),
                   method=args.method or 'NO_CHANGE',lookback=args.lookback if args.lookback is not None else 20,horizon=args.horizon or '1D',
                   source_manifest=args.source_manifest,source_root=args.source_root,source_archive=args.source_archive,interval_path=args.interval,probability_method=args.probability_method)
    except (ValueError,OSError,OverflowError) as error:
        print(json.dumps({"status":"REFUSED","error_type":type(error).__name__,
                          "message":"Offline input or publication refused; preserve partial evidence and inspect local configuration.",
                          "production_approved":False,"trading_authority":False}))
        return 2
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
