"""Append-only, non-authoritative JSONL diagnostic journal. Not a financial ledger."""
import json
import os
from datetime import UTC, datetime
from pathlib import Path

ALLOWED_SCHEMAS = {"ATLAS_QD_BOUNDED_PRICES_ONLY_V1", "ATLAS_QD_REPEATED_PRICES_ONLY_V1"}

def journal_diagnostic(result, *, path, timestamp=None):
    """Record a sanitized summary and sync it; never serialize provider payloads."""
    if type(result) is not dict or result.get("schema") not in ALLOWED_SCHEMAS:
        raise ValueError("QD_JOURNAL_DIAGNOSTIC_SCHEMA_REQUIRED")
    if (result.get("operational_source_accepted") is not False
            or result.get("paper_fill_authorized") is not False
            or result.get("live_order_authorized") is not False):
        raise ValueError("QD_JOURNAL_AUTHORITY_REFUSED")
    symbols = result.get("symbols")
    if (type(symbols) is not list or not 1 <= len(symbols) <= 8
            or any(type(x) is not str or not x.isascii() or not x.isalpha()
                   or not x.isupper() or len(x) > 8 for x in symbols)
            or len(set(symbols)) != len(symbols)):
        raise ValueError("QD_JOURNAL_SYMBOLS_REFUSED")
    refused = result.get("refused_count")
    rounds = result.get("rounds_completed", 1)
    if (type(refused) is not int or type(rounds) is not int or not 1 <= rounds <= 3
            or not 0 <= refused <= len(symbols)*rounds):
        raise ValueError("QD_JOURNAL_COUNTS_REFUSED")
    record = {"schema":"ATLAS_QD_DIAGNOSTIC_JOURNAL_V1",
              "at_utc": timestamp or datetime.now(UTC).isoformat(),
              "source_schema":result["schema"], "symbols":symbols,
              "rounds_completed":rounds,"refused_count":refused,
              "operational_source_accepted":False,"paper_fill_authorized":False,
              "live_order_authorized":False}
    target=Path(path)
    if target.is_symlink() or not target.parent.is_dir():
        raise ValueError("QD_JOURNAL_DESTINATION_REFUSED")
    payload=json.dumps(record,sort_keys=True,separators=(",",":"))+"\n"
    with target.open("a",encoding="utf-8",newline="\n") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return record


def inspect_diagnostic_journal(*, path):
    """Read-only, fail-closed scan; a truncated final line is NOT a completed run."""
    target=Path(path)
    if target.is_symlink() or not target.is_file():
        raise ValueError('QD_JOURNAL_SOURCE_REFUSED')
    raw=target.read_bytes()
    if not raw or not raw.endswith(b'\n') or len(raw)>2_000_000:
        raise ValueError('QD_JOURNAL_EMPTY_TRUNCATED_OR_OVERSIZED')
    try:
        lines=raw.decode('utf-8').splitlines()
    except UnicodeError as exc:
        raise ValueError('QD_JOURNAL_ENCODING_REFUSED') from exc
    if len(lines)>1000:
        raise ValueError('QD_JOURNAL_RECORD_LIMIT_REFUSED')
    for line in lines:
        try:
            record=json.loads(line)
        except (ValueError,TypeError) as exc:
            raise ValueError('QD_JOURNAL_INVALID_RECORD') from exc
        if (type(record) is not dict or set(record)!={
                'schema','at_utc','source_schema','symbols','rounds_completed',
                'refused_count','operational_source_accepted','paper_fill_authorized',
                'live_order_authorized'} or record['schema']!='ATLAS_QD_DIAGNOSTIC_JOURNAL_V1'
                or record['source_schema'] not in ALLOWED_SCHEMAS
                or any(record[k] is not False for k in ('operational_source_accepted',
                                                        'paper_fill_authorized','live_order_authorized'))
                or type(record['rounds_completed']) is not int
                or not 1<=record['rounds_completed']<=3
                or type(record['refused_count']) is not int
                or type(record['symbols']) is not list
                or not 1<=len(record['symbols'])<=8
                or len(set(record['symbols']))!=len(record['symbols'])
                or any(type(x) is not str or not x.isascii() or not x.isalpha()
                       or not x.isupper() or len(x)>8 for x in record['symbols'])
                or not 0<=record['refused_count']<=len(record['symbols'])*record['rounds_completed']
                or type(record['at_utc']) is not str):
            raise ValueError('QD_JOURNAL_RECORD_AUTHORITY_OR_SHAPE_REFUSED')
        try:
            moment=datetime.fromisoformat(record['at_utc'])
            if moment.utcoffset() is None or moment.utcoffset().total_seconds()!=0:
                raise ValueError('QD_JOURNAL_TIMESTAMP_REFUSED')
        except ValueError as exc:
            raise ValueError('QD_JOURNAL_TIMESTAMP_REFUSED') from exc
    return {'schema':'ATLAS_QD_DIAGNOSTIC_JOURNAL_INSPECTION_V1',
            'completed_records':len(lines),'last_record_refused_count':record['refused_count'],
            'operational_source_accepted':False,'paper_fill_authorized':False,
            'live_order_authorized':False}


