"""Nonfinancial, bounded Alpaca IEX subscription-survey resume checkpoint.

Only advances after one fully acknowledged, disconnected, data-only batch.
The stored offset records SUBSCRIPTION ACK coverage, never fresh quotes,
financial source eligibility, verified broker coverage, or paper permission.
No financial-root writes. A leftover exclusive lock fails closed.
"""
import argparse
import asyncio
import hashlib
import json
import os
import secrets
from contextlib import contextmanager
from pathlib import Path

from scripts.observation_runtime import alpaca_iex_basic_research_batch as batch

SCHEMA = "ATLAS_IEX_BASIC_SUBSCRIPTION_SURVEY_CURSOR_V2"
STATUS = "RESEARCH_SUBSCRIPTION_ACK_ONLY_NOT_CURRENT_MARKET_COVERAGE"
SAFE_BATCH_KEYS = frozenset({
    "schema", "status", "selected_native_release", "catalog_digest",
    "catalog_count", "research_offset", "next_research_offset_uncommitted",
    "requested_symbols_count", "pinned_research_symbols_count",
    "one_websocket_connection_seconds", "authenticated",
    "all_requested_symbols_subscription_acknowledged",
    "websocket_closed_after_batch", "quote_messages_received",
    "quote_messages_accepted", "quote_messages_rejected",
    "symbols_with_accepted_quote", "fresh_quotes_seen_during_connection",
    "raw_quotes_or_prices_published", "cursor_durably_committed",
    "current_qualified_market_source",
    "independent_provider_contract_rights_accepted",
    "financial_position_owner_verified", "trading_suppressed",
    "paper_start_authorized", "live_money_authorized", "orders_created",
})
CURSOR = Path(r"D:\Work\Project Atlas\logs\research\iex_basic_subscription_cursor.json")


def _sha(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")).hexdigest()


def _directory(path):
    parent = path.parent
    if (not parent.is_dir() or parent.is_symlink()
            or parent.is_junction() or path.name != CURSOR.name):
        raise ValueError("IEX_SURVEY_LOCAL_RESEARCH_DIRECTORY_REQUIRED")
    if (path.is_symlink() or path.is_junction()
            or path.exists() and not path.is_file()):
        raise ValueError("IEX_SURVEY_CURSOR_NOT_ORDINARY_FILE")
    return parent


def _sealed(record):
    return {**record, "digest": _sha(record)}


def _validated(value):
    keys = {"schema", "status", "generation", "selected_native_release",
            "catalog_sha256",
            "catalog_count", "pinned_symbols_sha256",
            "last_research_offset", "next_research_offset",
            "total_acknowledged_subscription_symbols",
            "last_quote_messages_received", "last_quote_messages_accepted",
            "financial_source_accepted", "raw_prices_stored",
            "paper_start_authorized", "live_money_authorized", "digest"}
    if (type(value) is not dict or set(value) != keys
            or value["schema"] != SCHEMA or value["status"] != STATUS
            or any(type(value[k]) is not int or value[k] < 0 for k in (
                "generation", "catalog_count", "last_research_offset",
                "next_research_offset", "total_acknowledged_subscription_symbols",
                "last_quote_messages_received", "last_quote_messages_accepted"))
            or value["selected_native_release"] not in ("R15", "R22")
            or value["generation"] < 1 or value["catalog_count"] < 1
            or not value["last_research_offset"] < value["next_research_offset"]
            or value["next_research_offset"] > value["catalog_count"]
            or value["last_quote_messages_accepted"] >
                value["last_quote_messages_received"]
            or any(type(value[k]) is not str or len(value[k]) != 64
                   or any(x not in "0123456789abcdef" for x in value[k])
                   for k in ("catalog_sha256", "pinned_symbols_sha256", "digest"))
            or any(value[k] is not False for k in (
                "financial_source_accepted", "raw_prices_stored",
                "paper_start_authorized", "live_money_authorized"))
            or value["digest"] != _sha({k: v for k, v in value.items()
                                       if k != "digest"})):
        raise ValueError("IEX_SURVEY_CURSOR_SCOPE_OR_DIGEST_REFUSED")
    return value


def read_cursor(path=None):
    path = CURSOR if path is None else path
    _directory(path)
    if not path.exists():
        return None
    if not 0 < path.stat().st_size <= 4096:
        raise ValueError("IEX_SURVEY_CURSOR_SIZE_REFUSED")
    return _validated(json.loads(path.read_text(encoding="ascii")))


@contextmanager
def _single_survey(path):
    _directory(path)
    lock = path.with_suffix(".lock")
    if lock.exists() or lock.is_symlink():
        raise ValueError("IEX_SURVEY_CONCURRENT_OR_STALE_LOCK_REFUSED")
    fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def _write_atomic(path, row):
    _directory(path)
    raw = (json.dumps(_validated(row), sort_keys=True,
                      separators=(",", ":")) + "\n").encode("ascii")
    if len(raw) > 4096:
        raise ValueError("IEX_SURVEY_CURSOR_SIZE_REFUSED")
    temporary = path.with_name("." + path.name + "." + secrets.token_hex(12))
    fd = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(path))
    finally:
        if temporary.exists():
            temporary.unlink()


