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
