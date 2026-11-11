"""Selected R16 Alpaca IEX single-GET research/transport observation ONLY.

R15's original IEX REST probe correctly refuses after R16 selection. This
is the current-R16 equivalent, with a pinned HTTPS data endpoint, 1 symbol,
1 GET, <8KB response, no redirect or retry, no orders, no provider/paper
source grant, no quote prices in any output. The current selected native
R16 immutable installed code and 12 empty financial roots remain unchanged.

One positive transport observation is NOT contract/license entitlement or
a continuously owned source publishing lease; no E1 gate is accepted.
"""
from __future__ import annotations

import argparse
import json
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

from app.investment.alpaca_iex import Credentials
from scripts.observation_runtime.alpaca_iex_rest_access_probe import (
    DATA_BASE, LIMIT, SYMBOL, SCOPE, _NoRedirect, interpret_latest,
    _no_financial_grant,
)
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    ARTIFACT_DIGEST, R16_HEAD, R16_RECORD_SHA, selected_code,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)

SCHEMA = "ATLAS_R16_IEX_ONE_GET_DATA_ONLY_NONFINANCIAL_V1"
CONFIG = Path("D:/Work/Project Atlas/config/alpaca.env")


def require_selected_r16_data_only():
    selected = selected_code()
    if (type(selected) is not dict
            or selected.get("selected_revision") != 15
            or selected.get("selected_native_head") != R16_HEAD
            or selected.get("selected_native_record_sha256") != R16_RECORD_SHA
            or selected.get("installed_artifact_digest") != ARTIFACT_DIGEST
            or selected.get("code_selection_accepted") is not True
            or selected.get("native_receipt_and_install_ack_verified") is not True
            or selected.get("native_selection_append_only_chain_verified") is not True
            or any(selected.get(key) is not False for key in (
                "financial_clock_operational_accepted",
                "provider_source_operational_accepted",
                "financial_writer_operational_accepted",
                "paper_start_authorized",
                "live_trading_authorized"))):
        raise ValueError("R16_IEX_CURRENT_CODE_ONLY_NO_TRADING_SELECTED_REQUIRED")
    return selected


def no_financial_claim():
    return {
        "schema": SCHEMA,
        "selected_native_revision": 15,
        "provider": "ALPACA",
        "data_feed": "IEX",
        "single_exchange_not_nbbo": True,
        "independent_provider_license_verified": False,
        "full_robinhood_equity_etf_coverage_verified": False,
        "continuous_quote_source_and_freshness_verified": False,
        "hyperliquid_data_source_not_covered": True,
        "financial_writer_role_enrolled": False,
        "financial_operating_gates_accepted": 0,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
        "paper_orders_created": 0,
        "real_money_orders_created": 0,
        "native_account_files_written": 0,
    }


def inspect():
    require_selected_r16_data_only()
    path = CONFIG
    safe_config = path.is_file() and not path.is_symlink() and not path.is_junction()
    return {
        **no_financial_claim(),
        "status": "R16_SELECTED_RESEARCH_ONLY_NO_NETWORK",
        "credentials_file_present_without_reading": safe_config,
        "credentials_read": False,
        "network_requests": 0,
    }