def _expected(old, roster, pins):
    if old is None:
        return 0
    if (old["selected_native_release"] != roster["selected_native_release"]
            or old["catalog_sha256"] != roster["catalog_sha256"]
            or old["catalog_count"] != roster["catalog_count"]
            or old["pinned_symbols_sha256"] != _sha(list(pins))):
        raise ValueError("IEX_SURVEY_CATALOG_OR_PINNED_RESEARCH_CHANGED")
    if old["next_research_offset"] >= (
            roster["catalog_count"] - len(roster["pinned_research_symbols"])):
        raise ValueError("IEX_SURVEY_SUBSCRIPTION_CYCLE_COMPLETE")
    return old["next_research_offset"]


async def resume_one(*, scope, pinned_research_symbols=(), seconds=12,
                     path=None, observer=None):
    if (scope != batch.SCOPE or type(pinned_research_symbols) not in (tuple, list)
            or type(seconds) is not int
            or not batch.MIN_SECONDS <= seconds <= batch.MAX_SECONDS):
        raise ValueError("IEX_SURVEY_EXPLICIT_BOUNDED_RESEARCH_ONLY_SCOPE_REQUIRED")
    path = CURSOR if path is None else path
    with _single_survey(path):
        old = read_cursor(path)
        # Probe planner only: credentials are not read until the cursor, catalog,
        # selected release, and data-only scope all agree.
        first = batch.prepare(scope=scope, offset=0,
                              pinned_research_symbols=pinned_research_symbols)
        offset = _expected(old, first, pinned_research_symbols)
        roster = batch.prepare(scope=scope, offset=offset,
                               pinned_research_symbols=pinned_research_symbols)
        if not offset <= roster["offset"] < roster["next_offset"]:
            raise ValueError("IEX_SURVEY_ROSTER_DID_NOT_ADVANCE")
        observe = batch.observe_one if observer is None else observer
        report = await observe(scope=scope, offset=offset,
                               pinned_research_symbols=pinned_research_symbols,
                               seconds=seconds)
        if (type(report) is not dict or set(report) != SAFE_BATCH_KEYS
                or report.get("schema") != batch.SCHEMA
                or report.get("catalog_digest") != roster["catalog_sha256"]
                or report.get("catalog_count") != roster["catalog_count"]
                or report.get("research_offset") != offset
                or report.get("next_research_offset_uncommitted") !=
                    roster["next_offset"]
                or report.get("requested_symbols_count") !=
                    roster["requested_symbol_count"]
                or report.get("pinned_research_symbols_count") !=
                    len(pinned_research_symbols)
                or report.get("one_websocket_connection_seconds") != seconds
                or report.get("selected_native_release") !=
                    roster["selected_native_release"]
                or report.get("status") !=
                    "AUTHENTICATED_30_SYMBOL_DATA_ONLY_OBSERVATION"
                or report.get("authenticated") is not True
                or report.get("all_requested_symbols_subscription_acknowledged") is not True
                or report.get("websocket_closed_after_batch") is not True
                or report.get("raw_quotes_or_prices_published") is not False
                or report.get("cursor_durably_committed") is not False
                or report.get("current_qualified_market_source") is not False
                or report.get("independent_provider_contract_rights_accepted") is not False
                or report.get("financial_position_owner_verified") is not False
                or report.get("trading_suppressed") is not True
                or report.get("paper_start_authorized") is not False
                or report.get("live_money_authorized") is not False
                or type(report.get("orders_created")) is not int
                or report.get("orders_created") != 0
                or type(report.get("fresh_quotes_seen_during_connection")) is not bool
                or type(report.get("quote_messages_rejected")) is not int
                or type(report.get("symbols_with_accepted_quote")) is not int
                or type(report.get("quote_messages_received")) is not int
                or type(report.get("quote_messages_accepted")) is not int
                or report["quote_messages_received"] < 0
                or not 0 <= report["quote_messages_accepted"] <=
                    report["quote_messages_received"]
                or report["quote_messages_rejected"] < 0
                or report["quote_messages_received"] !=
                    report["quote_messages_accepted"] + report["quote_messages_rejected"]
                or not 0 <= report["symbols_with_accepted_quote"] <=
                    roster["requested_symbol_count"]
                or report["fresh_quotes_seen_during_connection"] and
                    not report["quote_messages_accepted"]):
            raise ValueError("IEX_SURVEY_ONLY_EXACT_NONFINANCIAL_ACK_ADVANCES")
        # Neither the selected immutable release nor the research catalog may
        # change during the remote session before this local-only checkpoint.
        if batch.prepare(scope=scope, offset=offset,
                         pinned_research_symbols=pinned_research_symbols) != roster:
            raise ValueError("IEX_SURVEY_SELECTED_OR_CATALOG_CHANGED_DURING_SESSION")
        row = _sealed({
            "schema": SCHEMA, "status": STATUS,
            "selected_native_release": roster["selected_native_release"],
            "generation": 1 if old is None else old["generation"] + 1,
            "catalog_sha256": roster["catalog_sha256"],
            "catalog_count": roster["catalog_count"],
            "pinned_symbols_sha256": _sha(list(pinned_research_symbols)),
            "last_research_offset": offset,
            "next_research_offset": roster["next_offset"],
            "total_acknowledged_subscription_symbols": (
                (0 if old is None else old["total_acknowledged_subscription_symbols"])
                + roster["requested_symbol_count"]),
            "last_quote_messages_received": report["quote_messages_received"],
            "last_quote_messages_accepted": report["quote_messages_accepted"],
            "financial_source_accepted": False, "raw_prices_stored": False,
            "paper_start_authorized": False, "live_money_authorized": False,
        })
        _write_atomic(path, row)
        return {
            **report,
            "research_subscription_checkpoint_committed": True,
            "research_subscription_checkpoint_schema": SCHEMA,
            "research_subscription_generation": row["generation"],
            "next_subscription_research_offset_saved": row["next_research_offset"],
            "financial_execution_cursor_committed": False,
            "acknowledged_subscriptions_are_fresh_quotes": False,
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--execute-data-only", action="store_true")
    parser.add_argument("--confirm-scope")
    parser.add_argument("--monitor-research", action="append", default=[])
    parser.add_argument("--seconds", type=int, default=12)
    args = parser.parse_args(argv)
    try:
        if args.inspect:
            if args.confirm_scope is not None:
                raise ValueError("IEX_SURVEY_INSPECT_CANNOT_ACTIVATE")
            first = batch.prepare(scope=batch.SCOPE, offset=0,
                                  pinned_research_symbols=args.monitor_research)
            old = read_cursor()
            offset = _expected(old, first, args.monitor_research)
            print(json.dumps({
                "schema": SCHEMA, "status": "RESEARCH_ONLY_OFFLINE_RESUME_INSPECTION",
                "next_research_offset": offset,
                "saved_generation": 0 if old is None else old["generation"],
                "selected_native_release": first["selected_native_release"],
                "data_provider_called": False,
                "paper_start_authorized": False,
                "live_money_authorized": False}, sort_keys=True))
            return 0
        result = asyncio.run(resume_one(
            scope=args.confirm_scope,
            pinned_research_symbols=args.monitor_research,
            seconds=args.seconds))
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception:
        print(json.dumps({
            "schema": SCHEMA, "status": "NONFINANCIAL_SURVEY_REFUSED",
            "paper_start_authorized": False,
            "live_money_authorized": False,
            "orders_created": 0}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
