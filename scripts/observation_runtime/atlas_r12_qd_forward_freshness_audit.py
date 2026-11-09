"""Read-only QD historical coverage vs CURRENT forward source separation.

This is DIAGNOSTIC ONLY. Its explicit operator-supplied UTC reference is NOT an
independent financial clock and cannot permit financial PAPER. Reads just the
last bounded journal tail plus existing historical readiness counters and the
native QD custody inventory. No broker credentials, provider, or journal write.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(r'D:\Work\Project Atlas')
MAX_TAIL_BYTES=131072
MAX_RECENCY_SECONDS=3*86400


def aware_utc(value):
    if type(value) is not str or len(value)>64:
        raise ValueError('R12_QD_FORWARD_REFERENCE_TIMESTAMP_REQUIRED')
    try:
        stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:
        raise ValueError('R12_QD_FORWARD_REFERENCE_TIMESTAMP_REQUIRED') from None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('R12_QD_FORWARD_AWARE_UTC_REQUIRED')
    return stamp.astimezone(timezone.utc)


def tail_evidence(path):
    """Bounded final-row read. An interrupted/incomplete last row REFUSES."""
    path=Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size==0:
        raise ValueError('R12_QD_FORWARD_JOURNAL_ABSENT_OR_UNSAFE')
    size=path.stat().st_size
    with path.open('rb') as handle:
        seek=max(0,size-MAX_TAIL_BYTES)
        handle.seek(seek)
        raw=handle.read(MAX_TAIL_BYTES)
    if not raw.endswith(b'\n'):
        raise ValueError('R12_QD_FORWARD_JOURNAL_PARTIAL_LAST_RECORD')
    if seek:
        _,sep,raw=raw.partition(b'\n')
        if not sep:
            raise ValueError('R12_QD_FORWARD_LAST_RECORD_UNBOUNDED')
    lines=[line for line in raw.splitlines() if line.strip()]
    if not lines or len(lines[-1])>16384:
        raise ValueError('R12_QD_FORWARD_LAST_RECORD_UNAVAILABLE')
    try:
        entry=json.loads(lines[-1])
    except (UnicodeError,ValueError):
        raise ValueError('R12_QD_FORWARD_LAST_RECORD_MALFORMED') from None
    if (type(entry) is not dict or type(entry.get('timestamp')) is not str
            or type(entry.get('symbol')) is not str
            or type(entry.get('patient_state')) is not str):
        raise ValueError('R12_QD_FORWARD_LAST_RECORD_SCOPE_MISSING')
    return {'file_bytes':size,'last_event_utc':aware_utc(entry['timestamp']).isoformat(),
            'last_event_symbol':entry['symbol'],'last_event_state':entry['patient_state'],
            'bounded_tail_records_sampled':len(lines)}


def evaluate(*,historical,tail,native,reference_utc):
    """A historical threshold PASS can never be operating source admission."""
    asof=aware_utc(reference_utc)
    if (type(historical) is not dict or
            historical.get('execution')!='MANUAL_ONLY' or
            historical.get('live_capital_allowed') is not False or
            historical.get('automatic_real_money_execution') is not False or
            type(historical.get('evaluations')) is not int or
            type(historical.get('symbols')) is not int or
            type(historical.get('unique_days')) is not int):
        raise ValueError('R12_QD_FORWARD_HISTORICAL_SCOPE_REFUSED')
    if (type(native) is not dict or
            native.get('schema')!='ATLAS_QD_NATIVE_SOURCE_INVENTORY_V1' or
            type(native.get('operational_publication_verified')) is not bool):
        raise ValueError('R12_QD_FORWARD_NATIVE_CUSTODY_INVALID')
    if type(tail) is not dict or type(tail.get('file_bytes')) is not int or tail['file_bytes']<=0:
        raise ValueError('R12_QD_FORWARD_LAST_OBSERVATION_REQUIRED')
    last=aware_utc(tail.get('last_event_utc'))
    age=(asof-last).total_seconds()
    if age<0:
        raise ValueError('R12_QD_FORWARD_EVENT_FROM_UNTRUSTED_FUTURE')
    age_seconds=int(age)
    recency=age<=MAX_RECENCY_SECONDS
    # Even recent shadow journals and a truthy inventory cannot replace
    # independently verified SOURCE_AUTHORITY, custody ACK, prices, and clock.
    return {'schema':'ATLAS_R12_QD_SHADOW_VS_OPERATIONAL_SOURCE_AUDIT_V1',
        'status':'SHADOW_COVERAGE_ONLY_FORWARD_SOURCE_NOT_ACCEPTED',
        'as_of_utc':asof.isoformat(),
        'time_reference':'EXPLICIT_DIAGNOSTIC_ARGUMENT_NOT_FINANCIAL_CLOCK',
        'historical_shadow_thresholds_met':historical.get('ready') is True,
        'historical_evaluations':historical['evaluations'],
        'historical_symbols':historical['symbols'],
        'historical_unique_days':historical['unique_days'],
        'historical_watch_only_and_accumulation_counts':{
          k:v for k,v in historical.get('state_counts',{}).items()
          if k in ('WATCH','ACCUMULATION')},
        'shadow_last_event_utc':last.isoformat(),
        'shadow_last_event_age_days':round(age/86400,2),
        'shadow_last_event_recent_by_diagnostic_3_day_limit':recency,
        'shadow_journal_bytes':tail['file_bytes'],
        'shadow_journal_kind':'HISTORICAL_SHADOW_NOT_INDEPENDENT_FORWARD_COLLECTION',
        'qd_native_custody_parent_present':native.get('source_parent_present') is True,
        'qd_native_custody_children':native.get('ordinary_child_count'),
        'qd_native_forward_publication_verified':native['operational_publication_verified'],
        'independent_provider_iex_rights_verified':False,
        'current_forward_issuer_provenance_verified':False,
        'native_publication_acknowledged':False,
        'financial_clock_verified':False,
        'operational_qd_source_accepted':False,
        'financial_paper_gates_accepted':0,
        'startup_authorized':False,'provider_connections_opened':False,
        'paper_accounts_created':False,'orders_submitted':False,
        'next_dependency':'Obtain separately authorized genuine provider data-only IEX evidence and independently owned current QD forward publication with native issuer/custody ACK.'}


def inspect(*,reference_utc,path=None):
    from app.investment.quality_dips_v3_forward_store import V3_FORWARD_PATH
    from app.investment.quality_dips_v3_forward_readiness import forward_readiness
    from scripts.observation_runtime.quality_dips_source_inventory import inspect as custody
    path=Path(path) if path is not None else V3_FORWARD_PATH
    return evaluate(historical=forward_readiness(path),tail=tail_evidence(path),
                    native=custody(),reference_utc=reference_utc)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--as-of-utc',required=True,
                   help='Explicit audit reference; NOT independent financial clock evidence')
    args=p.parse_args(argv)
    print(json.dumps(inspect(reference_utc=args.as_of_utc),sort_keys=True,indent=2))
    return 2 # NEVER a startup/operational acceptance


if __name__=='__main__':
    raise SystemExit(main())
