"""Usable offline accountability reports and explicit archive-bundle CLI.

No provider/API startup, registry provisioning, trade execution or external I/O.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html import escape
from pathlib import Path, PurePosixPath
from statistics import fmean
from types import SimpleNamespace

from app.backtest.forecast_artifacts import publish_research_text
from app.backtest.forecast_baselines import fingerprint
from app.backtest.forecast_cli import _read, source_from_paths
from app.backtest.forecast_dataset import _fields, _json, review_dataset
from app.backtest.forecast_evaluation import (
    ForecastEvidenceRefused,
    Outcome,
    _asset,
    _identity,
    _metrics,
    _number,
    _time,
    probability_reliability,
    score_forecasts,
    select_asof,
)
from app.backtest.forecast_outcomes import _forecast, append_outcome, verify_outcome_history


@dataclass(frozen=True)
class ForecastHistory:
    forecast_path: Path
    forecast_review: object
    history: tuple = ()
    expected_head: str | None = None
    source_review: object = None


def _cohort(row, *, bind_provenance=True):
    cohort={k:row[k] for k in ('asset_class','asset_id','horizon','model')}
    if ('model_version' in row)!=('lookback' in row):
        raise ForecastEvidenceRefused('Incomplete model configuration binding')
    if 'model_version' in row:
        _identity(row['model_version'])
        if type(row['lookback']) is not int or not 2<=row['lookback']<=10000:
            raise ForecastEvidenceRefused('Invalid model lookback binding')
        cohort.update(model_version=row['model_version'],lookback=row['lookback'])
    if 'model_configuration_sha256' in row:
        value=row['model_configuration_sha256']
        if type(value) is not str or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise ForecastEvidenceRefused('Invalid model configuration commitment')
        cohort['model_configuration_sha256']=value
    if bind_provenance:
        if any(k in row for k in ('release_source_sha256','forecast_code_sha256','forecast_dataset_manifest_sha256','forecast_dataset_id','forecast_dataset_version')) and 'forecast_dataset_sha256' not in row:
            raise ForecastEvidenceRefused('Incomplete diagnostic dataset/source binding')
        for key in ('forecast_dataset_sha256','release_source_sha256','forecast_dataset_manifest_sha256','forecast_code_sha256'):
            if key not in row:
                continue
            value=row[key]
            if key=='release_source_sha256' and value is None:
                cohort[key]=None
                continue
            if type(value) is not str or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
                raise ForecastEvidenceRefused('Invalid diagnostic dataset/source commitment')
            cohort[key]=value
        manifest_fields=('forecast_dataset_manifest_sha256','forecast_dataset_id','forecast_dataset_version')
        if any(k in row for k in manifest_fields):
            if not all(k in row for k in manifest_fields):
                raise ForecastEvidenceRefused('Incomplete diagnostic manifest/version binding')
            for key in ('forecast_dataset_id','forecast_dataset_version'):
                _identity(row[key]);cohort[key]=row[key]
    return cohort


def _cohort_key(cohort):
    return tuple(cohort[k] for k in ('asset_class','asset_id','horizon','model'))+(cohort.get('model_version',''),cohort.get('lookback',0),cohort.get('forecast_dataset_sha256',''),cohort.get('release_source_sha256') or '',cohort.get('forecast_dataset_manifest_sha256',''),cohort.get('forecast_dataset_id',''),cohort.get('forecast_dataset_version',''),cohort.get('forecast_code_sha256',''),cohort.get('model_configuration_sha256',''))


def directional_diagnostics(rows, *, bind_provenance=True):
    """Descriptive three-state counts; unresolved forecasts are never negatives."""
    if not isinstance(rows,(list,tuple)) or len(rows)>64:
        raise ForecastEvidenceRefused('Bounded directional rows required')
    groups={}
    for row in rows:
        if type(row) is not dict or row.get('status') not in ('RESOLVED','FORECAST_ONLY','PENDING_TARGET','PENDING_PUBLICATION','MISSING_OUTCOME'):
            raise ForecastEvidenceRefused('Exact directional outcome state required')
        _asset(row['asset_id'],row['asset_class']);_identity(row['model'])
        if row['horizon'] not in ('1D','5D'):
            raise ForecastEvidenceRefused('Unsupported directional horizon')
        _number(row['reference'],positive=True);_number(row['forecast_point'],positive=True)
        if row['status']=='RESOLVED':_number(row['actual'],positive=True)
        elif row['actual'] is not None:raise ForecastEvidenceRefused('Unresolved outcome cannot be scored')
        cohort=_cohort(row,bind_provenance=bind_provenance);key=_cohort_key(cohort)
        group=groups.setdefault(key,{'cohort':cohort,'resolved_n':0,'pending_n':0,'matrix':{p:{a:0 for a in ('DOWN','FLAT','UP')} for p in ('DOWN','FLAT','UP')}})
        if row['status']!='RESOLVED':
            group['pending_n']+=1
            continue
        if row['actual'] is None:
            raise ForecastEvidenceRefused('Resolved directional evidence requires an outcome')
        direction=lambda value,reference=row['reference']:'UP' if value>reference else 'DOWN' if value<reference else 'FLAT'
        group['matrix'][direction(row['forecast_point'])][direction(row['actual'])]+=1
        group['resolved_n']+=1
    result=[]
    for key,group in sorted(groups.items()):
        m=group['matrix'];n=group['resolved_n']
        item={**group,
              'correct_n':sum(m[d][d] for d in m),'directional_accuracy':sum(m[d][d] for d in m)/n if n else None,
              'status':'DIAGNOSTIC_ONLY' if n else 'INSUFFICIENT_EVIDENCE'}
        for side in ('UP','DOWN'):
            predicted=sum(m[side].values());actual=sum(m[p][side] for p in m);true=m[side][side]
            item[side.lower()]={'true_positive_n':true,'false_positive_n':predicted-true,'false_negative_n':actual-true,
                                'predicted_n':predicted,'actual_n':actual,'precision':true/predicted if predicted else None,
                                'recall':true/actual if actual else None}
        result.append(item)
    return {'matrix_rows':'FORECAST_DIRECTION','matrix_columns':'OBSERVED_DIRECTION','flat_is_separate':True,
            'pending_excluded_from_accuracy':True,'trade_opportunity_or_profitability_established':False,'cohorts':result}


def signed_error_diagnostics(rows):
    """Descriptive forecast-minus-actual errors within existing provenance cohorts."""
    checked = directional_diagnostics(rows)
    groups = {_cohort_key(c['cohort']): {'cohort':c['cohort'], 'resolved_n':c['resolved_n'],
              'pending_n':c['pending_n'], 'over_n':0, 'under_n':0, 'equal_n':0, 'errors':[]}
              for c in checked['cohorts']}
    for row in rows:
        if row['status'] != 'RESOLVED':
            continue
        error = _number(row['forecast_point']) - _number(row['actual'])
        group = groups[_cohort_key(_cohort(row))]
        group['over_n'] += error > 0
        group['under_n'] += error < 0
        group['equal_n'] += error == 0
        group['errors'].append(error)
    cohorts = []
    for key in sorted(groups):
        group = groups[key]
        errors = group.pop('errors')
        mean = None
        status = 'NO_RESOLVED_OUTCOMES'
        if errors:
            try:
                total = math.fsum(errors)
                mean = total/len(errors)
                if not math.isfinite(mean) or (total != 0 and mean == 0):
                    raise OverflowError('Signed mean exceeds numeric range')
                status = 'DESCRIPTIVE_ONLY'
            except OverflowError:
                mean, status = None, 'UNAVAILABLE_NUMERIC_RANGE'
        cohorts.append({**group, 'mean_signed_error':mean, 'status':status})
    return {'definition':'FORECAST_MINUS_ACTUAL', 'pending_excluded_from_mean':True,
            'predictive_skill_established':False, 'independent_samples_established':False, 'cohorts':cohorts}


def interval_target_support(rows):
    """Descriptive recorded target counts, not independent samples or calibration."""
    diagnostics = interval_diagnostics(rows)
    groups = {(_cohort_key(c['cohort']), c['cohort']['level']):
              {**c, 'distinct_recorded_target_n': 0, 'missing_target_n': 0,
               'repeated_target_n': 0, 'target_support_status': 'NO_RESOLVED_TARGETS'}
              for c in diagnostics['cohorts']}
    targets, order = {}, []
    pattern = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)'
    for row in rows:
        if row.get('interval') is None:
            continue
        key = (_cohort_key(_cohort(row)), row['interval']['level'])
        if key not in targets:
            targets[key] = set()
            order.append(key)
        if row['status'] != 'RESOLVED':
            continue
        value = row.get('target_at')
        try:
            if type(value) is not str or len(value) > 128 or not re.fullmatch(pattern, value) or not 1900 <= int(value[:4]) <= 2200:
                raise ForecastEvidenceRefused('Unrecorded target clock')
            targets[key].add(_report_time(value))
        except (ForecastEvidenceRefused, OverflowError):
            groups[key]['missing_target_n'] += 1
    for key, group in groups.items():
        group['distinct_recorded_target_n'] = len(targets[key])
        group['repeated_target_n'] = group['resolved_n'] - group['missing_target_n'] - len(targets[key])
        group['target_support_status'] = (
            'NO_RESOLVED_TARGETS' if not group['resolved_n'] else
            'UNRECORDED_TARGET_EVIDENCE' if group['missing_target_n'] else
            'REPEATED_TARGET_EVIDENCE' if group['repeated_target_n'] else 'RECORDED_TARGETS_ONLY')
    return {'cohorts': [groups[key] for key in order],
            'independent_samples_established': False, 'calibration_established': False}


def interval_diagnostics(rows, *, minimum_samples=20, bind_provenance=True):
    """Exact-target interval counts, not calibrated coverage or trading evidence."""
    directional_diagnostics(rows,bind_provenance=bind_provenance)  # Reuse bounded identity/outcome/price validation.
    if type(minimum_samples) is not int or not 1<=minimum_samples<=10000:
        raise ForecastEvidenceRefused('Explicit bounded interval sample minimum required')
    groups={};without=0
    for row in rows:
        interval=row.get('interval')
        if interval is None:
            without+=1
            continue
        if type(interval) is not dict or set(interval)!={'lower','upper','level'}:
            raise ForecastEvidenceRefused('Complete original interval required')
        low,high,level=(_number(interval[k]) for k in ('lower','upper','level'))
        if not 0<=low<=row['forecast_point']<=high or not 0<level<1:
            raise ForecastEvidenceRefused('Invalid original interval or level')
        cohort={**_cohort(row,bind_provenance=bind_provenance),'level':level};key=_cohort_key(cohort)+(level,)
        group=groups.setdefault(key,{'cohort':cohort,'forecast_n':0,'pending_n':0,'covered_n':0,'below_n':0,'above_n':0,'widths':[],'scores':[]})
        group['forecast_n']+=1
        if row['status']!='RESOLVED':
            group['pending_n']+=1
            continue
        actual=row['actual'];width=high-low
        score=width+2*(max(low-actual,0)+max(actual-high,0))/(1-level)
        if not math.isfinite(width) or not math.isfinite(score):
            raise ForecastEvidenceRefused('Interval aggregate exceeds finite range')
        group['covered_n']+=low<=actual<=high
        group['below_n']+=actual<low;group['above_n']+=actual>high
        group['widths'].append(width);group['scores'].append(score)
    cohorts=[]
    for key,group in sorted(groups.items()):
        n=len(group['scores'])
        try:
            width=fmean(group['widths']) if n else None;score=fmean(group['scores']) if n else None
        except OverflowError as error:
            raise ForecastEvidenceRefused('Interval aggregate exceeds finite range') from error
        cohorts.append({'cohort':group['cohort'],
                        **{k:v for k,v in group.items() if k not in ('widths','scores')},'resolved_n':n,
                        'coverage':group['covered_n']/n if n else None,'mean_width':width,'mean_interval_score':score,
                        'status':'DIAGNOSTIC_ONLY' if n>=minimum_samples else 'INSUFFICIENT_EVIDENCE'})
    return {'minimum_samples':minimum_samples,'without_interval_n':without,'pending_excluded_from_scores':True,
            'boundary_policy':'INCLUSIVE','calibration_established':False,'coverage_guarantee':False,
            'cohorts':cohorts}


_SCORE_FIELDS=('asset_id','asset_class','horizon','model_id','model_version','dataset_id','dataset_sha256','code_sha256','evidence_class','interval_level','dataset_manifest_sha256','dataset_version')
_SCORE_FIELDS_V2=(*_SCORE_FIELDS,'model_configuration_sha256')
_SCORE_ROW_FIELDS={'model_id':'model','dataset_id':'forecast_dataset_id','dataset_sha256':'forecast_dataset_sha256','code_sha256':'forecast_code_sha256','dataset_manifest_sha256':'forecast_dataset_manifest_sha256','dataset_version':'forecast_dataset_version'}
_PROBABILITY_METRICS={'probability_n','brier','expected_calibration_error','uninformative_half_probability_brier','calibration_bins'}
_INTERVAL_METRICS={'interval_n','interval_coverage','mean_interval_width','mean_interval_score'}


def _report_time(value):
    try:
        return _time(datetime.fromisoformat(value))
    except (TypeError,ValueError) as error:
        raise ForecastEvidenceRefused('Explicit aware report time required') from error


def _count(value,limit=10000):
    if type(value) is not int or not 0<=value<=limit:
        raise ForecastEvidenceRefused('Exact bounded report count required')
    return value


def _same_score(expected,actual):
    if type(expected) is dict:
        return type(actual) is dict and expected.keys()==actual.keys() and all(_same_score(v,actual[k]) for k,v in expected.items())
    if type(expected) is list:
        return type(actual) is list and len(expected)==len(actual) and all(_same_score(a,b) for a,b in zip(expected,actual,strict=True))
    if type(expected) is int:
        return type(actual) is int and expected==actual
    if type(expected) is float:
        return type(actual) in (int,float) and math.isfinite(actual) and abs(expected-actual)<=1e-12*max(1,abs(expected))
    return type(expected) is type(actual) and expected==actual


def _row_metrics(rows):
    pairs=[]
    for row in rows:
        if row['status']!='RESOLVED':continue
        probability=row.get('probability_up')
        if probability is not None and not 0<=_number(probability)<=1:
            raise ForecastEvidenceRefused('Invalid recorded forecast probability')
        interval=row.get('interval')
        forecast=SimpleNamespace(point=row['forecast_point'],reference_price=row['reference'],probability_up=probability,
                                 lower=interval['lower'] if interval else None,upper=interval['upper'] if interval else None,
                                 interval_level=interval['level'] if interval else None)
        pairs.append((forecast,SimpleNamespace(price=row['actual'])))
    try:
        return _metrics(pairs,20)
    except (OverflowError,ValueError,ZeroDivisionError) as error:
        raise ForecastEvidenceRefused('Row score arithmetic refused') from error


def _score_matches(row,cohort):
    if type(cohort) is not dict or not all(k in cohort for k in ('asset_id','asset_class','horizon','model_id')):
        raise ForecastEvidenceRefused('Score cohort identity required')
    _asset(cohort['asset_id'],cohort['asset_class'])
    for key in ('model_id','model_version','dataset_id'):
        if key in cohort:_identity(cohort[key])
    for key in ('dataset_sha256','code_sha256','dataset_manifest_sha256','model_configuration_sha256'):
        if key not in cohort or (key=='dataset_manifest_sha256' and cohort[key] is None):continue
        value=cohort[key]
        if type(value) is not str or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise ForecastEvidenceRefused('Invalid score source commitment')
    if 'dataset_version' in cohort and cohort['dataset_version'] is not None:_identity(cohort['dataset_version'])
    if 'dataset_manifest_sha256' in cohort and (cohort['dataset_manifest_sha256'] is None)!=(cohort.get('dataset_version') is None):raise ForecastEvidenceRefused('Incomplete score manifest/version binding')
    if cohort.get('interval_level') is not None and not 0<_number(cohort['interval_level'])<1:raise ForecastEvidenceRefused('Invalid score interval level')
    for key,value in cohort.items():
        name=_SCORE_ROW_FIELDS.get(key,key)
        if key=='evidence_class':
            if value!='SYNTHETIC':return False
        elif key=='interval_level':
            if 'interval' in row and value!=(row['interval']['level'] if row['interval'] else None):return False
        elif name in row and row[name]!=value:return False
    return True


def _check_report_score(report):
    rows=report['rows'];asof=_report_time(report['asof'])
    interval_diagnostics(rows)
    if not 1<=len(rows)<=64 or _count(report.get('forecast_n'),64)!=len(rows):
        raise ForecastEvidenceRefused('Report forecast count contradicts rows')
    seen=set();declared_cases=set();corrections=0
    for row in rows:
        digest=row.get('forecast_sha256')
        if type(digest) is not str or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest) or digest in seen:
            raise ForecastEvidenceRefused('Repeated or invalid report forecast identity')
        seen.add(digest);issued,target=_report_time(row['issued_at']),_report_time(row['target_at'])
        if issued>asof or target<=issued:raise ForecastEvidenceRefused('Report forecast chronology contradicts rows')
        input_fields=('input_observed_at','input_available_at','input_source_id',
                      'input_source_revision','input_source_sha256')
        if any(key in row for key in input_fields):
            if not all(key in row for key in input_fields):
                raise ForecastEvidenceRefused('Incomplete forecast input provenance')
            observed,available=_report_time(row['input_observed_at']),_report_time(row['input_available_at'])
            _identity(row['input_source_id']);_identity(row['input_source_revision'])
            if observed>available or available>issued:
                raise ForecastEvidenceRefused('Forecast input was unavailable at issue time')
            if row['input_source_sha256'] is not None:_pair_hash(row['input_source_sha256'])
        case=(*_cohort_key(_cohort(row)),issued,target,row['interval']['level'] if row.get('interval') else None)
        if case in declared_cases:raise ForecastEvidenceRefused('Repeated declared report forecast case')
        declared_cases.add(case)
        history=_count(row.get('history_n'),128);correction=_count(row.get('correction_n'),128);corrections+=correction
        if correction>history or (row['status']=='FORECAST_ONLY')!=(history==0):raise ForecastEvidenceRefused('Report history counts contradict rows')
        if history:
            head=row.get('expected_head')
            if type(head) is not str or len(head)!=64 or any(c not in '0123456789abcdef' for c in head):raise ForecastEvidenceRefused('Report history head required')
            cutoff=_report_time(row['last_reconciled_asof'])
            if not issued<=cutoff<=asof or (row['status']=='PENDING_TARGET')!=(cutoff<target):raise ForecastEvidenceRefused('Report reconciliation chronology contradicts rows')
            available=row.get('source_available_at')
            if available is not None and not target<=_report_time(available)<=cutoff:raise ForecastEvidenceRefused('Report outcome publication contradicts rows')
            if row['status']=='RESOLVED' and available is None:raise ForecastEvidenceRefused('Resolved report outcome lacks publication evidence')
        elif any(row.get(k) is not None for k in ('expected_head','last_reconciled_asof','source_available_at','actual')):
            raise ForecastEvidenceRefused('Forecast-only report claims outcome evidence')
    if _count(report.get('correction_n'))!=corrections:raise ForecastEvidenceRefused('Report correction total contradicts rows')
    score=report.get('score');resolved=sum(row['status']=='RESOLVED' for row in rows)
    if type(score) is not dict or any(_count(score.get(k))!=v for k,v in [('issued_n',len(rows)),('scored_n',resolved),('pending_n',len(rows)-resolved)]):
        raise ForecastEvidenceRefused('Report score totals contradict rows')
    for key in ('trading_authority','production_approved','calibration_established','dataset_authenticated'):
        if key in score and score[key] is not False:raise ForecastEvidenceRefused('Unsupported nested score authority')
    cohorts=score.get('cohorts')
    if type(cohorts) is not list or len(cohorts)>64 or any(type(c) is not dict for c in cohorts) or sum(_count(c.get('n')) for c in cohorts)!=resolved:
        raise ForecastEvidenceRefused('Report score cohort counts contradict rows')
    if 'asof' in score and _report_time(score['asof'])!=asof:raise ForecastEvidenceRefused('Score cutoff contradicts report')
    metadata=[c.get('cohort') for c in cohorts]
    if len({fingerprint(c) for c in metadata})!=len(metadata):raise ForecastEvidenceRefused('Repeated score cohort')
    version=report.get('score_rows_contract');bound=version in ('ROW_BOUND_SCORE_V1','ROW_BOUND_SCORE_V2')
    if 'score_rows_contract' in report and not bound:raise ForecastEvidenceRefused('Unknown row score contract')
    if not bound and any('score_cohort' in row or 'probability_up' in row for row in rows):raise ForecastEvidenceRefused('Recorded score inputs require their score contract')
    if bound:
        groups={};cases={}
        fields=_SCORE_FIELDS_V2 if version=='ROW_BOUND_SCORE_V2' else _SCORE_FIELDS
        for row in rows:
            identity=row.get('score_cohort')
            required=set(fields if 'model_configuration_sha256' in row else _SCORE_FIELDS)
            if version=='ROW_BOUND_SCORE_V1' and 'model_configuration_sha256' in row:raise ForecastEvidenceRefused('Configuration-aware score requires V2')
            if type(identity) is not dict or set(identity)!=required or not _score_matches(row,identity) or 'probability_up' not in row or 'interval' not in row:
                raise ForecastEvidenceRefused('Complete original row score binding required')
            if row['probability_up'] is not None and not 0<=_number(row['probability_up'])<=1:raise ForecastEvidenceRefused('Invalid original row probability')
            key=tuple(identity.get(k) for k in fields);case=(*key[:len(_SCORE_FIELDS)],_report_time(row['issued_at']),_report_time(row['target_at']))
            configurations=cases.setdefault(case,set());configuration=identity.get('model_configuration_sha256')
            if configuration in configurations or (configurations and (configuration is None or None in configurations)):raise ForecastEvidenceRefused('Repeated or ambiguous configured forecast case')
            configurations.add(configuration);groups.setdefault(key,[]).append(row)
        expected=score_forecasts([],[],asof=asof)
        expected.update(issued_n=len(rows),scored_n=resolved,pending_n=len(rows)-resolved,
                        cohorts=[{'cohort':{k:v for k,v in zip(fields,key,strict=True) if k!='model_configuration_sha256' or v is not None},**_row_metrics(group)} for key,group in sorted(groups.items(),key=lambda item:repr(item[0]))])
        expected['status']='DIAGNOSTIC_ONLY' if any(c['status']=='DIAGNOSTIC_ONLY' for c in expected['cohorts']) else 'INSUFFICIENT_EVIDENCE'
        if not _same_score(expected,score):raise ForecastEvidenceRefused('Score contradicts complete original row evidence')
    else:
        # Legacy rows did not retain every score input. Validate available fields;
        # never infer missing probability/interval evidence or assign ambiguous groups.
        matches=[[i for i,c in enumerate(metadata) if _score_matches(row,c)] for row in rows]
        if any(not indices for indices in matches):raise ForecastEvidenceRefused('Score cohort identity contradicts rows')
        for i,cohort in enumerate(cohorts):
            if any(i in indices and len(indices)>1 for indices in matches):continue
            group=[row for row,indices in zip(rows,matches,strict=True) if indices==[i]]
            if not group:raise ForecastEvidenceRefused('Unsupported orphan score cohort')
            expected=_row_metrics(group);skip=set()
            if any('probability_up' not in row for row in group):skip|=_PROBABILITY_METRICS
            if any('interval' not in row for row in group):skip|=_INTERVAL_METRICS
            if any(k not in skip and not _same_score(v,cohort.get(k)) for k,v in expected.items()):
                raise ForecastEvidenceRefused('Legacy score contradicts available original row evidence')



def _pair_us(value):
    instant=_report_time(value);delta=instant-datetime(1970,1,1,tzinfo=UTC)
    return str((delta.days*86400+delta.seconds)*1000000+delta.microseconds)


def _pair_hash(value):
    if type(value) is not str or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
        raise ForecastEvidenceRefused('Exact paired evidence commitment required')
    return value


def _point_definition_equal(a,b):
    base=('model','model_version','lookback','forecast_code_sha256')
    return all(a.get(k)==b.get(k) for k in base) and a.get('model_configuration_sha256')==b.get('model_configuration_sha256')


def paired_model_diagnostics(rows, *, asof, model_pairs=None, minimum_samples=20):
    """Descriptive matched price errors; no independent skill or winner proof."""
    interval_diagnostics(rows);asof=_time(asof)
    if type(minimum_samples) is not int or not 2<=minimum_samples<=10000:
        raise ForecastEvidenceRefused('Bounded paired sample threshold required')
    groups={};seen=set()
    for row in rows:
        source=_pair_hash(row.get('forecast_sha256'))
        if source in seen:raise ForecastEvidenceRefused('Repeated paired forecast identity')
        seen.add(source);issued,target=_report_time(row.get('issued_at')),_report_time(row.get('target_at'))
        if issued>asof or target<=issued:raise ForecastEvidenceRefused('Invalid paired forecast chronology')
        for name in ('outcome_dataset_sha256',):
            if row.get(name) is not None:_pair_hash(row[name])
        if row.get('source_revision') is not None:_identity(row['source_revision'])
        cutoff=_report_time(row['last_reconciled_asof']) if row.get('last_reconciled_asof') is not None else None
        available=_report_time(row['source_available_at']) if row.get('source_available_at') is not None else None
        if cutoff is not None and (not issued<=cutoff<=asof or (row['status']=='PENDING_TARGET')!=(cutoff<target)):
            raise ForecastEvidenceRefused('Invalid paired reconciliation chronology')
        if available is not None and (not target<=available<=asof or (cutoff is not None and available>cutoff)):
            raise ForecastEvidenceRefused('Invalid paired outcome publication')
        interval=row.get('interval');binding='UNRECORDED' if 'interval' not in row else 'NONE' if interval is None else 'FLOAT64:'+struct.pack('>d',interval['level']).hex()
        cohort={**_cohort(row),'interval_binding':binding}
        identity=json.dumps(cohort,sort_keys=True,separators=(',',':'),allow_nan=False)
        group=groups.setdefault(identity,{'cohort':cohort,'cases':{},'interval_level':interval['level'] if interval else None,'interval_recorded':'interval' in row})
        key=_pair_us(row['issued_at'])+'/'+_pair_us(row['target_at'])
        if key in group['cases']:raise ForecastEvidenceRefused('Repeated paired model case')
        group['cases'][key]=row
    ids=sorted(groups)
    models=[{'id':key,'cohort':groups[key]['cohort'],'interval_level':groups[key]['interval_level'],'interval_recorded':groups[key]['interval_recorded'],'forecast_n':len(groups[key]['cases']),'resolved_n':sum(r['status']=='RESOLVED' for r in groups[key]['cases'].values()),'pending_n':sum(r['status']!='RESOLVED' for r in groups[key]['cases'].values())} for key in ids]
    candidates=[(a,b) for i,a in enumerate(ids) for b in ids[i+1:] if all(groups[a]['cohort'].get(k)==groups[b]['cohort'].get(k) for k in ('asset_class','asset_id','horizon')) and not _point_definition_equal(groups[a]['cohort'],groups[b]['cohort'])]
    result={'schema':'AFI_PAIRED_MODEL_DIAGNOSTICS_V1','asof':asof.isoformat(),'minimum_samples':minimum_samples,'maximum_automatic_pair_n':64,'model_n':len(models),'possible_pair_n':len(candidates),'model_id_scope':'CANONICAL_SUPPLIED_CONTEXT_NOT_AUTHENTICATED','models':models,'comparisons':[],
            'independent_samples_established':False,'predictive_skill_established':False,'winner_established':False,'calibration_established':False,'production_approved':False,'trading_authority':False}
    if model_pairs is None:
        if len(candidates)>64:return {**result,'status':'EXPLICIT_PAIR_SELECTION_REQUIRED','selection_mode':'AUTOMATIC'}
        selected=candidates
    else:
        if not isinstance(model_pairs,(list,tuple)) or not 1<=len(model_pairs)<=64:raise ForecastEvidenceRefused('Bounded explicit model pairs required')
        selected=[];selected_ids=set()
        for pair in model_pairs:
            if not isinstance(pair,(list,tuple)) or len(pair)!=2 or any(type(key) is not str or len(key)>4096 or key not in groups for key in pair) or pair[0]==pair[1]:raise ForecastEvidenceRefused('Known distinct paired model identities required')
            key=tuple(sorted(pair))
            if key in selected_ids:raise ForecastEvidenceRefused('Repeated comparison pair')
            selected_ids.add(key);selected.append(tuple(pair))
    data_fields=('forecast_dataset_sha256','forecast_dataset_manifest_sha256','forecast_dataset_id','forecast_dataset_version')
    model_fields=('model_version','lookback','forecast_code_sha256')
    for a,b in selected:
        left,right=groups[a],groups[b];ac,bc=left['cohort'],right['cohort'];am,bm=left['cases'],right['cases'];shared=set(am)&set(bm)
        pair={'a':a,'b':b,'a_forecast_n':len(am),'b_forecast_n':len(bm),'a_resolved_n':sum(r['status']=='RESOLVED' for r in am.values()),'b_resolved_n':sum(r['status']=='RESOLVED' for r in bm.values()),'shared_n':len(shared),'a_only_n':len(set(am)-set(bm)),'b_only_n':len(set(bm)-set(am)),
              'pending_shared_n':0,'outcome_conflict_n':0,'reference_conflict_n':0,'missing_provenance_n':0,'unassessed_shared_n':0,'paired_n':0,'distinct_target_n':0,'a_mae':None,'b_mae':None,'a_rmse':None,'b_rmse':None,'a_minus_b_mae':None,'baseline_mae':None,'a_ratio_to_baseline':None,'b_ratio_to_baseline':None,'a_lower_error_n':0,'b_lower_error_n':0,'tied_error_n':0,'cases':[]}
        reason=None
        if any(ac.get(k)!=bc.get(k) for k in ('asset_class','asset_id','horizon')):reason='INCOMPARABLE_CONTEXT'
        elif any(k not in c or c[k] is None for c in (ac,bc) for k in data_fields):reason='MISSING_FORECAST_DATA_BINDING'
        elif any(ac[k]!=bc[k] for k in data_fields):reason='INCOMPARABLE_FORECAST_DATA'
        elif any(k not in c or c[k] is None for c in (ac,bc) for k in model_fields):reason='MISSING_MODEL_DEFINITION'
        elif _point_definition_equal(ac,bc):reason='SAME_POINT_MODEL_DEFINITION'
        elif all(ac[k]==bc[k] for k in model_fields) and (ac.get('model_configuration_sha256') is None)!=(bc.get('model_configuration_sha256') is None):reason='AMBIGUOUS_CONFIGURATION_BINDING'
        errors_a=[];errors_b=[];baselines=[];targets=set()
        for key in sorted(set(am)|set(bm)):
            x,y=am.get(key),bm.get(key);case={'case_id':key,'a_forecast_sha256':x['forecast_sha256'] if x else None,'b_forecast_sha256':y['forecast_sha256'] if y else None,'a_state':x['status'] if x else None,'b_state':y['status'] if y else None,'a_abs_error':None,'b_abs_error':None,'error_difference':None}
            if x is None:case['status']='B_ONLY'
            elif y is None:case['status']='A_ONLY'
            elif reason is not None:case['status']='UNASSESSED_CONTEXT';pair['unassessed_shared_n']+=1
            elif x['status']!='RESOLVED' or y['status']!='RESOLVED':case['status']='PENDING_SHARED_OUTCOME';pair['pending_shared_n']+=1
            elif x['reference']!=y['reference']:case['status']='REFERENCE_CONFLICT';pair['reference_conflict_n']+=1
            elif any(r.get(k) is None for r in (x,y) for k in ('source_revision','source_available_at','outcome_dataset_sha256','last_reconciled_asof')):case['status']='MISSING_OUTCOME_PROVENANCE';pair['missing_provenance_n']+=1
            elif x['actual']!=y['actual'] or x['source_revision']!=y['source_revision'] or x['outcome_dataset_sha256']!=y['outcome_dataset_sha256'] or _pair_us(x['source_available_at'])!=_pair_us(y['source_available_at']):case['status']='OUTCOME_CONFLICT';pair['outcome_conflict_n']+=1
            else:
                ea,eb=abs(x['forecast_point']-x['actual']),abs(y['forecast_point']-y['actual']);errors_a.append(ea);errors_b.append(eb);baselines.append(abs(x['reference']-x['actual']));targets.add(_pair_us(x['target_at']))
                pair['paired_n']+=1;pair['a_lower_error_n']+=ea<eb;pair['b_lower_error_n']+=eb<ea;pair['tied_error_n']+=ea==eb
                case.update(status='PAIRED',a_abs_error=ea,b_abs_error=eb,error_difference=ea-eb)
            pair['cases'].append(case)
        pair['distinct_target_n']=len(targets)
        if errors_a:
            try:
                mae_a,mae_b,baseline=fmean(errors_a),fmean(errors_b),fmean(baselines)
                values={'a_mae':mae_a,'b_mae':mae_b,'a_rmse':math.sqrt(fmean(e*e for e in errors_a)),'b_rmse':math.sqrt(fmean(e*e for e in errors_b)),'a_minus_b_mae':fmean(x-y for x,y in zip(errors_a,errors_b,strict=True)),'baseline_mae':baseline,'a_ratio_to_baseline':mae_a/baseline if baseline else None,'b_ratio_to_baseline':mae_b/baseline if baseline else None}
                if any(v is not None and not math.isfinite(v) for v in values.values()):raise OverflowError
                pair.update(values);pair['status']='INSUFFICIENT_EVIDENCE' if pair['paired_n']<minimum_samples else 'OVERLAPPING_TARGET_EVIDENCE' if pair['distinct_target_n']<minimum_samples else 'DIAGNOSTIC_ONLY'
            except (OverflowError,ValueError,ZeroDivisionError):pair['status']='UNAVAILABLE_NUMERIC_RANGE'
        else:pair['status']=reason or ('NO_SHARED_CASES' if not shared else 'NO_COMPATIBLE_SHARED_OUTCOMES')
        result['comparisons'].append(pair)
    return {**result,'status':'COMPARISONS_RECORDED' if selected else 'NO_ELIGIBLE_MODEL_PAIRS','selection_mode':'AUTOMATIC' if model_pairs is None else 'EXPLICIT'}


def paired_interval_diagnostics(rows, *, asof, model_pairs=None, minimum_samples=20):
    """Same-case interval comparison; observed coverage is not calibration."""
    source=paired_model_diagnostics(rows,asof=asof,model_pairs=model_pairs,minimum_samples=minimum_samples)
    by_hash={row['forecast_sha256']:row for row in rows};comparisons=[]
    for point in source['comparisons']:
        pair={k:point[k] for k in ('a','b','shared_n','a_only_n','b_only_n','pending_shared_n','outcome_conflict_n','reference_conflict_n','missing_provenance_n','unassessed_shared_n')}
        pair.update(point_paired_n=point['paired_n'],interval_paired_n=0,missing_interval_n=0,level_mismatch_n=0,distinct_target_n=0,
                    a_covered_n=0,b_covered_n=0,a_coverage=None,b_coverage=None,a_mean_width=None,b_mean_width=None,
                    a_mean_interval_score=None,b_mean_interval_score=None,a_minus_b_interval_score=None,nominal_level=None,cases=[])
        scores_a=[];scores_b=[];widths_a=[];widths_b=[];targets=set()
        for case in point['cases']:
            record={k:case[k] for k in ('case_id','a_forecast_sha256','b_forecast_sha256')}
            record.update(status=case['status'],a_interval_score=None,b_interval_score=None,a_covered=None,b_covered=None)
            if case['status']=='PAIRED':
                x,y=(by_hash[case[k]] for k in ('a_forecast_sha256','b_forecast_sha256'));a,b=x.get('interval'),y.get('interval')
                if a is None or b is None:record['status']='MISSING_INTERVAL';pair['missing_interval_n']+=1
                elif a['level']!=b['level']:record['status']='NOMINAL_LEVEL_MISMATCH';pair['level_mismatch_n']+=1
                else:
                    actual=x['actual'];level=a['level'];wa=a['upper']-a['lower'];wb=b['upper']-b['lower']
                    sa=wa+2*(max(a['lower']-actual,0)+max(actual-a['upper'],0))/(1-level)
                    sb=wb+2*(max(b['lower']-actual,0)+max(actual-b['upper'],0))/(1-level)
                    ca=a['lower']<=actual<=a['upper'];cb=b['lower']<=actual<=b['upper']
                    pair['interval_paired_n']+=1;pair['a_covered_n']+=ca;pair['b_covered_n']+=cb;pair['nominal_level']=level
                    scores_a.append(sa);scores_b.append(sb);widths_a.append(wa);widths_b.append(wb);targets.add(_pair_us(x['target_at']))
                    record.update(status='INTERVAL_PAIRED',a_interval_score=sa,b_interval_score=sb,a_covered=ca,b_covered=cb)
            pair['cases'].append(record)
        n=pair['interval_paired_n'];pair['distinct_target_n']=len(targets)
        if n:
            try:
                values={'a_coverage':pair['a_covered_n']/n,'b_coverage':pair['b_covered_n']/n,
                        'a_mean_width':fmean(widths_a),'b_mean_width':fmean(widths_b),
                        'a_mean_interval_score':fmean(scores_a),'b_mean_interval_score':fmean(scores_b),
                        'a_minus_b_interval_score':fmean(a-b for a,b in zip(scores_a,scores_b,strict=True))}
                if any(not math.isfinite(v) for v in values.values()):raise OverflowError
                pair.update(values);pair['status']='INSUFFICIENT_EVIDENCE' if n<minimum_samples else 'OVERLAPPING_TARGET_EVIDENCE' if len(targets)<minimum_samples else 'DIAGNOSTIC_ONLY'
            except (OverflowError,ValueError):pair['status']='UNAVAILABLE_NUMERIC_RANGE'
        else:pair['status']='NO_COMPATIBLE_SHARED_INTERVALS'
        comparisons.append(pair)
    return {'schema':'AFI_PAIRED_INTERVAL_DIAGNOSTICS_V1','asof':source['asof'],'minimum_samples':minimum_samples,
            'status':source['status'],'selection_mode':source['selection_mode'],'model_n':source['model_n'],
            'possible_pair_n':source['possible_pair_n'],'comparisons':comparisons,'boundary_policy':'INCLUSIVE',
            'same_nominal_level_required':True,'independent_samples_established':False,'winner_established':False,
            'calibration_established':False,'coverage_guarantee':False,'production_approved':False,'trading_authority':False}


def paired_probability_diagnostics(rows, *, asof, model_pairs=None, minimum_samples=20):
    """Paired Brier diagnostics for recorded P(price > reference), not skill."""
    source=paired_model_diagnostics(rows,asof=asof,model_pairs=model_pairs,minimum_samples=minimum_samples)
    for row in rows:
        if row.get('probability_up') is not None and not 0<=_number(row['probability_up'])<=1:
            raise ForecastEvidenceRefused('Invalid original paired probability')
    by_hash={row['forecast_sha256']:row for row in rows};comparisons=[]
    for point in source['comparisons']:
        pair={k:point[k] for k in ('a','b','shared_n','a_only_n','b_only_n','pending_shared_n','outcome_conflict_n','reference_conflict_n','missing_provenance_n','unassessed_shared_n')}
        pair.update(point_paired_n=point['paired_n'],probability_paired_n=0,missing_probability_n=0,a_missing_probability_n=0,
                    b_missing_probability_n=0,both_missing_probability_n=0,distinct_target_n=0,actual_up_n=0,flat_outcome_n=0,
                    a_brier=None,b_brier=None,a_minus_b_brier=None,uninformative_baseline_brier=None,
                    a_ratio_to_baseline=None,b_ratio_to_baseline=None,a_lower_brier_n=0,b_lower_brier_n=0,tied_brier_n=0,cases=[])
        scores_a=[];scores_b=[];targets=set()
        for case in point['cases']:
            record={k:case[k] for k in ('case_id','a_forecast_sha256','b_forecast_sha256')}
            record.update(status=case['status'],a_probability_state=None,b_probability_state=None,actual_up=None,a_brier=None,b_brier=None)
            if case['status']=='PAIRED':
                x,y=(by_hash[case[k]] for k in ('a_forecast_sha256','b_forecast_sha256'));a,b=x.get('probability_up'),y.get('probability_up')
                record.update(a_probability_state='UNRECORDED' if 'probability_up' not in x else 'NONE' if a is None else 'RECORDED',
                              b_probability_state='UNRECORDED' if 'probability_up' not in y else 'NONE' if b is None else 'RECORDED')
                if a is None or b is None:
                    record['status']='MISSING_PROBABILITY';pair['missing_probability_n']+=1
                    pair['a_missing_probability_n']+=a is None;pair['b_missing_probability_n']+=b is None;pair['both_missing_probability_n']+=a is None and b is None
                else:
                    actual=int(x['actual']>x['reference']);sa=(a-actual)**2;sb=(b-actual)**2
                    scores_a.append(sa);scores_b.append(sb);targets.add(_pair_us(x['target_at']))
                    pair['probability_paired_n']+=1;pair['actual_up_n']+=actual;pair['flat_outcome_n']+=x['actual']==x['reference']
                    pair['a_lower_brier_n']+=sa<sb;pair['b_lower_brier_n']+=sb<sa;pair['tied_brier_n']+=sa==sb
                    record.update(status='PROBABILITY_PAIRED',actual_up=actual,a_brier=sa,b_brier=sb)
            pair['cases'].append(record)
        n=pair['probability_paired_n'];pair['distinct_target_n']=len(targets)
        if n:
            a,b=fmean(scores_a),fmean(scores_b)
            pair.update(a_brier=a,b_brier=b,a_minus_b_brier=fmean(a-b for a,b in zip(scores_a,scores_b,strict=True)),
                        uninformative_baseline_brier=.25,a_ratio_to_baseline=a/.25,b_ratio_to_baseline=b/.25,
                        status='INSUFFICIENT_EVIDENCE' if n<minimum_samples else 'OVERLAPPING_TARGET_EVIDENCE' if len(targets)<minimum_samples else 'DIAGNOSTIC_ONLY')
        else:pair['status']='NO_COMPATIBLE_SHARED_PROBABILITIES'
        comparisons.append(pair)
    return {'schema':'AFI_PAIRED_PROBABILITY_DIAGNOSTICS_V1','asof':source['asof'],'minimum_samples':minimum_samples,
            'status':source['status'],'selection_mode':source['selection_mode'],'model_n':source['model_n'],
            'possible_pair_n':source['possible_pair_n'],'comparisons':comparisons,'binary_event':'PRICE_STRICTLY_ABOVE_REFERENCE; FLAT_IS_NOT_UP',
            'missing_inputs_not_inferred':True,'independent_samples_established':False,'winner_established':False,
            'calibration_established':False,'predictive_skill_established':False,'production_approved':False,'trading_authority':False}


def reliability_diagnostics(rows, *, minimum_samples=20):
    """Fixed-bin display evidence; partial inputs never become zero probability."""
    if type(minimum_samples) is not int or not 1<=minimum_samples<=10000:
        raise ForecastEvidenceRefused('Bounded reliability sample minimum required')
    interval_diagnostics(rows);groups={};seen=set();cases=set()
    # Validate even pending inputs; they must not become valid after resolution.
    for row in rows:
        source=_pair_hash(row.get('forecast_sha256'))
        if source in seen:raise ForecastEvidenceRefused('Repeated reliability forecast identity')
        seen.add(source)
        if row.get('probability_up') is not None and not 0<=_number(row['probability_up'])<=1:
            raise ForecastEvidenceRefused('Invalid recorded reliability probability')
        interval=row.get('interval');binding='UNRECORDED' if 'interval' not in row else 'NONE' if interval is None else 'FLOAT64:'+struct.pack('>d',interval['level']).hex()
        cohort={**_cohort(row),'interval_binding':binding}
        key=json.dumps(cohort,sort_keys=True,separators=(',',':'),allow_nan=False)
        case=(key,_pair_us(row['issued_at']),_pair_us(row['target_at']))
        if case in cases or _report_time(row['target_at'])<=_report_time(row['issued_at']):raise ForecastEvidenceRefused('Repeated or invalid reliability forecast case')
        cases.add(case)
        groups.setdefault(key,{'cohort':cohort,'rows':[]})['rows'].append(row)
    cohorts=[]
    for _,group in sorted(groups.items()):
        resolved=[r for r in group['rows'] if r['status']=='RESOLVED']
        recorded=[r for r in resolved if r.get('probability_up') is not None]
        metrics=probability_reliability([(r['probability_up'],int(r['actual']>r['reference'])) for r in recorded],minimum_samples)
        populated={b['bin']:b for b in metrics['calibration_bins']};bins=[]
        for index in range(10):
            sample=[r for r in recorded if min(int(r['probability_up']*10),9)==index]
            targets={_pair_us(r['target_at']) for r in sample};n=len(sample)
            item=populated.get(index,{'bin':index,'n':0,'mean_probability':None,'observed_up_fraction':None})
            bins.append({**item,'lower':index/10,'upper':(index+1)/10,'upper_inclusive':index==9,'distinct_target_n':len(targets),
                         'status':'EMPTY' if not n else 'INSUFFICIENT_EVIDENCE' if n<minimum_samples else 'OVERLAPPING_TARGET_EVIDENCE' if len(targets)<minimum_samples else 'DIAGNOSTIC_ONLY'})
        n=metrics['probability_n'];distinct=len({_pair_us(r['target_at']) for r in recorded});unknown=sum('probability_up' not in r for r in resolved)
        cohorts.append({**metrics,'calibration_bins':bins,'cohort':group['cohort'],'forecast_n':len(group['rows']),
                        'resolved_n':len(resolved),'pending_n':len(group['rows'])-len(resolved),'distinct_target_n':distinct,
                        'unrecorded_probability_n':unknown,'no_probability_n':sum('probability_up' in r and r['probability_up'] is None for r in resolved),
                        'input_status':'PARTIAL_LEGACY_INPUTS' if unknown else 'RECORDED_INPUTS',
                        'status':'NO_RECORDED_PROBABILITIES' if not n else 'PARTIAL_LEGACY_INPUTS' if unknown else 'INSUFFICIENT_EVIDENCE' if n<minimum_samples else 'OVERLAPPING_TARGET_EVIDENCE' if distinct<minimum_samples else 'DIAGNOSTIC_ONLY'})
    return {'schema':'AFI_FIXED_BIN_RELIABILITY_V1','minimum_samples':minimum_samples,'fixed_bin_n':10,
            'denominator_scope':'RESOLVED_RECORDED_PROBABILITIES_ONLY','cohorts':cohorts,
            'empty_bins_not_zero_error':True,'independent_samples_established':False,'calibration_established':False,
            'predictive_skill_established':False,'production_approved':False,'trading_authority':False}


def build_accountability_report(entries, *, evidence_asof):
    if (not isinstance(entries,(list,tuple)) or not 1<=len(entries)<=64
            or any(type(e) is not ForecastHistory for e in entries)):
        raise ForecastEvidenceRefused('Bounded exact forecast histories required')
    asof = _time(evidence_asof)
    rows,forecasts,outcomes,seen = [],[],[],set()
    for entry in tuple(entries):
        checked = verify_outcome_history(entry.forecast_path,entry.forecast_review,evidence_asof=asof,
                                         history=entry.history,expected_head=entry.expected_head,source_review=entry.source_review)
        data,records = checked['forecast'],checked['records']
        forecast = _forecast(data)
        if data['forecast_sha256'] in seen:
            raise ForecastEvidenceRefused('Repeated report forecast would inflate sample count')
        seen.add(data['forecast_sha256']);forecasts.append(forecast)
        manifest=_json(entry.forecast_review.manifest_bytes)
        asset=next((item for item in manifest['assets'] if item['asset_id']==forecast.asset_id),None)
        if asset is None:
            raise ForecastEvidenceRefused('Forecast input asset is absent from its reviewed dataset')
        selected=select_asof(entry.forecast_review.observations,asset_id=forecast.asset_id,
                             asset_class=forecast.asset_class,cutoff=forecast.issued_at,
                             max_age=timedelta(seconds=asset['freshness_seconds']))
        input_record=selected['record']
        if (input_record is None or input_record.value!=forecast.reference_price
                or input_record.observed_at!=forecast.input_observed_at
                or input_record.available_at!=forecast.input_available_at):
            raise ForecastEvidenceRefused('Forecast accountability input is not the latest issue-time dataset record')
        source_records=[record for record in _json(entry.forecast_review.payload_bytes)['records']
                        if record['record_id']==input_record.record_id
                        and record['revision']==input_record.revision
                        and record['source_id']==input_record.source_id]
        if len(source_records)!=1:
            raise ForecastEvidenceRefused('Forecast input source record is missing or ambiguous')
        input_source=source_records[0]
        input_provenance=({'input_observed_at':input_record.observed_at.isoformat(),
                           'input_available_at':input_record.available_at.isoformat(),
                           'input_source_id':input_record.source_id,
                           'input_source_revision':input_record.revision,
                           'input_source_sha256':input_source['source_sha256']}
                          if 'source_sha256' in input_source else {})
        latest = records[-1] if records else None
        row = latest['observation'] if latest else None
        if row is not None:
            outcomes.append(Outcome(forecast.forecast_id,forecast.asset_id,forecast.asset_class,forecast.target_at,
                                    datetime.fromisoformat(row['observed_at']),datetime.fromisoformat(row['available_at']),
                                    row['value'],row['source_id'],row['revision'],'SYNTHETIC'))
        rows.append({'asset_id':forecast.asset_id,'asset_class':forecast.asset_class,'model':forecast.model_id,
                     'model_version':forecast.model_version,'lookback':data['model']['lookback'],
                     'probability_up':forecast.probability_up,'score_cohort':{key:getattr(forecast,key) for key in _SCORE_FIELDS_V2 if key!='model_configuration_sha256' or forecast.model_configuration_sha256 is not None},
                     **({'model_configuration_sha256':forecast.model_configuration_sha256} if forecast.model_configuration_sha256 is not None else {}),
                     'horizon':forecast.horizon,'issued_at':forecast.issued_at.isoformat(),'target_at':forecast.target_at.isoformat(),
                     **input_provenance,
                     'interval':None if forecast.interval_level is None else {'lower':forecast.lower,'upper':forecast.upper,'level':forecast.interval_level},
                     'forecast_point':forecast.point,'reference':forecast.reference_price,'actual':row['value'] if row else None,
                     'status':latest['status'] if latest else 'FORECAST_ONLY','latest_event':latest['event'] if latest else None,
                     'last_reconciled_asof':latest['outcome_asof'] if latest else None,
                     'source_revision':row['revision'] if row else None,'source_available_at':row['available_at'] if row else None,
                     'correction_n':sum(r['event']=='CORRECTION' for r in records),'history_n':len(records),
                     'expected_head':entry.expected_head,'forecast_sha256':data['forecast_sha256'],
                     'forecast_artifact_sha256':data['artifact_sha256'],'forecast_dataset_sha256':entry.forecast_review.content_sha256,
                     'outcome_dataset_sha256':latest['outcome_dataset_sha256'] if latest else None,
                     'release_source_sha256':data.get('release_source_sha256'),'forecast_code_sha256':forecast.code_sha256,
                     **({'forecast_dataset_manifest_sha256':forecast.dataset_manifest_sha256,'forecast_dataset_id':forecast.dataset_id,'forecast_dataset_version':forecast.dataset_version} if forecast.dataset_manifest_sha256 is not None else {}),
                     'reconciliation_freshness':'NOT_INDEPENDENTLY_ESTABLISHED'})
    score = score_forecasts(forecasts,outcomes,asof=asof)
    result = {'paired_probability_contract':'MATCHED_PROBABILITY_V1','paired_probability_diagnostics':paired_probability_diagnostics(rows,asof=asof),'paired_interval_contract':'MATCHED_INTERVAL_V1','paired_interval_diagnostics':paired_interval_diagnostics(rows,asof=asof),'paired_model_contract':'MATCHED_CASE_V1','paired_model_diagnostics':paired_model_diagnostics(rows,asof=asof),'score_rows_contract':'ROW_BOUND_SCORE_V2','diagnostic_partition':'DATASET_RELEASE_V1','schema':'AFI_ACCOUNTABILITY_REPORT_V1','evidence_class':'SYNTHETIC','asof':asof.isoformat(),
              'rows':sorted(rows,key=lambda r:(r['asset_class'],r['asset_id'],r['target_at'],r['model'],r['forecast_sha256'])),
              'score':score,'directional_diagnostics':directional_diagnostics(rows),'interval_diagnostics':interval_diagnostics(rows),'forecast_n':len(rows),'correction_n':sum(r['correction_n'] for r in rows),
              'history_completeness_verified':False,'live_feed_freshness_verified':False,'calibration_established':False,
              'production_approved':False,'trading_authority':False,'recovery_authorized':False}
    return {**result,'report_sha256':fingerprint(result)}


def browser_export(report):
    # Reuse report consistency/safety validation before exposing a client bundle.
    render_accountability_report(report)
    text=json.dumps(report,sort_keys=True,separators=(",",":"),allow_nan=False)
    envelope={"schema":"AFI_BROWSER_REPORT_V1","report_json":text,
              "payload_sha256":hashlib.sha256(text.encode("utf-8")).hexdigest()}
    raw=json.dumps(envelope,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n"
    if len(raw.encode("utf-8"))>1_000_000:
        raise ForecastEvidenceRefused("Browser report export exceeds viewer limit")
    return raw



def _deny_unsupported_claims(report):
    flags={'production_approved','trading_authority','recovery_authorized','calibration_established','live_feed_freshness_verified','history_completeness_verified','dataset_authenticated','live_capital_allowed','automatic_real_money_execution','predictive_skill_established','coverage_guarantee','independent_samples_established','winner_established'}
    stack=[(report,0)];visited=0
    while stack:
        value,depth=stack.pop();visited+=1
        if depth>20 or visited>100000:raise ForecastEvidenceRefused('Bounded report structure required')
        if type(value) is dict:
            for key,child in value.items():
                if key in flags and child is not False:raise ForecastEvidenceRefused('Unsupported nested report authority or acceptance claim')
                stack.append((child,depth+1))
        elif type(value) is list:
            stack.extend((child,depth+1) for child in value)

def _render_case_plots(rows):
    """Derived scriptless cases; no cross-cohort path or missing-value inference."""
    if type(rows) is not list or len(rows)>64:
        raise ForecastEvidenceRefused('Bounded plot rows required')
    interval_diagnostics(rows)
    groups={};seen=set();unbound=0
    required=('model_version','model_configuration_sha256','forecast_dataset_sha256',
              'forecast_dataset_manifest_sha256','forecast_dataset_id',
              'forecast_dataset_version','forecast_code_sha256')
    for row in rows:
        identity=_pair_hash(row['forecast_sha256'])
        if identity in seen:raise ForecastEvidenceRefused('Duplicate plotted forecast')
        seen.add(identity);_report_time(row['target_at'])
        cohort=_cohort(row)
        if any(cohort.get(k) is None for k in required):
            unbound+=1;continue
        cohort.update({k:row.get(k) for k in ('input_source_id','input_source_revision','input_source_sha256')})
        cohort.update(interval_level=(row.get('interval') or {}).get('level'),interval_recorded='interval' in row)
        key=json.dumps(cohort,sort_keys=True,separators=(',',':'),allow_nan=False)
        groups.setdefault(key,[]).append(row)
    def text(value):return escape(str(value),quote=True) if value is not None else 'Unavailable'
    parts=['<section class="panel"><h2>Forecast cases and original uncertainty</h2><p>Synthetic evidence only. Separate recorded cohorts; open one to inspect discrete cases. Blue circles are forecasts, orange squares observed outcomes and whiskers original intervals. No connecting price path, calibrated coverage or independent-sample claim. Pending outcomes have no observed marker.</p>',
           '<p>'+str(unbound)+' cases lack complete recorded provenance and are not plotted.</p>']
    for key,sample in groups.items():
        sample=sorted(sample,key=lambda r:(_report_time(r['target_at']),r['forecast_sha256']))
        values=[value for r in sample for value in [r['forecast_point'],r['actual'],
                (r.get('interval') or {}).get('lower'),(r.get('interval') or {}).get('upper')] if value is not None]
        low,high=min(values),max(values)
        def x(value, low=low, high=high):return 260+620*(.5 if high==low else (value-low)/(high-low))
        first=sample[0]
        parts.append('<details><summary>'+text(first['asset_id'])+' / '+text(first['model'])+' / '+text(first['horizon'])+' / '+str(len(sample))+' cases</summary><p>Exact recorded cohort (not authenticated): '+text(key)+'</p><div class="scroll" tabindex="0" aria-label="Forecast case plot and exact values"><svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Discrete forecast and observed outcome cases with original intervals" width="900" viewBox="0 0 900 '+str(80+42*len(sample))+'"><title>Synthetic forecast cases</title><desc>Target then identity order. Pending observations have no orange square. Exact values and provenance follow in the table.</desc><text x="260" y="20" fill="currentColor">'+text(low)+'</text><text x="880" y="20" text-anchor="end" fill="currentColor">'+text(high)+'</text>')
        table=[]
        for index,row in enumerate(sample,1):
            y=52+42*(index-1);interval=row.get('interval')
            parts.append('<g><title>'+text(row['forecast_sha256'])+'</title><text x="8" y="'+str(y+5)+'" fill="currentColor">'+str(index)+'. '+text(row['status'])+'</text>')
            if interval:
                parts.append(f'<line x1="{x(interval["lower"])}" x2="{x(interval["upper"])}" y1="{y}" y2="{y}" stroke="currentColor" stroke-width="2"/>')
                for value in (interval['lower'],interval['upper']):
                    parts.append(f'<line x1="{x(value)}" x2="{x(value)}" y1="{y-8}" y2="{y+8}" stroke="currentColor"/>')
            parts.append(f'<circle cx="{x(row["forecast_point"])}" cy="{y}" r="6" fill="#4aa8ff" stroke="currentColor"/>')
            if row['actual'] is not None:
                parts.append(f'<rect x="{x(row["actual"])-4}" y="{y-4}" width="8" height="8" fill="#ffad4a" stroke="currentColor"/>')
            parts.append('</g>')
            fields=[index,row['forecast_sha256'],row['target_at'],row['forecast_point'],row['actual'],row['status'],
                    None if interval is None else f'{interval["lower"]} to {interval["upper"]} (level {interval["level"]})',
                    row.get('outcome_dataset_sha256'),row.get('source_revision'),row['correction_n']]
            table.append('<tr>'+''.join('<td>'+text(v)+'</td>' for v in fields)+'</tr>')
        headers=['Case','Forecast identity','Target','Forecast','Observed','Outcome state','Original interval','Outcome dataset','Outcome revision','Corrections']
        parts.append('</svg><table><caption>Exact plotted cases; corrections remain one original forecast.</caption><thead><tr>'+''.join('<th scope="col">'+h+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join(table)+'</tbody></table></div></details>')
    if not rows:parts.append('<p>No visible cases.</p>')
    return ''.join(parts)+'</section>'


def render_accountability_report(report):
    """Render only a consistent report; all values escaped, no scripts/requests."""
    if type(report) is not dict or report.get('schema')!='AFI_ACCOUNTABILITY_REPORT_V1':
        raise ForecastEvidenceRefused('Exact accountability report required')
    _deny_unsupported_claims(report)
    body={k:v for k,v in report.items() if k!='report_sha256'}
    if (fingerprint(body)!=report.get('report_sha256') or report.get('production_approved') is not False
            or report.get('evidence_class')!='SYNTHETIC'
            or any(report.get(k) is not False for k in ('trading_authority','recovery_authorized','history_completeness_verified','live_feed_freshness_verified','calibration_established'))
            or ('diagnostic_partition' in report and report['diagnostic_partition']!='DATASET_RELEASE_V1')
            or report.get('directional_diagnostics')!=directional_diagnostics(report.get('rows'),bind_provenance=report.get('diagnostic_partition')=='DATASET_RELEASE_V1')
):
        raise ForecastEvidenceRefused('Substituted accountability report')
    _check_report_score(report)
    if (('paired_probability_contract' in report or 'paired_probability_diagnostics' in report)
            and (report.get('paired_probability_contract')!='MATCHED_PROBABILITY_V1' or not _same_score(paired_probability_diagnostics(report['rows'],asof=_report_time(report['asof'])),report.get('paired_probability_diagnostics')))):
        raise ForecastEvidenceRefused('Substituted matched probability diagnostics')
    if (('paired_interval_contract' in report or 'paired_interval_diagnostics' in report)
            and (report.get('paired_interval_contract')!='MATCHED_INTERVAL_V1' or not _same_score(paired_interval_diagnostics(report['rows'],asof=_report_time(report['asof'])),report.get('paired_interval_diagnostics')))):
        raise ForecastEvidenceRefused('Substituted matched interval diagnostics')
    if (('paired_model_contract' in report or 'paired_model_diagnostics' in report)
            and (report.get('paired_model_contract')!='MATCHED_CASE_V1' or not _same_score(paired_model_diagnostics(report['rows'],asof=_report_time(report['asof'])),report.get('paired_model_diagnostics')))):
        raise ForecastEvidenceRefused('Substituted matched-case model diagnostics')
    legacy_intervals='interval_diagnostics' not in report
    if legacy_intervals:
        if any('interval' in row for row in report['rows']):
            raise ForecastEvidenceRefused('Original interval rows require interval accountability')
        checked_intervals={'cohorts':[]}
    else:
        checked_intervals=interval_diagnostics(report['rows'],bind_provenance=report.get('diagnostic_partition')=='DATASET_RELEASE_V1')
        if report['interval_diagnostics']!=checked_intervals:
            raise ForecastEvidenceRefused('Substituted interval accountability')
    # Legacy serialized aggregates remain verifiable; presentation derives safe partitions.
    if not legacy_intervals:
        checked_intervals=interval_diagnostics(report['rows'])
    display_directional=directional_diagnostics(report['rows'])
    def text(x):return escape(str(x),quote=True) if x is not None else 'Unavailable'
    rows=[]
    for row in report['rows']:
        rows.append('<tr>'+''.join('<td>'+text(v)+'</td>' for v in [row['asset_id'],row['model'],row['horizon'],
                     row['target_at'],row['forecast_point'],row.get('input_observed_at'),
                     row.get('input_available_at'),row.get('input_source_id'),row.get('input_source_revision'),
                     row.get('input_source_sha256'),
                     row['actual'],row['status'],row['source_revision'],row['last_reconciled_asof'],
                     row['correction_n'],row['history_n']])+'</tr>')
    heads=''.join('<li>'+text(r['asset_id'])+' / forecast '+text(r['forecast_sha256'])+' / expected head '+text(r['expected_head'])+'</li>' for r in report['rows'])
    diagnostics=[]
    for cohort in display_directional['cohorts']:
        c=cohort['cohort']
        diagnostics.append('<tr>'+''.join('<td>'+text(v)+'</td>' for v in [c['asset_id'],c['model'],c.get('model_version','LEGACY_UNBOUND'),c.get('lookback'),c.get('model_configuration_sha256','LEGACY_UNBOUND'),c.get('forecast_dataset_version','LEGACY_UNBOUND'),c.get('forecast_dataset_manifest_sha256','LEGACY_UNBOUND'),c.get('forecast_code_sha256','LEGACY_UNBOUND'),c.get('forecast_dataset_sha256','LEGACY_UNBOUND'),c.get('release_source_sha256') or 'UNBOUND',c['horizon'],cohort['resolved_n'],cohort['pending_n'],cohort['up']['true_positive_n'],cohort['up']['false_positive_n'],cohort['up']['false_negative_n'],cohort['up']['precision'],cohort['up']['recall']])+'</tr>')
    diagnostic_html='<section class="panel"><h2>Directional outcome diagnostics</h2><p>Descriptive synthetic counts, separated by asset, model, horizon, dataset and release commitment. Legacy unbound evidence cannot establish provenance. Flat outcomes are separate from UP and DOWN; pending outcomes are excluded. An UP false positive is an UP forecast followed by FLAT or DOWN, not a failed trade. Zero denominators are unavailable. No market skill or profitability is established.</p><div class="scroll" tabindex="0"><table><caption>UP prediction counts; the JSON report retains the full three-direction matrix and DOWN counts.</caption><thead><tr>'+''.join('<th scope="col">'+text(h)+'</th>' for h in ['Asset','Model','Model version','Lookback','Configuration binding','Dataset version','Manifest commitment','Model code commitment','Forecast dataset commitment','Release source commitment','Horizon','Resolved','Pending','True UP','False UP','Missed UP','UP precision','UP recall'])+'</tr></thead><tbody>'+''.join(diagnostics)+'</tbody></table></div></section>'
    signed_rows=[]
    for c in signed_error_diagnostics(report['rows'])['cohorts']:
        k=c['cohort']
        values=[k['asset_id'],k['model'],k.get('model_version','LEGACY_UNBOUND'),k.get('lookback'),k.get('model_configuration_sha256','LEGACY_UNBOUND'),k.get('forecast_dataset_version','LEGACY_UNBOUND'),k.get('forecast_dataset_manifest_sha256','LEGACY_UNBOUND'),k.get('forecast_code_sha256','LEGACY_UNBOUND'),k.get('forecast_dataset_sha256','LEGACY_UNBOUND'),k.get('release_source_sha256') or 'UNBOUND',k['horizon'],c['resolved_n'],c['pending_n'],c['over_n'],c['under_n'],c['equal_n'],c['mean_signed_error'],c['status']]
        signed_rows.append('<tr>'+''.join('<td>'+text(v)+'</td>' for v in values)+'</tr>')
    signed_headers=['Asset','Model','Model version','Lookback','Configuration binding','Dataset version','Manifest commitment','Model code commitment','Forecast dataset commitment','Release source commitment','Horizon','Resolved','Pending','Overprediction','Underprediction','Exact','Mean signed error','Evidence']
    signed_html='<section class="panel"><h2>Signed price error diagnostics</h2><p>Forecast minus observed price. Positive is overprediction, negative is underprediction; this is not directional accuracy or PAPER P&amp;L. Pending outcomes do not enter the mean. Opposite errors may cancel; inspect counts alongside the mean. Separate asset/model/data cohorts and repeated samples do not establish independent skill.</p><div class="scroll" tabindex="0"><table><caption>Descriptive price-unit bias. Unsupported numeric ranges are unavailable.</caption><thead><tr>'+''.join('<th scope="col">'+text(h)+'</th>' for h in signed_headers)+'</tr></thead><tbody>'+''.join(signed_rows)+'</tbody></table></div></section>'
    interval_rows=[]
    for c in interval_target_support(report['rows'])['cohorts']:
        key=c['cohort']
        interval_rows.append('<tr>'+''.join('<td>'+text(v)+'</td>' for v in [key['asset_id'],key['model'],key.get('model_version','LEGACY_UNBOUND'),key.get('lookback'),key.get('model_configuration_sha256','LEGACY_UNBOUND'),key.get('forecast_dataset_version','LEGACY_UNBOUND'),key.get('forecast_dataset_manifest_sha256','LEGACY_UNBOUND'),key.get('forecast_code_sha256','LEGACY_UNBOUND'),key.get('forecast_dataset_sha256','LEGACY_UNBOUND'),key.get('release_source_sha256') or 'UNBOUND',key['horizon'],key['level'],c['resolved_n'],c['pending_n'],c['coverage'],c['mean_width'],c['mean_interval_score'],c['status'],c['distinct_recorded_target_n'],c['missing_target_n'],c['repeated_target_n'],c['target_support_status']])+'</tr>')
    interval_html='<section class="panel"><h2>Interval outcome diagnostics</h2><p>Inclusive interval boundaries; exact-target resolved outcomes only. Assets, models, horizons, nominal levels, dataset and release commitments are separate. Legacy unbound evidence cannot establish provenance. Pending observations do not count as misses. Fewer than20 resolved outcomes remains INSUFFICIENT_EVIDENCE. Synthetic coverage is not calibrated market coverage or a guarantee. Repeated target dates do not provide independent samples; missing target clocks remain unknown. Distinct recorded targets alone do not establish independence.</p><div class="scroll" tabindex="0"><table><caption>Interval score: width plus scaled miss penalties; smaller is better within the same units and cohort only.</caption><thead><tr>'+''.join('<th scope="col">'+text(h)+'</th>' for h in ['Asset','Model','Model version','Lookback','Configuration binding','Dataset version','Manifest commitment','Model code commitment','Forecast dataset commitment','Release source commitment','Horizon','Nominal level','Resolved','Pending','Observed coverage','Mean width','Mean interval score','Evidence','Distinct recorded targets','Missing target clocks','Repeated targets','Target support'])+'</tr></thead><tbody>'+''.join(interval_rows)+'</tbody></table></div></section>'
    if legacy_intervals:
        interval_html='<section class="panel"><h2>Interval evidence unavailable</h2><p>Legacy report did not record original intervals. No interval coverage or score is inferred.</p></section>'
    score_note=('Original score inputs reconciled with the supplied rows; no independent source truth or skill established.' if report.get('score_rows_contract') in ('ROW_BOUND_SCORE_V1','ROW_BOUND_SCORE_V2') else 'Legacy score inputs are incomplete; available fields only were checked. Missing probability or interval inputs are not inferred.')
    compared=paired_model_diagnostics(report['rows'],asof=_report_time(report['asof']))
    models={m['id']:m['cohort'] for m in compared['models']};pair_rows=[]
    for item in compared['comparisons']:
        a,b=models[item['a']],models[item['b']]
        values=[a['asset_id'],a['horizon'],a['model']+' / window '+str(a.get('lookback','unknown')),b['model']+' / window '+str(b.get('lookback','unknown')),item['paired_n'],item['distinct_target_n'],item['a_only_n'],item['b_only_n'],item['pending_shared_n'],item['outcome_conflict_n']+item['reference_conflict_n'],item['missing_provenance_n'],item['unassessed_shared_n'],item['a_mae'],item['b_mae'],item['a_minus_b_mae'],item['status']]
        pair_rows.append('<tr>'+''.join('<td>'+text(v)+'</td>' for v in values)+'</tr>')
    paired_html='<section class="panel"><h2>Matched-case model comparisons</h2><p>'+text(compared['status'])+'. Exact shared UTC cases and matching outcome vintages only. No winner or independent skill is established. Negative A-minus-B error means smaller observed A errors only.</p><div class="scroll" tabindex="0"><table><caption>Unmatched and pending cases are not zero-error observations. Distinct target counts expose repeated-target samples.</caption><thead><tr>'+''.join('<th scope="col">'+text(h)+'</th>' for h in ['Asset','Horizon','Model A','Model B','Paired','Distinct targets','A only','B only','Pending','Conflicts','Missing provenance','Unassessed','A MAE','B MAE','A minus B MAE','Evidence'])+'</tr></thead><tbody>'+''.join(pair_rows)+'</tbody></table></div></section>'
    paired_intervals=paired_interval_diagnostics(report['rows'],asof=_report_time(report['asof']));paired_interval_rows=[]
    for item in paired_intervals['comparisons']:
        a,b=models[item['a']],models[item['b']]
        values=[a['asset_id'],a['horizon'],a['model']+' / window '+str(a.get('lookback','unknown')),b['model']+' / window '+str(b.get('lookback','unknown')),item['point_paired_n'],item['interval_paired_n'],item['distinct_target_n'],item['missing_interval_n'],item['level_mismatch_n'],item['nominal_level'],item['a_coverage'],item['b_coverage'],item['a_mean_width'],item['b_mean_width'],item['a_mean_interval_score'],item['b_mean_interval_score'],item['a_minus_b_interval_score'],item['status']]
        paired_interval_rows.append('<tr>'+''.join('<td>'+text(v)+'</td>' for v in values)+'</tr>')
    paired_interval_html='<section class="panel"><h2>Matched-case interval comparisons</h2><p>Shared compatible outcomes and identical nominal levels only. Missing intervals and level mismatches are not coverage misses. Inclusive boundaries. Observed coverage is not calibrated coverage or a guarantee.</p><div class="scroll" tabindex="0"><table><caption>Pending and conflicting cases remain in the model comparison above. Lower interval scores balance width and scaled miss penalties; no winner is established.</caption><thead><tr>'+''.join('<th scope="col">'+text(h)+'</th>' for h in ['Asset','Horizon','Model A','Model B','Point paired','Interval paired','Distinct targets','Missing interval','Level mismatch','Nominal level','A coverage','B coverage','A width','B width','A interval score','B interval score','A minus B score','Evidence'])+'</tr></thead><tbody>'+''.join(paired_interval_rows)+'</tbody></table></div></section>'
    paired_probabilities=paired_probability_diagnostics(report['rows'],asof=_report_time(report['asof']));paired_probability_rows=[]
    for item in paired_probabilities['comparisons']:
        a,b=models[item['a']],models[item['b']]
        values=[a['asset_id'],a['horizon'],a['model']+' / window '+str(a.get('lookback','unknown')),b['model']+' / window '+str(b.get('lookback','unknown')),item['point_paired_n'],item['probability_paired_n'],item['distinct_target_n'],item['missing_probability_n'],item['a_missing_probability_n'],item['b_missing_probability_n'],item['actual_up_n'],item['flat_outcome_n'],item['a_brier'],item['b_brier'],item['a_minus_b_brier'],item['uninformative_baseline_brier'],item['a_ratio_to_baseline'],item['b_ratio_to_baseline'],item['status']]
        paired_probability_rows.append('<tr>'+''.join('<td>'+text(v)+'</td>' for v in values)+'</tr>')
    paired_probability_html='<section class="panel"><h2>Matched-case probability comparisons</h2><p>Recorded probabilities and shared compatible outcomes only. Price strictly above reference is UP; flat is not UP. Missing probability is not zero. No calibration, skill or winner is established.</p><div class="scroll" tabindex="0"><table><caption>Pending and conflicting outcomes remain above. Uninformative P(UP)=0.5 has Brier error0.25. Original JSON retains each case and input state.</caption><thead><tr>'+''.join('<th scope="col">'+text(h)+'</th>' for h in ['Asset','Horizon','Model A','Model B','Point paired','Probability paired','Distinct targets','Missing probability','A missing','B missing','Actual UP','Flat outcomes','A Brier','B Brier','A minus B Brier','Uninformative baseline','A baseline ratio','B baseline ratio','Evidence'])+'</tr></thead><tbody>'+''.join(paired_probability_rows)+'</tbody></table></div></section>'
    reliability=reliability_diagnostics(report['rows']);reliability_rows=[]
    for c in reliability['cohorts']:
        k=c['cohort']
        for b in c['calibration_bins']:
            values=[k['asset_id'],k['model'],k.get('lookback'),k['horizon'],c['probability_n'],c['unrecorded_probability_n'],c['no_probability_n'],c['distinct_target_n'],b['lower'],b['upper'],b['upper_inclusive'],b['n'],b['distinct_target_n'],b['mean_probability'],b['observed_up_fraction'],c['expected_calibration_error'],b['status'],c['status'],k.get('model_configuration_sha256','LEGACY_UNBOUND'),k.get('forecast_dataset_manifest_sha256','LEGACY_UNBOUND'),k['interval_binding']]
            reliability_rows.append('<tr>'+''.join('<td>'+text(v)+'</td>' for v in values)+'</tr>')
    reliability_html='<section class="panel"><h2>Probability reliability evidence</h2><p>Ten fixed bins; lower bounds inclusive, upper bounds exclusive except probability1. Empty bins are unavailable, not zero error. Only resolved recorded probabilities enter the weighted bin gap. Missing and partial legacy inputs remain explicit. Repeated targets and sparse bins establish no calibrated coverage, independence or skill.</p><div class="scroll" tabindex="0"><table><caption>Original-row diagnostics. Model, data, configuration and nominal interval contexts remain separate.</caption><thead><tr>'+''.join('<th scope="col">'+text(h)+'</th>' for h in ['Asset','Model','Lookback','Horizon','Recorded probabilities','Unrecorded inputs','No probability forecast','Distinct targets','Bin lower','Bin upper','Upper inclusive','Bin count','Bin distinct targets','Mean probability','Observed UP fraction','Weighted bin gap','Bin evidence','Cohort evidence','Configuration','Manifest','Interval binding'])+'</tr></thead><tbody>'+''.join(reliability_rows)+'</tbody></table></div></section>'
    headers=['Asset','Model','Horizon','Target (UTC)','Forecast','Input observed (UTC)','Input available (UTC)','Input source','Input source revision','Input source hash','Observed','Outcome state','Revision','Last reconciled (UTC)','Corrections','History records']
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Atlas forecast accountability</title><style>
:root{color-scheme:dark}body{margin:0;background:#09111c;color:#e8f1fc;font:16px/1.5 system-ui,sans-serif}main{max-width:1500px;margin:auto;padding:clamp(20px,4vw,60px)}
h1{font-size:clamp(28px,4vw,44px)}.notice{border:1px solid #e38891;background:#2c1720;padding:20px;border-radius:12px}.panel{margin-top:28px;padding:22px;background:#122034;border:1px solid #405168;border-radius:12px}.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%}caption{text-align:left;color:#b9cddd;padding-bottom:16px}th,td{padding:12px;text-align:left;border-bottom:1px solid #405168;white-space:nowrap}th{color:#8ee8df}ul{overflow-wrap:anywhere}
</style></head><body><main><p>PROJECT ATLAS / EVIDENCE ENGINE</p><h1>Forecast accountability</h1>
<section class="notice" aria-label="Evidence limitations"><strong>Production NO-GO - synthetic evidence only</strong><p>Corrections revise evidence; they do not create extra forecast samples. No market skill, calibrated coverage, live freshness or trading authority is established.</p><p>'''+text(score_note)+'''</p></section>
<section class="panel"><h2>Latest supplied evidence</h2><p>Report as of '''+text(report['asof'])+'''</p><p>Forecasts: '''+text(report['forecast_n'])+''' / Resolved: '''+text(report['score']['scored_n'])+''' / Pending: '''+text(report['score']['pending_n'])+''' / Corrections: '''+text(report['correction_n'])+'''</p><div class="scroll" tabindex="0" aria-label="Scrollable accountability table"><table><caption>Snapshot of explicitly supplied histories. Last reconciliation is distinct from provider freshness; prices/errors are not PAPER P&amp;L.</caption><thead><tr>'''+''.join('<th scope="col">'+text(h)+'</th>' for h in headers)+'''</tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></div></section><section class="panel"><h2>Traceable identities</h2><ul>'''+heads+'''</ul><p>Expected heads verify the supplied subset, not independent whole-history completeness, external-writer exclusion or recovery authority.</p></section>'''+_render_case_plots(report['rows'])+diagnostic_html+signed_html+interval_html+paired_html+paired_interval_html+paired_probability_html+reliability_html+'''</main></body></html>'''


class BundleReader:
    def __init__(self,root):
        self.root=Path(root).absolute();self.budget=50_000_000
        if not self.root.is_dir() or any(p.is_symlink() or p.is_junction() for p in (self.root,*self.root.parents)):
            raise ForecastEvidenceRefused('Existing unlinked bundle root required')

    def path(self,name,*,directory=False):
        if type(name) is not str or not name or len(name)>512 or '\\' in name or ':' in name:
            raise ForecastEvidenceRefused('Exact portable relative bundle path required')
        relative=PurePosixPath(name)
        if relative.is_absolute() or any(p in ('..','.') for p in relative.parts) or relative.as_posix()!=name:
            raise ForecastEvidenceRefused('Bundle path escape or ambiguity refused')
        path=self.root.joinpath(*relative.parts)
        if any(p.is_symlink() or p.is_junction() for p in (path,*path.parents)):
            raise ForecastEvidenceRefused('Linked bundle path refused')
        if directory and not path.is_dir():
            raise ForecastEvidenceRefused('Bundle source directory unavailable')
        return path

    def read(self,name):
        raw=_read(self.path(name));self.budget-=len(raw)
        if self.budget<0:
            raise ForecastEvidenceRefused('Bundle read budget exhausted')
        return raw

    def dataset(self,spec,asof):
        return review_dataset(self.read(spec['dataset_manifest']),self.read(spec['dataset_records']),asof=asof)

    def source(self,spec):
        if 'source_archive' in spec:
            from app.backtest.forecast_source import review_source_archive
            return None if spec['source_archive'] is None else review_source_archive(self.read(spec['source_archive']))
        if (spec['source_manifest'] is None)!=(spec['source_root'] is None):
            raise ForecastEvidenceRefused('Incomplete bundle source binding')
        if spec['source_manifest'] is None:
            return None
        result=source_from_paths(self.path(spec['source_manifest']),self.path(spec['source_root'],directory=True))
        self.budget-=sum(len(raw) for _,raw in result.source_files)
        if self.budget<0:
            raise ForecastEvidenceRefused('Bundle source budget exhausted')
        return result


def _prepare_accountability_bundle(reader,bundle):
    _fields(bundle,'schema asof forecasts')
    if bundle['schema'] not in ('AFI_ACCOUNTABILITY_BUNDLE_V1','AFI_ACCOUNTABILITY_BUNDLE_V2') or type(bundle['forecasts']) is not list or not 1<=len(bundle['forecasts'])<=64:
        raise ForecastEvidenceRefused('Bounded accountability bundle required')
    binding='source_manifest source_root' if bundle['schema'].endswith('V1') else 'source_archive'
    asof=_time(datetime.fromisoformat(bundle['asof']))
    entries,updates=[],[]
    for spec in bundle['forecasts']:
        _fields(spec,'artifact dataset_manifest dataset_records '+binding+' history expected_head append')
        original=reader.dataset(spec,asof);source=reader.source(spec);history=[]
        if type(spec['history']) is not list or len(spec['history'])>128:
            raise ForecastEvidenceRefused('Bounded bundle history required')
        for old in spec['history']:
            _fields(old,'artifact dataset_manifest dataset_records '+binding)
            history.append((reader.path(old['artifact']),reader.dataset(old,asof),reader.source(old)))
        entry=ForecastHistory(reader.path(spec['artifact']),original,tuple(history),spec['expected_head'],source)
        entries.append(entry)
        update=spec['append']
        if update is not None:
            _fields(update,'dataset_manifest dataset_records '+binding+' outcome_asof')
            updates.append((reader.dataset(update,asof),reader.source(update),_time(datetime.fromisoformat(update['outcome_asof']))))
        else:updates.append(None)
    # Complete all input/history/duplicate validation before any publication.
    build_accountability_report(entries,evidence_asof=asof)
    from app.backtest.forecast_outcomes import preview_outcome
    for entry,update in zip(entries,updates,strict=True):
        if update is not None:
            review,source,cutoff=update
            preview_outcome(entry.forecast_path,entry.forecast_review,review,evidence_asof=asof,outcome_asof=cutoff,
                            history=entry.history,expected_head=entry.expected_head,source_review=entry.source_review,outcome_source=source)
    return asof,entries,updates


def run_bundle(*, bundle_root,bundle_name,output_root,continuation_output_prefix=None,evidence_states=False):
    reader=BundleReader(bundle_root);bundle=_json(reader.read(bundle_name));asof,entries,updates=_prepare_accountability_bundle(reader,bundle)
    if continuation_output_prefix is not None:
        # Explicit mapping must already identify the exact reviewed output directory.
        # Refuse before appending anything; never infer a portable path from cwd.
        mapped=reader.path(continuation_output_prefix,directory=True)
        if mapped.resolve()!=Path(output_root).resolve():
            raise ForecastEvidenceRefused('Continuation output mapping mismatch')
    for i,(entry,update) in enumerate(zip(entries,updates,strict=True)):
        if update is None:
            continue
        review,outcome_source,cutoff=update
        path,record=append_outcome(output_root,entry.forecast_path,entry.forecast_review,review,evidence_asof=asof,
                                   outcome_asof=cutoff,history=entry.history,expected_head=entry.expected_head,
                                   source_review=entry.source_review,outcome_source=outcome_source)
        chain=entry.history
        if record['artifact_sha256']!=entry.expected_head:
            chain=(*chain,(path,review,outcome_source))
        entries[i]=ForecastHistory(entry.forecast_path,entry.forecast_review,chain,record['artifact_sha256'],entry.source_review)
    report=build_accountability_report(entries,evidence_asof=asof)
    text=json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n'
    report_path=publish_research_text(output_root,text,extension='.json')
    html_path=publish_research_text(output_root,render_accountability_report(report),extension='.html')
    browser_text=browser_export(report)
    browser_path=publish_research_text(output_root,browser_text,extension='.json')
    # Re-read exact derived bytes rather than reporting merely successful HTTP/I/O.
    if report_path.read_text(encoding='utf-8')!=text or html_path.read_text(encoding='utf-8')!=render_accountability_report(report) or browser_path.read_text(encoding='utf-8')!=browser_text:
        raise ForecastEvidenceRefused('Accountability output read-back failed')
    result={'status':'OFFLINE_ACCOUNTABILITY_COMPLETE','report':report_path.name,'dashboard':html_path.name,
            'browser_export':browser_path.name,'updated_heads':[e.expected_head for e in entries],'forecast_n':report['forecast_n'],
            'scored_n':report['score']['scored_n'],'production_approved':False,'trading_authority':False}
    if evidence_states:
        from app.backtest.forecast_evidence_state_report import publish_evidence_state_report

        result['evidence_states']=publish_evidence_state_report(output_root,entries,evidence_asof=asof)
    if continuation_output_prefix is not None:
        forecasts=[]
        for spec,entry in zip(bundle['forecasts'],entries,strict=True):
            history=list(spec['history'])
            if entry.expected_head!=spec['expected_head']:
                update=spec['append']
                history.append({**{k:v for k,v in update.items() if k!='outcome_asof'},
                                'artifact':continuation_output_prefix+'/'+entry.expected_head+'.json'})
            forecasts.append({**spec,'history':history,'expected_head':entry.expected_head,'append':None})
        continuation={**bundle,'forecasts':forecasts}
        # Revalidate the actual referenced files and complete chains, not just paths.
        _prepare_accountability_bundle(BundleReader(bundle_root),continuation)
        serialized=json.dumps(continuation,sort_keys=True,indent=2,allow_nan=False)+'\n'
        path=publish_research_text(output_root,serialized,extension='.json')
        if path.read_text(encoding='utf-8')!=serialized:
            raise ForecastEvidenceRefused('Continuation bundle read-back failed')
        result['continuation_bundle']=path.name
    return result


def _prepare_forecast_batch(reader,batch_name):
    from app.backtest.forecast_artifacts import artifact_envelope
    from app.backtest.forecast_baselines import fit_baseline

    plan=_json(reader.read(batch_name));_fields(plan,'schema asof forecasts')
    if plan['schema']!='AFI_FORECAST_BATCH_V1' or type(plan['forecasts']) is not list or not 1<=len(plan['forecasts'])<=64:
        raise ForecastEvidenceRefused('Bounded explicit forecast batch required')
    asof=_time(datetime.fromisoformat(plan['asof']));prepared=[];seen=set();ledger=[]
    for index,spec in enumerate(plan['forecasts']):
        _fields(spec,'dataset_manifest dataset_records source_archive asset_id issued_at method lookback horizon interval probability_method')
        review=reader.dataset(spec,asof);source=reader.source(spec)
        model=fit_baseline(review,asset_id=spec['asset_id'],issued_at=_time(datetime.fromisoformat(spec['issued_at'])),evidence_asof=asof,
                           method=spec['method'],lookback=spec['lookback'],horizon=spec['horizon'],source_review=source)
        interval=None if spec['interval'] is None else _json(reader.read(spec['interval']))
        envelope=artifact_envelope(review,model,evidence_asof=asof,interval=interval,source_review=source,probability_method=spec['probability_method'])
        if envelope['forecast_sha256'] in seen:raise ForecastEvidenceRefused('Duplicate batch forecast refused before publication')
        seen.add(envelope['forecast_sha256']);prepared.append((review,model,interval,spec['probability_method'],source))
        ledger.append({'index':index,'asset_id':model.asset_id,'asset_class':model.asset_class,'dataset_sha256':review.content_sha256,
                       'manifest_sha256':review.manifest_sha256,'release_source_sha256':model.release_source_sha256,
                       'forecast_sha256':envelope['forecast_sha256'],'artifact':envelope['artifact_sha256']+'.json','status':'NOT_ATTEMPTED'})
    return plan,asof,prepared,ledger


class ForecastBatchIncomplete(ForecastEvidenceRefused):
    """Failure evidence is available; original storage exception remains chained."""
    def __init__(self,result):
        super().__init__('Offline forecast batch incomplete; preserve partial evidence')
        self.result=result


def run_forecast_batch(*,bundle_root,batch_name,output_root):
    """Preflight all items, then verify each immutable publication independently.

    This is not an atomic multi-file transaction. A failed publication is
    uncertain, not presumed absent; no cleanup or automatic retry occurs.
    """
    from app.backtest.forecast_artifacts import publish_forecast, read_forecast
    from app.backtest.forecast_dashboard import render_dashboard

    reader=BundleReader(bundle_root);plan,asof,prepared,ledger=_prepare_forecast_batch(reader,batch_name)
    html=render_dashboard(prepared,evidence_asof=asof,title='Atlas offline multi-market forecast batch')
    stage='FORECAST_PUBLICATION';current=None;dashboard=None;index_path=None
    try:
        for current,(review,model,interval,probability,source) in enumerate(prepared):
            ledger[current]['status']='IN_PROGRESS'
            path=publish_forecast(output_root,review,model,evidence_asof=asof,interval=interval,source_review=source,probability_method=probability)
            checked=read_forecast(path,review,evidence_asof=asof,source_review=source)
            if path.name!=ledger[current]['artifact'] or checked['forecast_sha256']!=ledger[current]['forecast_sha256']:
                raise ForecastEvidenceRefused('Batch publication differs from preflight identity')
            ledger[current]['status']='PUBLISHED_VERIFIED'
        current=None;stage='DASHBOARD_PUBLICATION'
        dashboard=publish_research_text(output_root,html,extension='.html')
        if dashboard.read_text(encoding='utf-8')!=html:raise ForecastEvidenceRefused('Batch dashboard read-back failed')
        stage='INDEX_PUBLICATION'
        manifest={'schema':'AFI_FORECAST_BATCH_RESULT_V1','status':'OFFLINE_FORECAST_BATCH_COMPLETE','asof':asof.isoformat(),
                  'plan_sha256':fingerprint(plan),'forecast_n':len(ledger),'unique_asset_n':len({r['asset_id'] for r in ledger}),
                  'items':ledger,'dashboard':dashboard.name,'pooled_price_error':None,'ranking':None,
                  'production_approved':False,'trading_authority':False,'predictive_skill_established':False,'calibration_established':False}
        raw=json.dumps(manifest,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n'
        index_path=publish_research_text(output_root,raw,extension='.json')
        if index_path.read_text(encoding='utf-8')!=raw:raise ForecastEvidenceRefused('Batch index read-back failed')
    except (OSError,ValueError,TypeError,KeyError,OverflowError) as error:
        if current is not None and ledger[current]['status']=='IN_PROGRESS':ledger[current]['status']='UNCERTAIN_PUBLICATION'
        result={'schema':'AFI_FORECAST_BATCH_FAILURE_V1','status':'INCOMPLETE','plan_sha256':fingerprint(plan),
                'failed_stage':stage,'error_type':type(error).__name__,'error_errno':getattr(error,'errno',None),'items':ledger,
                'dashboard':dashboard.name if dashboard else None,'index':index_path.name if index_path else None,
                'failure_report':None,'failure_report_error_type':None,'production_approved':False,'trading_authority':False}
        try:
            failure=publish_research_text(output_root,json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n',extension='.json')
            if hashlib.sha256(failure.read_bytes()).hexdigest()!=failure.stem:raise ForecastEvidenceRefused('Failure evidence read-back failed')
            result['failure_report']=failure.name
        except (OSError,ValueError,TypeError,KeyError,OverflowError) as evidence_error:
            result['failure_report_error_type']=type(evidence_error).__name__
        raise ForecastBatchIncomplete(result) from error
    return {'status':'OFFLINE_FORECAST_BATCH_COMPLETE','index':index_path.name,'dashboard':dashboard.name,
            'forecast_n':len(ledger),'unique_asset_n':len({r['asset_id'] for r in ledger}),
            'production_approved':False,'trading_authority':False,'predictive_skill_established':False}


def _verified_batch(reader,request,*,reproduce_dashboard=False):
    """Shared read-only batch reconstruction; no publication or outcome writes."""
    from app.backtest.forecast_artifacts import read_forecast

    plan,issued_asof,prepared,ledger=_prepare_forecast_batch(reader,request['batch_plan'])
    raw_index=reader.read(request['batch_index']);digest=hashlib.sha256(raw_index).hexdigest()
    if digest!=_pair_hash(request['expected_index_sha256']) or PurePosixPath(request['batch_index']).name!=digest+'.json':
        raise ForecastEvidenceRefused('Batch index differs from caller-retained identity')
    index=_json(raw_index);parent=PurePosixPath(request['batch_index']).parent
    dashboard=index.get('dashboard')
    if type(dashboard) is not str or len(dashboard)!=69 or dashboard[-5:]!='.html':raise ForecastEvidenceRefused('Exact batch dashboard identity required')
    _pair_hash(dashboard[:-5]);dashboard_raw=reader.read((parent/dashboard).as_posix())
    if hashlib.sha256(dashboard_raw).hexdigest()!=dashboard[:-5]:raise ForecastEvidenceRefused('Batch dashboard bytes changed')
    for item,(review,_,_,_,source) in zip(ledger,prepared,strict=True):
        data=read_forecast(reader.path((parent/item['artifact']).as_posix()),review,evidence_asof=issued_asof,source_review=source)
        if data['forecast_sha256']!=item['forecast_sha256']:raise ForecastEvidenceRefused('Batch forecast changed')
        item['status']='PUBLISHED_VERIFIED'
    expected={'schema':'AFI_FORECAST_BATCH_RESULT_V1','status':'OFFLINE_FORECAST_BATCH_COMPLETE','asof':issued_asof.isoformat(),
              'plan_sha256':fingerprint(plan),'forecast_n':len(ledger),'unique_asset_n':len({r['asset_id'] for r in ledger}),
              'items':ledger,'dashboard':dashboard,'pooled_price_error':None,'ranking':None,
              'production_approved':False,'trading_authority':False,'predictive_skill_established':False,'calibration_established':False}
    if raw_index!=(json.dumps(expected,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode():
        raise ForecastEvidenceRefused('Batch index contradicts reconstructed forecast evidence')
    if reproduce_dashboard:
        from app.backtest.forecast_dashboard import render_dashboard
        rendered=render_dashboard(prepared,evidence_asof=issued_asof,title='Atlas offline multi-market forecast batch')
        if dashboard_raw!=rendered.encode('utf-8'):
            # The retained V1 scriptless dashboard predates the two error
            # columns. Reconstruct that exact known layout as well; the
            # caller-pinned dashboard hash above still binds the bytes.
            legacy=render_dashboard(prepared,evidence_asof=issued_asof,
                                    title='Atlas offline multi-market forecast batch',legacy_error_layout=True)
            if dashboard_raw!=legacy.encode('utf-8'):
                raise ForecastEvidenceRefused('Batch dashboard differs from reconstructed forecast evidence')
    return plan,issued_asof,prepared,ledger,parent,digest,index


def prepare_batch_accountability(*,bundle_root,request_name,output_root):
    """Verify a batch and publish an explicit V2 bundle; never append outcomes."""
    reader=BundleReader(bundle_root);request=_json(reader.read(request_name))
    _fields(request,'schema asof batch_plan batch_index expected_index_sha256 outcomes')
    if request['schema']!='AFI_BATCH_ACCOUNTABILITY_REQUEST_V1':raise ForecastEvidenceRefused('Explicit batch accounting request required')
    asof=_time(datetime.fromisoformat(request['asof']))
    plan,issued_asof,_prepared,ledger,parent,digest,_index=_verified_batch(reader,request)
    if asof<issued_asof:raise ForecastEvidenceRefused('Accounting evidence time predates original batch')
    if type(request['outcomes']) is not list or len(request['outcomes'])!=len(ledger):raise ForecastEvidenceRefused('One explicit outcome instruction per forecast required')
    instructions={}
    for instruction in request['outcomes']:
        _fields(instruction,'forecast_sha256 history expected_head append');identity=_pair_hash(instruction['forecast_sha256'])
        if identity in instructions:raise ForecastEvidenceRefused('Duplicate batch outcome instruction')
        instructions[identity]=instruction
    if set(instructions)!={r['forecast_sha256'] for r in ledger}:raise ForecastEvidenceRefused('Missing or foreign batch outcome instruction')
    forecasts=[]
    for spec,item in zip(plan['forecasts'],ledger,strict=True):
        instruction=instructions[item['forecast_sha256']]
        forecasts.append({'artifact':(parent/item['artifact']).as_posix(),
                **{k:spec[k] for k in ('dataset_manifest','dataset_records','source_archive')},
                **{k:instruction[k] for k in ('history','expected_head','append')}})
    bundle={'schema':'AFI_ACCOUNTABILITY_BUNDLE_V2','asof':asof.isoformat(),'forecasts':forecasts}
    _prepare_accountability_bundle(reader,bundle)  # Includes no-write append previews.
    text=json.dumps(bundle,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n'
    path=publish_research_text(output_root,text,extension='.json')
    if path.read_text(encoding='utf-8')!=text:raise ForecastEvidenceRefused('Prepared bundle read-back failed')
    provenance={'schema':'AFI_BATCH_ACCOUNTABILITY_BRIDGE_V1','request_sha256':fingerprint(request),
                'batch_plan_sha256':fingerprint(plan),'batch_index_sha256':digest,'bundle':path.name,
                'forecast_n':len(forecasts),'outcome_appends_performed':0,'forecast_writes_performed':0,
                'production_approved':False,'trading_authority':False}
    metadata=json.dumps(provenance,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n'
    sidecar=publish_research_text(output_root,metadata,extension='.json')
    if sidecar.read_text(encoding='utf-8')!=metadata:raise ForecastEvidenceRefused('Bridge provenance read-back failed')
    return {'status':'OFFLINE_BATCH_ACCOUNTABILITY_PREPARED','bundle':path.name,'provenance':sidecar.name,
            'forecast_n':len(forecasts),'outcome_appends_performed':0,'production_approved':False,'trading_authority':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description='Offline synthetic forecast accountability; no providers or execution')
    parser.add_argument('--bundle-root',required=True);parser.add_argument('--output-root',required=True)
    parser.add_argument('--continuation-output-prefix',help='Explicit reviewed relative output directory, bundle mode only')
    parser.add_argument('--evidence-states',action='store_true',help='Opt-in V2 evidence-state companion, bundle mode only')
    mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--bundle');mode.add_argument('--forecast-batch');mode.add_argument('--batch-accountability')
    args=parser.parse_args(argv)
    if args.continuation_output_prefix is not None and args.bundle is None:
        parser.error('Continuation export requires accountability bundle mode')
    if args.evidence_states and args.bundle is None:
        parser.error('Evidence-state companion requires accountability bundle mode')
    try:
        result=(prepare_batch_accountability(bundle_root=args.bundle_root,request_name=args.batch_accountability,output_root=args.output_root) if args.batch_accountability is not None else
                run_forecast_batch(bundle_root=args.bundle_root,batch_name=args.forecast_batch,output_root=args.output_root) if args.forecast_batch is not None else
                run_bundle(bundle_root=args.bundle_root,bundle_name=args.bundle,output_root=args.output_root,continuation_output_prefix=args.continuation_output_prefix,evidence_states=args.evidence_states))
    except ForecastBatchIncomplete as error:
        print(json.dumps(error.result,sort_keys=True));return 2
    except (OSError,ValueError,TypeError,KeyError,OverflowError) as error:
        print(json.dumps({'status':'REFUSED','error_type':type(error).__name__,'message':'Offline bundle or publication refused; preserve partial evidence.','production_approved':False}))
        return 2
    print(json.dumps(result,sort_keys=True));return 0


if __name__=='__main__':
    raise SystemExit(main())
