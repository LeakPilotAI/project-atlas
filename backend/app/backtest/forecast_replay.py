"""Deterministic synthetic walk-forward and untouched-partition diagnostics."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from statistics import fmean

from app.backtest.forecast_baselines import (
    PROBABILITY_METHOD,
    checked_dataset,
    fingerprint,
    fit_baseline,
    model_fingerprint,
    predict_baseline,
    predict_probability_baseline,
    probability_algorithm,
)
from app.backtest.forecast_dataset import score_dataset_forecasts
from app.backtest.forecast_evaluation import ForecastEvidenceRefused, Outcome, _time


def replay_baselines(review, *, asset_id, issued_times, evidence_asof, method="NO_CHANGE", lookback=20, horizon="1D", outcome_asof=None, source_review=None, probability_method=None):
    """Every case actually refits from its past; missing labels remain pending.

    Insufficient cases remain in an explicit refusal ledger, never disappear
    from the denominator. This is synthetic replay, not prospective evidence.
    """
    checked_dataset(review, evidence_asof)
    if probability_method is not None and (type(probability_method) is not str or probability_method!=PROBABILITY_METHOD or horizon!='1D'):
        raise ForecastEvidenceRefused('Supported explicit next-close probability replay required')
    if not isinstance(issued_times, (list, tuple)) or not 1 <= len(issued_times) <= 128:
        raise ForecastEvidenceRefused("Bounded replay issue times required")
    outcome_asof = _time(evidence_asof) if outcome_asof is None else _time(outcome_asof)
    if outcome_asof > _time(evidence_asof):
        raise ForecastEvidenceRefused("Outcome vintage exceeds evidence time")
    times = tuple(_time(t) for t in issued_times)
    if len(set(times)) != len(times) or times != tuple(sorted(times)) or any(t > outcome_asof for t in times):
        raise ForecastEvidenceRefused("Unique chronological issued cases required")
    forecasts, outcomes, cases = [], [], []
    for issued in times:
        try:
            model = fit_baseline(review, asset_id=asset_id, issued_at=issued, evidence_asof=evidence_asof,
                                 method=method, lookback=lookback, horizon=horizon, source_review=source_review)
            if probability_method is None:
                forecast = predict_baseline(model, review, evidence_asof=evidence_asof, source_review=source_review)
                training_audit=None
            else:
                forecast,training_audit=predict_probability_baseline(model,review,evidence_asof=evidence_asof,source_review=source_review)
        except ForecastEvidenceRefused as error:
            cases.append({"issued_at": issued.isoformat(), "status": "REFUSED", "reason": str(error)})
            continue
        forecasts.append(forecast)
        available = [r for r in review.observations if r.asset_id == asset_id and r.observed_at == forecast.target_at
                     and r.available_at <= outcome_asof]
        outcome = None
        if available:
            row = max(available, key=lambda r: r.available_at)
            outcome = Outcome(forecast.forecast_id, asset_id, forecast.asset_class, forecast.target_at,
                              row.observed_at, row.available_at, row.value, row.source_id, row.revision, "SYNTHETIC")
            outcomes.append(outcome)
        case={"issued_at": issued.isoformat(), "status": "RESOLVED" if outcome else "PENDING",
                      "model_sha256": model_fingerprint(model), "training_sha256": model.training_sha256,
                      "training_available_through": forecast.training_available_through.isoformat(),
                      "forecast_id": forecast.forecast_id}
        if probability_method is not None:
            state='RESOLVED' if outcome else 'PENDING_TARGET' if forecast.target_at>outcome_asof else 'PENDING_PUBLICATION' if any(r.asset_id==asset_id and r.observed_at==forecast.target_at for r in review.observations) else 'MISSING_OUTCOME'
            actual_up=int(outcome.price>forecast.reference_price) if outcome else None
            case.update(status=state,target_at=forecast.target_at.isoformat(),probability_up=forecast.probability_up,
                        probability_training=training_audit,reference=forecast.reference_price,actual=outcome.price if outcome else None,
                        actual_up=actual_up,source_revision=outcome.revision if outcome else None,
                        source_available_at=outcome.available_at.isoformat() if outcome else None,
                        brier=(forecast.probability_up-actual_up)**2 if outcome else None)
        cases.append(case)
    score = score_dataset_forecasts(review, forecasts, outcomes, asof=evidence_asof, outcome_asof=outcome_asof)
    result={"schema": "AFI_SYNTHETIC_REPLAY_V1", "evidence_class": "SYNTHETIC", "asset_id": asset_id,
            "method": method, "lookback": lookback, "horizon": horizon,
            "requested_n": len(times), "refused_n": sum(c["status"] == "REFUSED" for c in cases),
            "cases": cases, "forecasts": forecasts, "outcomes": outcomes, "score": score,
            "production_approved": False, "trading_authority": False, "predictive_skill_established": False}
    if probability_method is not None:
        resolved=[c for c in cases if c['status']=='RESOLVED'];targets={_time(f.target_at) for f in forecasts if any(o.forecast_id==f.forecast_id for o in outcomes)}
        n=len(resolved);brier=fmean(c['brier'] for c in resolved) if n else None
        result.update(schema='AFI_SYNTHETIC_PROBABILITY_REPLAY_V1',probability_method=probability_method,
                      asof=_time(evidence_asof).isoformat(),outcome_asof=outcome_asof.isoformat(),
                      dataset_sha256=review.content_sha256,manifest_sha256=review.manifest_sha256,
                      release_source_sha256=source_review.release_sha256 if source_review else None,
                      issued_n=len(forecasts),resolved_n=n,unscored_n=len(forecasts)-n,
                      pending_target_n=sum(c['status']=='PENDING_TARGET' for c in cases),
                      pending_publication_n=sum(c['status']=='PENDING_PUBLICATION' for c in cases),
                      missing_outcome_n=sum(c['status']=='MISSING_OUTCOME' for c in cases),
                      probability_diagnostics={'probability_n':n,'distinct_target_n':len(targets),'brier':brier,
                         'uninformative_baseline_brier':.25 if n else None,'ratio_to_baseline':brier/.25 if n else None,
                         'status':'INSUFFICIENT_EVIDENCE' if n<20 else 'OVERLAPPING_TARGET_EVIDENCE' if len(targets)<20 else 'DIAGNOSTIC_ONLY'},
                      calibration_established=False,independent_samples_established=False,retuning_allowed=False,
                      history_completeness_verified=False)
    return result


def freeze_selection(review, *, asset_id, selection_issues, frozen_at, evidence_asof, lookback=20, horizon="1D",
                     embargo=timedelta(0), source_review=None):
    """Choose between fixed naive/drift candidates on ONLY pre-freeze labels.

    Every requested selection case must resolve before freeze minus embargo.
    Configuration/case set is fingerprinted. No holdout labels are consumed.
    """
    frozen_at, evidence_asof = _time(frozen_at), _time(evidence_asof)
    if frozen_at > evidence_asof or type(embargo) is not timedelta or embargo < timedelta(0):
        raise ForecastEvidenceRefused("Invalid selection freeze/embargo")
    reports = {}
    for method in ("NO_CHANGE", "ENDPOINT_DRIFT"):
        replay = replay_baselines(review, asset_id=asset_id, issued_times=selection_issues,
                                  evidence_asof=evidence_asof, method=method, lookback=lookback, horizon=horizon,
                                  outcome_asof=frozen_at-embargo-timedelta(microseconds=1), source_review=source_review)
        if (replay["refused_n"] or len(replay["outcomes"]) != replay["requested_n"]
                or any(f.issued_at >= frozen_at or f.target_at >= frozen_at-embargo for f in replay["forecasts"])
                or any(o.available_at >= frozen_at-embargo for o in replay["outcomes"])):
            raise ForecastEvidenceRefused("Selection includes unavailable, embargoed or holdout labels")
        reports[method] = replay
    if len(selection_issues) < 2:
        raise ForecastEvidenceRefused("At least two selection cases required")
    # Fixed tie break is part of the frozen protocol; no holdout optimization.
    selected = min(reports, key=lambda m: (reports[m]["score"]["cohorts"][0]["mae"], m != "NO_CHANGE"))
    # V1 already binds lookback/method and fitted forecast IDs. Preserve its
    # historical case serialization rather than rewriting frozen selection bytes.
    result = {"schema": "AFI_SELECTION_FREEZE_V1", "asset_id": asset_id,
              "selection_issues": [_time(t).isoformat() for t in selection_issues], "frozen_at": frozen_at.isoformat(),
              "embargo_seconds": embargo.total_seconds(), "lookback": lookback, "horizon": horizon,
              "selected_method": selected, "candidate_mae": {m:r["score"]["cohorts"][0]["mae"] for m,r in reports.items()},
              "selection_case_sha256": fingerprint({m:[{k:v for k,v in asdict(f).items() if k!="model_configuration_sha256"} for f in r["forecasts"]] for m,r in reports.items()}),
              "dataset_sha256": review.content_sha256, "manifest_sha256": review.manifest_sha256,
              "independently_unseen": False, "production_approved": False}
    if source_review is not None:
        result["release_source_sha256"] = source_review.release_sha256
    return {**result, "freeze_sha256": fingerprint(result)}


def evaluate_holdout(review, selection, *, holdout_issues, evidence_asof, outcome_asof=None, source_review=None):
    """Reconstruct freeze, enforce disjoint post-freeze issues, retain both baselines.

    This demonstrates algorithmic separation on fixtures, not human custody of an
    unseen real holdout. Frozen-method performance cannot enable activation.
    """
    if type(selection) is not dict:
        raise ForecastEvidenceRefused("Exact frozen selection required")
    try:
        from datetime import datetime
        expected = freeze_selection(review, asset_id=selection["asset_id"],
                                    selection_issues=[datetime.fromisoformat(t) for t in selection["selection_issues"]],
                                    frozen_at=datetime.fromisoformat(selection["frozen_at"]), evidence_asof=evidence_asof,
                                    lookback=selection["lookback"], horizon=selection["horizon"],
                                    embargo=timedelta(seconds=selection["embargo_seconds"]), source_review=source_review)
        if selection != expected:
            raise ForecastEvidenceRefused("Substituted selection freeze")
        frozen = datetime.fromisoformat(selection["frozen_at"])
        if not isinstance(holdout_issues, (list, tuple)) or not holdout_issues or any(_time(t) < frozen for t in holdout_issues):
            raise ForecastEvidenceRefused("Holdout starts before freeze or is empty")
        if {_time(t).isoformat() for t in holdout_issues} & set(selection["selection_issues"]):
            raise ForecastEvidenceRefused("Selection/holdout overlap")
        reports = {m:replay_baselines(review, asset_id=selection["asset_id"], issued_times=holdout_issues,
                                     evidence_asof=evidence_asof, method=m, lookback=selection["lookback"], horizon=selection["horizon"], outcome_asof=outcome_asof, source_review=source_review)
                   for m in ("NO_CHANGE", "ENDPOINT_DRIFT")}
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        if isinstance(error, ForecastEvidenceRefused):
            raise
        raise ForecastEvidenceRefused("Malformed selection/holdout evidence") from error
    return {"schema": "AFI_SYNTHETIC_HOLDOUT_V1", "selection": selection, "reports": reports,
            "selected_method": selection["selected_method"], "retuning_allowed": False,
            "independently_unseen": False, "production_approved": False, "predictive_skill_established": False}


def freeze_probability_protocol(review, *, asset_id, selection_issues, holdout_issues, frozen_at,
                                evidence_asof, lookback=20, embargo=timedelta(0), source_review=None):
    """Bind fixed probability rules and planned post-freeze cases, not custody.

    The existing point selection uses pre-freeze MAE only. The probability rule
    is never selected or tuned on holdout outcomes. A caller-retained digest is
    required for evaluation; a local declaration is not independent attestation.
    """
    selection=freeze_selection(review,asset_id=asset_id,selection_issues=selection_issues,frozen_at=frozen_at,
                               evidence_asof=evidence_asof,lookback=lookback,horizon='1D',embargo=embargo,source_review=source_review)
    if not isinstance(holdout_issues,(list,tuple)) or not 1<=len(holdout_issues)<=128:
        raise ForecastEvidenceRefused('Bounded planned holdout cases required')
    times=tuple(_time(t) for t in holdout_issues);frozen=_time(frozen_at)
    if times!=tuple(sorted(set(times))) or any(t<frozen for t in times) or set(times)&{_time(t) for t in selection_issues}:
        raise ForecastEvidenceRefused('Unique chronological disjoint post-freeze holdout required')
    algorithm=probability_algorithm()
    result={'schema':'AFI_PROBABILITY_PROTOCOL_V1','selection':selection,'probability_algorithm':algorithm,
            'probability_algorithm_sha256':fingerprint(algorithm),'holdout_issues':[t.isoformat() for t in times],
            'scope':'ALGORITHMIC_PARTITION_ONLY_NOT_INDEPENDENT_CUSTODY','retuning_allowed':False,
            'independently_unseen':False,'calibration_established':False,'production_approved':False,'trading_authority':False}
    return {**result,'protocol_sha256':fingerprint(result)}


def evaluate_probability_holdout(review, protocol, *, expected_protocol_sha256, evidence_asof,
                                 outcome_asof=None, source_review=None):
    """Reconstruct the exact pinned protocol before evaluating planned cases."""
    if (type(protocol) is not dict or type(expected_protocol_sha256) is not str or len(expected_protocol_sha256)!=64
            or any(c not in '0123456789abcdef' for c in expected_protocol_sha256)):
        raise ForecastEvidenceRefused('Exact protocol and explicit caller-retained digest required')
    try:
        selection=protocol['selection']
        expected=freeze_probability_protocol(review,asset_id=selection['asset_id'],
                    selection_issues=[datetime.fromisoformat(t) for t in selection['selection_issues']],
                    holdout_issues=[datetime.fromisoformat(t) for t in protocol['holdout_issues']],
                    frozen_at=datetime.fromisoformat(selection['frozen_at']),evidence_asof=evidence_asof,
                    lookback=selection['lookback'],embargo=timedelta(seconds=selection['embargo_seconds']),source_review=source_review)
        # Canonical comparison distinguishes booleans from counts and refuses
        # extra fields; matching a self-reported hash alone is never sufficient.
        if expected['protocol_sha256']!=expected_protocol_sha256 or fingerprint(protocol)!=fingerprint(expected):
            raise ForecastEvidenceRefused('Protocol differs from reconstructed evidence or retained pin')
        replay=replay_baselines(review,asset_id=selection['asset_id'],issued_times=[datetime.fromisoformat(t) for t in expected['holdout_issues']],
                    evidence_asof=evidence_asof,method=selection['selected_method'],lookback=selection['lookback'],horizon='1D',
                    probability_method=PROBABILITY_METHOD,outcome_asof=outcome_asof,source_review=source_review)
    except (KeyError,TypeError,ValueError,OverflowError) as error:
        if isinstance(error,ForecastEvidenceRefused):raise
        raise ForecastEvidenceRefused('Malformed frozen probability protocol') from error
    return {'schema':'AFI_PROBABILITY_HOLDOUT_V1','protocol':expected,'expected_protocol_sha256':expected_protocol_sha256,
            'selected_point_method':selection['selected_method'],'selection_basis':'PRE_FREEZE_POINT_MAE_NOT_HOLDOUT_BRIER',
            'replay':replay,'retuning_allowed':False,'independently_unseen':False,'calibration_established':False,
            'predictive_skill_established':False,'production_approved':False,'trading_authority':False}