def probe(*, confirmed_scope, symbol="MSFT", credential_path=None,
          credential_reader=Credentials.load, opener=None, observed_at=None):
    """One genuine HTTPS GET, only if explicitly allowed data-only scope."""
    if (confirmed_scope != SCOPE
            or type(symbol) is not str or SYMBOL.fullmatch(symbol) is None
            or (credential_path is not None and
                Path(credential_path) != CONFIG)):
        raise ValueError("R16_IEX_EXACT_BOUNDED_DATA_ONLY_SCOPE_REQUIRED")
    before = require_selected_r16_data_only()
    roots_before = inspect_two_lane_native_roots()
    if (roots_before.get("native_root_total") != 12
            or roots_before.get("all_twelve_distinct_and_empty") is not True):
        raise ValueError("R16_IEX_REAL_NATIVE_ROOTS_NOT_EMPTY_REFUSE")
    if (not CONFIG.is_file() or CONFIG.is_symlink()
            or CONFIG.is_junction()):
        raise ValueError("R16_IEX_EXACT_LOCAL_CREDENTIAL_CONFIG_REQUIRED")
    credentials = credential_reader(CONFIG)
    # Credentials.load enforces ALPACA_TRADING_ENABLED=false.
    if not isinstance(credentials, Credentials):
        raise ValueError("R16_IEX_VALID_DATA_ONLY_CREDENTIALS_REQUIRED")
    url = DATA_BASE + symbol + "/quotes/latest?feed=iex"
    if opener is None:
        opener = urllib.request.build_opener(
            _NoRedirect(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        )
    request = urllib.request.Request(
        url, method="GET",
        headers={
            "APCA-API-KEY-ID":credentials.key,
            "APCA-API-SECRET-KEY":credentials.secret,
            "Accept":"application/json",
            "User-Agent":"Atlas-R16-IEX-DataOnly-REST/1.0",
        })
    with opener.open(request,timeout=8) as response:
        if (response.status != 200
                or response.geturl() != url
                or response.headers.get_content_type() != "application/json"):
            raise ValueError("R16_IEX_ONLY_DATA_HTTPS_JSON_200_REQUIRED")
        raw = response.read(LIMIT+1)
        if not 0 < len(raw) <= LIMIT:
            raise ValueError("R16_IEX_JSON_RESPONSE_BOUNDED_REQUIRED")
    payload = json.loads(raw)
    # OS time is observation-only (not trusted financial UTC).
    clock = int(time.time()) if observed_at is None else observed_at
    sanitized = interpret_latest(payload,symbol=symbol,observed_at=clock)
    after = require_selected_r16_data_only()
    roots_after = inspect_two_lane_native_roots()
    if after != before or roots_after != roots_before:
        raise ValueError("R16_IEX_SELECTED_CODE_OR_NATIVE_ROOTS_CHANGED")
    return {
        **no_financial_claim(),
        "status": "R16_BOUNDED_IEX_HTTPS_DATA_ONLY_OBSERVED_NO_FINANCIAL_GRANT",
        "observed_symbol":symbol,
        "http_data_endpoint_responded":True,
        "quote_timestamp_present":sanitized["latest_quote_timestamp_present"],
        "quote_timestamp_within_five_seconds_of_unqualified_host_clock":
            sanitized["quote_timestamp_within_five_seconds_of_UNQUALIFIED_host_clock"],
        "quote_age_approx_seconds":sanitized["reported_quote_age_seconds"],
        "raw_bid_ask_prices_exposed":False,
        "network_requests":1,
        "credentials_exposed":False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect",action="store_true")
    parser.add_argument("--execute-data-only",action="store_true")
    parser.add_argument("--confirm-scope")
    parser.add_argument("--symbol",default="MSFT")
    args = parser.parse_args(argv)
    if args.inspect == args.execute_data_only:
        raise SystemExit("R16_IEX_EXACTLY_ONE_INSPECT_OR_DATA_ONLY_REQUIRED")
    if args.inspect:
        if args.confirm_scope is not None:
            raise SystemExit("R16_IEX_INSPECT_MUST_NOT_INCLUDE_DATA_ONLY_APPROVAL")
        print(json.dumps(inspect(),sort_keys=True))
        return 0
    try:
        result = probe(
            confirmed_scope=args.confirm_scope,symbol=args.symbol)
        print(json.dumps(result,sort_keys=True))
        return 0
    except (ValueError, OSError, UnicodeError, TimeoutError,
            TypeError, KeyError, urllib.error.URLError, json.JSONDecodeError):
        # Never print HTTP provider response, raw quote or credentials.
        print(json.dumps({
            **no_financial_claim(),
            "status":"R16_BOUNDED_IEX_DATA_ONLY_REFUSED",
            "http_data_endpoint_responded":False,
            "network_request_count_verified":False,
        },sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
