"""R16 Alpaca paper-key identity check: one GET, redacted, NO trading.

Official Alpaca documentation says Paper-Only accounts are entitled to IEX
data and may run algorithms in the Alpaca PAPER environment. That statement
does not attest THIS account's agreement, eligibility for redistribution or
non-display automated consumption by an independently simulated local broker.

The exact paper-only URL is deliberately NOT the live trading hostname. This
check never submits/cancels orders, mutates a paper account or publishes market
prices. Successful paper authentication is NOT PAPER financial commissioning.
"""
from __future__ import annotations

import argparse
import json
import ssl
import urllib.error
import urllib.request
import uuid

from app.investment.alpaca_iex import Credentials

from scripts.observation_runtime.alpaca_iex_rest_access_probe import _NoRedirect
from scripts.observation_runtime.atlas_r16_alpaca_iex_rest_probe import (
    CONFIG,
    require_selected_r16_data_only,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)

SCHEMA = "ATLAS_R16_ALPACA_PAPER_IDENTITY_READONLY_V1"
SCOPE = "R16_ALPACA_PAPER_ACCOUNT_GET_ONLY_NO_ORDERS"
ACCOUNT_URL = "https://paper-api.alpaca.markets/v2/account"
MAX_BYTES = 32768
DOCS = (
    "https://docs.alpaca.markets/us/docs/paper-trading",
    "https://docs.alpaca.markets/us/v1.4.2/docs/about-market-data-api",
)


def no_grant():
    return {
        "schema": SCHEMA,
        "provider": "ALPACA",
        "paper_api_url": ACCOUNT_URL,
        "public_documentation_paper_iex_algo_support": True,
        "documentation": list(DOCS),
        "quotes_or_account_numbers_exposed": False,
        "credentials_exposed": False,
        "paper_account_values_exposed": False,
        "live_api_host_contacted": False,
        "orders_sent": 0,
        "account_modifications": 0,
        "provider_market_data_entitlement_independently_verified": False,
        "account_specific_terms_and_redistribution_rights_independently_verified": False,
        "continuous_source_accepted": False,
        "financial_writer_roles_enrolled": 0,
        "financial_operating_gates_accepted": 0,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }


def interpret_paper_account(data):
    """Validate account identity privately; return only nonidentifying flags."""
    if type(data) is not dict:
        raise ValueError("R16_ALPACA_PAPER_ACCOUNT_JSON_OBJECT_REQUIRED")
    ident, status, currency = data.get("id"), data.get("status"), data.get("currency")
    if (type(ident) is not str
            or type(status) is not str
            or status not in {
                "ACTIVE", "INACTIVE", "PAPER_ONLY", "ONBOARDING",
                "APPROVED", "ACCOUNT_UPDATED", "ACTION_REQUIRED", "LIMITED",
                "ACCOUNT_CLOSED", "REJECTED",
            }
            or currency != "USD"):
        raise ValueError("R16_ALPACA_PAPER_ACCOUNT_IDENTITY_SHAPE_REQUIRED")
    try:
        if str(uuid.UUID(ident)) != ident.lower():
            raise ValueError
    except (ValueError, AttributeError):
        raise ValueError("R16_ALPACA_PAPER_UUID_REQUIRED") from None
    # Never return id, account number, balances, positions, address, fees,
    # provider response headers, or its original JSON payload.
    return {
        "paper_trading_api_authenticated": True,
        "paper_account_status_suitable_for_data_research":
            status in {"ACTIVE", "PAPER_ONLY"},
        "paper_account_identity_shape_verified": True,
        "paper_data_endpoint_authenticated_in_this_check": False,
    }


def inspect():
    selected = require_selected_r16_data_only()
    roots = inspect_two_lane_native_roots()
    return {
        **no_grant(),
        "status": "R16_PAPER_ACCOUNT_READONLY_PRECHECK_NO_NETWORK",
        "selected_r16_code_only": selected["code_selection_accepted"],
        "original_native_roots_empty": roots["all_twelve_distinct_and_empty"],
        "credentials_file_present_unread":
            CONFIG.is_file() and not CONFIG.is_symlink() and not CONFIG.is_junction(),
        "network_requests": 0,
        "paper_trading_api_authenticated": False,
        "paper_account_status_suitable_for_data_research": False,
    }


def probe(*, confirmed_scope, credentials_reader=Credentials.load, opener=None):
    if confirmed_scope != SCOPE:
        raise ValueError("R16_EXACT_PAPER_READONLY_SCOPE_REQUIRED")
    selected_before = require_selected_r16_data_only()
    roots_before = inspect_two_lane_native_roots()
    if (roots_before.get("native_root_total") != 12
            or roots_before.get("all_twelve_distinct_and_empty") is not True
            or not CONFIG.is_file() or CONFIG.is_symlink() or CONFIG.is_junction()):
        raise ValueError("R16_PAPER_READONLY_ORIGINAL_NATIVE_ROOTS_AND_CONFIG_REQUIRED")
    creds = credentials_reader(CONFIG)
    if type(creds) is not Credentials:
        raise ValueError("R16_PAPER_READONLY_DATA_ONLY_CREDENTIALS_REQUIRED")
    if opener is None:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            _NoRedirect(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        )
    request = urllib.request.Request(
        ACCOUNT_URL, method="GET",
        headers={
            "APCA-API-KEY-ID": creds.key,
            "APCA-API-SECRET-KEY": creds.secret,
            "Accept": "application/json",
            "User-Agent": "Atlas-R16-PaperAccount-Identity-ReadOnly/1.0",
        })
    with opener.open(request, timeout=8) as response:
        if (response.status != 200 or response.geturl() != ACCOUNT_URL
                or response.headers.get_content_type() != "application/json"):
            raise ValueError("R16_PAPER_READONLY_EXACT_HTTPS_JSON_200_REQUIRED")
        raw = response.read(MAX_BYTES + 1)
        if not 0 < len(raw) <= MAX_BYTES:
            raise ValueError("R16_PAPER_READONLY_BOUNDED_RESPONSE_REQUIRED")
    packet = json.loads(raw)
    result = interpret_paper_account(packet)
    # Restore original strong native evidence after external provider I/O.
    selected_after = require_selected_r16_data_only()
    roots_after = inspect_two_lane_native_roots()
    if selected_after != selected_before or roots_after != roots_before:
        raise ValueError("R16_PAPER_READONLY_SELECTED_OR_ROOT_DRIFT")
    return {
        **no_grant(),
        **result,
        "status": (
            "R16_PAPER_ACCOUNT_API_AUTHENTICATED_RESEARCH_SCOPE_ONLY"
            if result["paper_account_status_suitable_for_data_research"]
            else "R16_PAPER_ACCOUNT_AUTHENTICATED_STATUS_NOT_SUITABLE"
        ),
        "network_requests": 1,
        "method": "GET",
        "native_financial_roots_unmodified": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--execute-readonly", action="store_true")
    parser.add_argument("--confirm-scope")
    args = parser.parse_args(argv)
    if args.inspect:
        if args.confirm_scope is not None:
            return 2
        print(json.dumps(inspect(), sort_keys=True))
        return 0
    try:
        safe = probe(confirmed_scope=args.confirm_scope)
        print(json.dumps(safe, sort_keys=True))
        return 0 if safe["paper_account_status_suitable_for_data_research"] else 2
    except (ValueError, OSError, TypeError, KeyError, UnicodeError,
            TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        print(json.dumps({
            **no_grant(),
            "status": "R16_PAPER_ACCOUNT_READONLY_REFUSED",
            "paper_trading_api_authenticated": False,
            "network_request_count_verified": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