def plan_interrupted_journal_recovery(*, path):
    """Read-only recovery plan; never truncates, rewrites, or blesses a journal."""
    target=Path(path)
    if target.is_symlink() or not target.is_file():
        raise ValueError('QD_RECOVERY_SOURCE_REFUSED')
    raw=target.read_bytes()
    if not raw or len(raw)>2_000_000:
        raise ValueError('QD_RECOVERY_SIZE_REFUSED')
    try:
        inspect_diagnostic_journal(path=target)
    except ValueError:
        pass
    else:
        return {'schema':'ATLAS_QD_JOURNAL_RECOVERY_PLAN_V1',
                'status':'ALREADY_COMPLETE','recoverable_records':len(raw.splitlines()),
                'mutation_authorized':False,'paper_fill_authorized':False,
                'live_order_authorized':False}
    # Only a non-newline-terminated suffix is a candidate for isolation.
    # A malformed *completed* line or a malformed prefix remains nonrecoverable.
    if raw.endswith(b'\n') or b'\n' not in raw:
        raise ValueError('QD_RECOVERY_NOT_TRAILING_FRAGMENT')
    prefix, _, fragment = raw.rpartition(b'\n')
    if not fragment or not prefix:
        raise ValueError('QD_RECOVERY_NO_COMPLETE_PREFIX')
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as directory:
        candidate=Path(directory)/'candidate.jsonl'
        candidate.write_bytes(prefix+b'\n')
        validated=inspect_diagnostic_journal(path=candidate)
    return {'schema':'ATLAS_QD_JOURNAL_RECOVERY_PLAN_V1',
            'status':'TRAILING_FRAGMENT_REQUIRES_OPERATOR_REVIEW',
            'recoverable_records':validated['completed_records'],
            'trailing_fragment_bytes':len(fragment),
            'mutation_authorized':False,'paper_fill_authorized':False,
            'live_order_authorized':False}


def export_recoverable_journal(*, source, destination):
    """Explicit, exclusive export of verified prefix; damaged original stays untouched."""
    src=Path(source)
    dst=Path(destination)
    if src.is_symlink() or not src.is_file() or dst.is_symlink() or not dst.parent.is_dir():
        raise ValueError('QD_RECOVERY_EXPORT_PATH_REFUSED')
    if src.resolve()==dst.resolve() or dst.exists():
        raise ValueError('QD_RECOVERY_EXPORT_OVERWRITE_REFUSED')
    plan=plan_interrupted_journal_recovery(path=src)
    if plan['status']!='TRAILING_FRAGMENT_REQUIRES_OPERATOR_REVIEW':
        raise ValueError('QD_RECOVERY_EXPORT_FRAGMENT_REQUIRED')
    raw=src.read_bytes()
    prefix, separator, fragment=raw.rpartition(b'\n')
    if not separator or len(fragment)!=plan['trailing_fragment_bytes']:
        raise ValueError('QD_RECOVERY_EXPORT_SOURCE_CHANGED')
    # Validate exact bytes to be exported, not merely a previous inspection.
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as directory:
        candidate=Path(directory)/'verified.jsonl'
        candidate.write_bytes(prefix+b'\n')
        verified=inspect_diagnostic_journal(path=candidate)
    if verified['completed_records']!=plan['recoverable_records']:
        raise ValueError('QD_RECOVERY_EXPORT_COUNT_CHANGED')
    descriptor=os.open(dst,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(descriptor,'wb') as output:
            output.write(prefix+b'\n')
            output.flush()
            os.fsync(output.fileno())
        inspect_diagnostic_journal(path=dst)
    except BaseException:
        dst.unlink(missing_ok=True)
        raise
    return {'schema':'ATLAS_QD_RECOVERY_EXPORT_V1',
            'status':'VERIFIED_PREFIX_EXPORTED_FOR_OPERATOR_REVIEW',
            'completed_records':verified['completed_records'],
            'original_preserved':True,'resume_authorized':False,
            'paper_fill_authorized':False,'live_order_authorized':False}
