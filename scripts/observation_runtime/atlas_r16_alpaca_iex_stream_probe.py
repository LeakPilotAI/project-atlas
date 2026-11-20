"""Selected R16 bounded live Alpaca IEX WebSocket OBSERVATION, never PAPER authority.

R15-only observational scripts cannot independently admit R16. This host-side
R16 replacement validates current immutable native selection, original
empty account roots and an exact explicit DATA-ONLY scope before credentials.
One websocket, 1-3 symbols, 10-45 seconds, ZERO reconnects or orders;
existing IEXFeed itself authenticates/subscribes/filters fresh quotes.
Only sanitized aggregate counts escape. No raw quotes, keys or price fields.

A successful bounded session does NOT independently verify license rights,
market-wide coverage, continuous financial feed publication, NBBO,
supervised account custody, executable fills or any of nine PAPER gates.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.investment.alpaca_iex import Credentials, IEXFeed, IEXRefused, SYMBOL
from scripts.observation_runtime.alpaca_iex_probe import (
    SCOPE, bounded_data_only_probe,
)
from scripts.observation_runtime.atlas_r16_alpaca_iex_rest_probe import (
    CONFIG, no_financial_claim, require_selected_r16_data_only,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)

SCHEMA="ATLAS_R16_IEX_BOUNDED_STREAM_DATA_ONLY_OBSERVATION_V1"
MAX_DURATION=45
MAX_SYMBOLS=3


def validate_scope(*, seconds, symbols, confirmed_scope):
    if (confirmed_scope != SCOPE
            or type(seconds) is not int or not 10 <= seconds <= MAX_DURATION
            or type(symbols) is not list or not 1 <= len(symbols) <= MAX_SYMBOLS
            or len(set(symbols)) != len(symbols)
            or any(type(symbol) is not str or SYMBOL.fullmatch(symbol) is None
                   for symbol in symbols)):
        raise ValueError("R16_IEX_WEBSOCKET_EXACT_BOUNDED_NO_TRADING_SCOPE_REQUIRED")
    return tuple(symbols)


def _assert_origins_still_original(before):
    current = require_selected_r16_data_only()
    roots = inspect_two_lane_native_roots()
    if (roots != before or roots.get("native_root_total") != 12
            or roots.get("all_twelve_distinct_and_empty") is not True):
        raise ValueError("R16_IEX_STREAM_ORIGINAL_ACCOUNT_NATIVE_ROOTS_CHANGED")
    return current


def _convert(result, *, requested, before, after):
    if (type(result) is not dict
            or result.get("schema") != "ATLAS_IEX_BOUNDED_DATA_ONLY_PROBE_V1"
            or result.get("status") !=
                "BOUNDED_FRESH_IEX_OBSERVED_NOT_FINANCIAL_AUTHORITY"
            or result.get("authenticated") is not True
            or result.get("subscribed") is not True
            or result.get("connection_closed") is not True
            or result.get("fresh_quote_observed_during_connection") is not True
            or type(result.get("quote_count")) is not int
            or result["quote_count"] <= 0
            or result.get("paper_fill_authorized") is not False
            or result.get("live_order_authorized") is not False
            or result.get("provider_rights_independently_accepted") is not False
            or result.get("continuous_executable_prices_verified") is not False
            or type(result.get("observed_symbols")) is not list
            or not set(result["observed_symbols"]) <= set(requested)
            or not result["observed_symbols"]
            or before != after):
        raise ValueError("R16_IEX_STREAM_EXACT_FRESH_READ_ONLY_RESULT_REQUIRED")
    rows = result.get("per_symbol_quote_diagnostics")
    if rows is None or type(rows) is not dict or set(rows) != set(requested):
        raise ValueError("R16_IEX_STREAM_PER_SYMBOL_PROVIDER_DIAGNOSTICS_REQUIRED")
    if any(type(v) is not dict or set(v) != {
            "received", "accepted", "rejected", "fresh_callbacks"}
           or any(type(number) is not int or number < 0
                  for number in v.values())
           or v["received"] != v["accepted"]+v["rejected"]
           or v["fresh_callbacks"] > v["accepted"]
           or (v["fresh_callbacks"] > 0) != (symbol in result["observed_symbols"])
           for symbol,v in rows.items()):
        raise ValueError("R16_IEX_STREAM_PROVIDER_COUNTS_INCONSISTENT")
    if sum(v["fresh_callbacks"] for v in rows.values()) != result.get(
            "callback_quote_count"):
        raise ValueError("R16_IEX_STREAM_CALLBACK_COUNT_CHANGED")
    return {
        **no_financial_claim(),
        "schema":SCHEMA,
        "status":"R16_BOUNDED_AUTHENTICATED_FRESH_IEX_STREAM_NOT_FINANCIAL_ACCEPTANCE",
        "selected_native_head_verified":True,
        "websocket_endpoint":"ALPACA_IEX_SINGLE_EXCHANGE",
        "request_symbols":list(requested),
        "observed_fresh_symbols":list(result["observed_symbols"]),
        "authenticated":True,
        "subscribed":True,
        "connection_closed":True,
        "fresh_quote_callbacks":result["callback_quote_count"],
        "per_symbol_counts":{s:dict(rows[s]) for s in requested},
        "max_reconnects":0,
        "network_connection_budget":1,
        "streaming_source_approved_for_financial_orders":False,
        "quotes_or_secrets_exported":False,
        "native_financial_account_files_written":0,
        "paper_orders_created":0,
    }


async def observe(*, seconds, symbols, confirmed_scope,
                  credential_reader=Credentials.load, feed_factory=IEXFeed):
    requested=validate_scope(
        seconds=seconds,symbols=symbols,confirmed_scope=confirmed_scope)
    before_selected=require_selected_r16_data_only()
    roots=inspect_two_lane_native_roots()
    if (roots.get("native_root_total") != 12
            or roots.get("all_twelve_distinct_and_empty") is not True):
        raise ValueError("R16_IEX_STREAM_ORIGINAL_NATIVE_ACCOUNT_ROOTS_NOT_EMPTY")
    if (not CONFIG.is_file() or CONFIG.is_symlink() or CONFIG.is_junction()):
        raise ValueError("R16_IEX_STREAM_EXACT_CREDENTIAL_CONFIG_MISSING")
    credentials=credential_reader(CONFIG)
    if not isinstance(credentials,Credentials):
        raise ValueError("R16_IEX_STREAM_VALIDATED_DATA_ONLY_CREDENTIALS_REQUIRED")
    result=await bounded_data_only_probe(
        seconds=seconds, symbols=list(requested),
        credentials=credentials,feed_factory=feed_factory)
    after_selected=_assert_origins_still_original(roots)
    return _convert(
        result,requested=requested,before=before_selected,after=after_selected)


def inspect():
    require_selected_r16_data_only()
    return {
        **no_financial_claim(),
        "schema":SCHEMA,
        "status":"R16_SELECTED_IEX_STREAM_SCOPE_ONLY_NO_NETWORK",
        "credentials_read":False,
        "provider_connected":False,
        "network_requests":0,
        "required_explicit_data_only_scope":SCOPE,
        "duration_bounds_seconds":[10,MAX_DURATION],
        "max_symbols":MAX_SYMBOLS,
        "max_reconnects":0,
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect",action="store_true")
    mode.add_argument("--execute-data-only",action="store_true")
    parser.add_argument("--confirm-scope")
    parser.add_argument("--seconds",type=int,default=30)
    parser.add_argument("--symbols",nargs="+",default=["MSFT","SPY"])
    args=parser.parse_args(argv)
    if args.inspect:
        if args.confirm_scope is not None:
            return 2
        print(json.dumps(inspect(),sort_keys=True))
        return 0
    try:
        result=asyncio.run(observe(
            seconds=args.seconds,symbols=args.symbols,
            confirmed_scope=args.confirm_scope))
        print(json.dumps(result,sort_keys=True))
        return 0
    except (ValueError,IEXRefused,OSError,TimeoutError,TypeError,KeyError):
        # Never forward provider exception strings, response frames or keys.
        print(json.dumps({
            **no_financial_claim(),"schema":SCHEMA,
            "status":"R16_IEX_BOUNDED_STREAM_NOT_ACCEPTED",
            "data_only_attempt_completed":False,
        },sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
