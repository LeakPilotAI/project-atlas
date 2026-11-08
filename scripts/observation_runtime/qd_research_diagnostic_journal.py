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
