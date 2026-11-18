"""One bounded Alpaca IEX latest-quote REST check, data-only and fail-closed.

Separate transport capability from *current* execution prices, continuous
feed rights, independent contract entitlements, and actual PAPER authority.
Never persists, exposes, or uses prices to authorize a simulated fill.

--inspect performs no credential or provider I/O. The ONLY network mode
requires the exact data-only scope and verifies the selected R15 source,
local ALPACA_TRADING_ENABLED=false, pinned data HTTPS host, one stock symbol,
one GET, no redirects, a bounded response, and no retries.
"""
import argparse
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from app.investment.alpaca_iex import Credentials

from scripts.observation_runtime.alpaca_iex_probe import (
    SCOPE,
    inspect_selected_data_only,
)

SCHEMA = "ATLAS_IEX_REST_SINGLE_LATEST_DATA_ONLY_ACCESS_V1"
SYMBOL = re.compile(r"[A-Z][A-Z0-9.-]{0,14}\Z")
DATA_BASE = "https://data.alpaca.markets/v2/stocks/"
ROOT = Path(__file__).resolve().parents[2]
LIMIT = 8192
MAX_AGE_SECONDS = 5


def _no_financial_grant():
    return {
        "provider": "ALPACA", "feed": "IEX",
        "single_exchange_not_nbbo": True,
        "independent_contract_license_verified": False,
        "continuous_quote_delivery_verified": False,
        "native_qualified_source_issuer_enrolled": False,
        "market_quotes_for_execution_authorized": False,
        "financial_operating_gate_accepted": False,
        "paper_start_authorized": False, "live_trading_authorized": False,
        "account_files_written": 0, "paper_orders_created": 0,
        "real_money_orders_created": 0,
    }


def interpret_latest(payload, *, symbol, observed_at):
    """Pure sanitized metadata; does not return raw quotes or prices."""
    if (type(symbol) is not str or SYMBOL.fullmatch(symbol) is None
            or type(observed_at) is not int or observed_at <= 0
            or type(payload) is not dict or set(payload) != {"quote", "symbol"}
            or payload["symbol"] != symbol
            or type(payload["quote"]) is not dict
            or type(payload["quote"].get("t")) is not str):
        raise ValueError("IEX_REST_EXACT_SYMBOL_AND_QUOTE_REQUIRED")
    try:
        stamp = datetime.fromisoformat(payload["quote"]["t"].replace("Z","+00:00"))
        if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
            raise ValueError
        micros = int(stamp.timestamp() * 1_000_000)
        if micros <= 0:
            raise ValueError
    except (ValueError,OverflowError,OSError):
        raise ValueError("IEX_REST_UTC_QUOTE_TIMESTAMP_REQUIRED") from None
    age = observed_at - micros / 1_000_000
    # A diagnostic is permitted to see a stale or future-dated payload:
    # neither can be accepted for executable PAPER quotes.
    fresh = 0 <= age <= MAX_AGE_SECONDS
    return {
        "schema": SCHEMA,
        "status": ("LATEST_IEX_QUOTE_TIMESTAMP_FRESH_NOT_FINANCIAL_ACCEPTANCE"
                   if fresh else
                   "LATEST_IEX_QUOTE_TIMESTAMP_STALE_OR_UNCERTAIN"),
        "symbol": symbol,
        "http_data_endpoint_responded": True,
        "latest_quote_timestamp_present": True,
        "reported_quote_age_seconds": round(age),
        "quote_timestamp_within_five_seconds_of_UNQUALIFIED_host_clock": fresh,
        "diagnostic_host_clock_is_not_independent_financial_utc": True,
        "raw_bid_ask_prices_exposed": False,
        **_no_financial_grant(),
    }


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def probe(*, symbol, confirmed_scope, credential_path=None, now=None,
          opener=None, credential_reader=Credentials.load):
    if (confirmed_scope != SCOPE or type(symbol) is not str
            or SYMBOL.fullmatch(symbol) is None):
        raise ValueError("IEX_REST_EXPLICIT_EXACT_DATA_ONLY_SCOPE_REQUIRED")
    selected = inspect_selected_data_only()
    # Original R15 remains inspectable only if genuinely selected. The
    # latest code-only native revision 22 is now supported by the same
    # read-only, no-financial-authority source/installed-image preflight.
    if (selected.get("selected_revision") not in (14, 22)
            or selected.get("trading_authorized") is not False
            or selected.get("provider_rights_independently_accepted") is not False):
        raise ValueError("IEX_REST_SELECTED_R15_NONFINANCIAL_SCOPE_REQUIRED")
    path = ROOT / "config/alpaca.env"
    if credential_path is not None and Path(credential_path) != path:
        raise ValueError("IEX_REST_LOCAL_EXACT_CONFIG_PATH_REQUIRED")
    # This credentials loader already requires ALPACA_TRADING_ENABLED=false.
    credentials = credential_reader(path)
    if not isinstance(credentials,Credentials):
        raise ValueError("IEX_REST_VALIDATED_DATA_ONLY_CREDENTIALS_REQUIRED")
    url = DATA_BASE + symbol + "/quotes/latest?feed=iex"
    if opener is None:
        opener = urllib.request.build_opener(_NoRedirect(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    request = urllib.request.Request(
        url,method="GET",
        headers={"APCA-API-KEY-ID":credentials.key,
                 "APCA-API-SECRET-KEY":credentials.secret,
                 "Accept":"application/json",
                 "User-Agent":"Atlas-DataOnly-IEX-REST/1.0"})
    with opener.open(request,timeout=8) as response:
        if (response.status != 200 or response.geturl() != url
                or response.headers.get_content_type() != "application/json"):
            raise ValueError("IEX_REST_UNEXPECTED_STATUS_REDIRECT_OR_CONTENT")
        raw = response.read(LIMIT+1)
        if len(raw) > LIMIT:
            raise ValueError("IEX_REST_RESPONSE_TOO_LARGE")
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError,UnicodeError):
        raise ValueError("IEX_REST_JSON_RESPONSE_REQUIRED") from None
    observed_at = int(time.time()) if now is None else now
    return interpret_latest(payload,symbol=symbol,observed_at=observed_at)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--inspect",action="store_true")
    group.add_argument("--execute-data-only",action="store_true")
    parser.add_argument("--confirm-scope")
    parser.add_argument("--symbol",default="MSFT")
    args=parser.parse_args(argv)
    if args.inspect:
        if args.confirm_scope is not None:
            print(json.dumps({"status":"REFUSED","reason":"SCOPE_ONLY_ON_EXECUTION"}))
            return 2
        print(json.dumps({
            "schema":SCHEMA,"status":"OFFLINE_DATA_ONLY_REQUIRES_EXPLICIT_APPROVAL",
            "credentials_read":False,"network_called":False,**_no_financial_grant(),
        },sort_keys=True))
        return 0
    try:
        result=probe(symbol=args.symbol,confirmed_scope=args.confirm_scope)
        print(json.dumps(result,sort_keys=True))
        return 0
    except (ValueError,OSError,TimeoutError,urllib.error.URLError,
            UnicodeError,TypeError,KeyError):
        # Never emit credentials, URLs with tokens, raw prices, or exception
        # messages from the remote data endpoint.
        print(json.dumps({"schema":SCHEMA,"status":"DATA_ONLY_ENDPOINT_REFUSED",
                          **_no_financial_grant()},sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
