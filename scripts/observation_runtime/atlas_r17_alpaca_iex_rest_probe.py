"""Selected R17 one-GET Alpaca IEX transport observation — NEVER PAPER authority.

Read-only --inspect neither reads credentials nor opens provider sockets.
--execute-data-only requires the existing exact one-GET scope; one HTTPS GET,
8-second timeout, 8 KiB response cap, no redirects/retries, no order endpoints.
Even a fresh quote is NOT a provider license, continuity proof, or execution
source admission. Never print prices or credentials.
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

from app.investment.alpaca_iex import Credentials

from scripts import release_selection as selection
from scripts.observation_runtime.alpaca_iex_rest_access_probe import (
    DATA_BASE,
    LIMIT,
    SCOPE,
    SYMBOL,
    _NoRedirect,
    interpret_latest,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)
from scripts.observation_runtime.personal_version_safe_release_clock import (
    SELECTOR_NATIVE,
)
from scripts.release_selection_store import NativeSelectionStore

SCHEMA = "ATLAS_R17_IEX_ONE_GET_DATA_ONLY_NONFINANCIAL_V1"
SOURCE = "471205f2c4eaff6e3c4b17cc19f7e9d1a40522ae"
ARTIFACT = "bb8e0c3835400e515cc3079986be220dbd6f876e36bfd02808289245dada1d00"
HEAD = "bcc3a28ed294081464ea21379f537693835adb0400690c549ec5535ac3d518f7"
PREDECESSOR = "1244c614ccc9e89e436d90df77cebb6e44a57edcb44972660940ed29ebfcd593"
CONFIG = Path("D:/Work/Project Atlas/config/alpaca.env")
SELECTION = r"D:\AtlasRuntime\selection"


def require_selected_r17_nonfinancial():
    """Original Windows selector store, 16-chain and exact immutable release."""
    if os.name != "nt":
        raise ValueError("R17_IEX_ORIGINAL_WINDOWS_NATIVE_SELECTION_REQUIRED")
    store = NativeSelectionStore(
        root=SELECTION, native_root=list(SELECTOR_NATIVE),
    )
    try:
        with store.locked():
            records = store.records()
        if (len(records) != 16
                or any(row.get("revision") != i for i, row in enumerate(records, 1))
                or selection.digest(records[14]) != PREDECESSOR
                or selection.digest(records[-1]) != HEAD
                or records[-1].get("previous") != PREDECESSOR
                or records[-1].get("action") != "SELECT"
                or records[-1].get("restores") is not None):
            raise ValueError("R17_IEX_EXACT_SELECTED_NATIVE_REV16_REQUIRED")
        selected = selection.validate_spec(records[-1]["selected"], "WINDOWS_LOCAL")
        if (selected["release"] != SOURCE
                or selected["root"] != "D:\\AtlasRuntime\\releases\\"+SOURCE
                or selected["artifact_digest"] != ARTIFACT):
            raise ValueError("R17_IEX_EXACT_NONFINANCIAL_RELEASE_REQUIRED")
        return selected
    finally:
        store.close()


def denial():
    return {
        "schema": SCHEMA,
        "selected_native_revision": 16,
        "provider": "ALPACA",
        "data_feed": "IEX",
        "single_exchange_not_nbbo": True,
        "licensed_execution_entitlement_independently_accepted": False,
        "full_robinhood_equity_etf_coverage_verified": False,
        "continuous_quote_source_and_freshness_verified": False,
        "hyperliquid_data_source_not_covered": True,
        "financial_issuer_accepted": False,
        "native_paper_accounts_incepted": False,
        "financial_operating_gates_accepted": 0,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
        "paper_orders_created": 0,
        "real_money_orders_created": 0,
        "native_account_files_written": 0,
    }


def inspect():
    require_selected_r17_nonfinancial()
    present = CONFIG.is_file() and not CONFIG.is_symlink() and not CONFIG.is_junction()
    return {
        **denial(),
        "status": "R17_SELECTED_RESEARCH_ONLY_NO_NETWORK",
        "credential_file_present_without_reading": present,
        "credential_read": False,
        "network_requests": 0,
    }


def probe(*, confirmed_scope, symbol="MSFT", credential_reader=Credentials.load,
          opener=None, observed_at=None):
    if confirmed_scope != SCOPE or type(symbol) is not str or SYMBOL.fullmatch(symbol) is None:
        raise ValueError("R17_IEX_EXACT_DATA_ONLY_SCOPE_REQUIRED")
    before = require_selected_r17_nonfinancial()
    roots_before = inspect_two_lane_native_roots()
    if (roots_before.get("native_root_total") != 12
            or roots_before.get("all_twelve_distinct_and_empty") is not True):
        raise ValueError("R17_IEX_NATIVE_PAPER_ROOTS_CHANGED")
    if not CONFIG.is_file() or CONFIG.is_symlink() or CONFIG.is_junction():
        raise ValueError("R17_IEX_LOCAL_DATA_ONLY_CREDENTIALS_REQUIRED")
    credentials = credential_reader(CONFIG)
    # This exact class loader requires ALPACA_TRADING_ENABLED=false.
    if not isinstance(credentials, Credentials):
        raise TypeError("R17_IEX_VALID_DATA_ONLY_CREDENTIALS_REQUIRED")
    url = DATA_BASE + symbol + "/quotes/latest?feed=iex"
    if opener is None:
        opener = urllib.request.build_opener(
            _NoRedirect(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        )
    request = urllib.request.Request(
        url, method="GET",
        headers={
            "APCA-API-KEY-ID": credentials.key,
            "APCA-API-SECRET-KEY": credentials.secret,
            "Accept": "application/json",
            "User-Agent": "Atlas-R17-DataOnly-IEX/1.0",
        },
    )
    with opener.open(request, timeout=8) as response:
        if (response.status != 200 or response.geturl() != url
                or response.headers.get_content_type() != "application/json"):
            raise ValueError("R17_IEX_PINNED_DATA_ENDPOINT_RESPONSE_REFUSED")
        raw = response.read(LIMIT + 1)
        if not 0 < len(raw) <= LIMIT:
            raise ValueError("R17_IEX_BOUNDED_JSON_RESPONSE_REQUIRED")
    payload = json.loads(raw)
    observation = int(time.time()) if observed_at is None else observed_at
    sanitized = interpret_latest(payload, symbol=symbol, observed_at=observation)
    if (require_selected_r17_nonfinancial() != before
            or inspect_two_lane_native_roots() != roots_before):
        raise ValueError("R17_IEX_NATIVE_SELECTION_OR_ACCOUNTS_CHANGED")
    return {
        **denial(),
        "status": "R17_SINGLE_DATA_ONLY_HTTPS_OBSERVED_NOT_FINANCIAL_AUTHORITY",
        "observed_symbol": symbol,
        "http_data_endpoint_responded": True,
        "quote_timestamp_present": sanitized["latest_quote_timestamp_present"],
        "quote_timestamp_within_five_seconds_of_unqualified_host_clock":
            sanitized["quote_timestamp_within_five_seconds_of_UNQUALIFIED_host_clock"],
        "quote_age_approx_seconds": sanitized["reported_quote_age_seconds"],
        "raw_bid_ask_prices_exposed": False,
        "network_requests": 1,
        "credentials_exposed": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--inspect", action="store_true")
    group.add_argument("--execute-data-only", action="store_true")
    parser.add_argument("--confirm-scope")
    parser.add_argument("--symbol", default="MSFT")
    args = parser.parse_args(argv)
    if args.inspect:
        if args.confirm_scope is not None:
            raise SystemExit("R17_IEX_INSPECT_CANNOT_TAKE_EXECUTION_SCOPE")
        print(json.dumps(inspect(), sort_keys=True))
        return 0
    try:
        result = probe(confirmed_scope=args.confirm_scope, symbol=args.symbol)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, UnicodeError,
            TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        # Do not disclose provider HTTP responses, prices, or credentials.
        print(json.dumps({
            **denial(), "status": "R17_ONE_GET_DATA_ONLY_REFUSED_NOT_FINANCIAL",
            "credential_or_provider_error_redacted": True,
            "http_data_endpoint_responded": False,
            "financial_execution_authorized": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
