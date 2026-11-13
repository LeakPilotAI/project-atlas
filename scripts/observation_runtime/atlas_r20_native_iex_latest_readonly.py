"""R20 selected native Alpaca IEX latest-quote REST transport audit, READ ONLY.

This can run only inside an original selected Job owner with an active selected
two-peer NTP clock. It uses the installed Credentials loader to require
ALPACA_TRADING_ENABLED=false, the pinned data HTTPS origin, at most four GETs,
no retries and no redirects. It never returns a raw price, secret or URL, and
never treats a stale/closed-market quote as an executable PAPER market quote.
External issuer authentication and provider license are NOT proven by API access.
"""
from __future__ import annotations

import inspect
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.investment.alpaca_iex import Credentials, IEXFeed

from scripts.observation_runtime.personal_native_selected_owned_job_preflight import (
    RetainedSelectedNativeOwnerPreflight,
)
from scripts.observation_runtime.personal_version_safe_release_clock import (
    NativeVersionSafePaperOperatorClock,
    require_version_safe_release_digest,
)

SCHEMA = "ATLAS_R20_NATIVE_IEX_LATEST_NTP_OWNED_READONLY_V1"
BASE = "https://data.alpaca.markets/v2/stocks/"
EXACT = re.compile(r"[A-Z][A-Z0-9.-]{0,14}\Z")
WATCHLIST = ("MSFT", "AVGO", "SCHD", "VTI")
MAX_BYTES = 8192
MAX_GETS = 4


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _price(value):
    if type(value) not in (Decimal, int):
        raise ValueError("IEX_NATIVE_DECIMAL_PRICE_REQUIRED")
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError):
        raise ValueError("IEX_NATIVE_DECIMAL_PRICE_REQUIRED") from None
    # Alpaca explicitly represents no active IEX bid or ask with numeric 0.
    # It is source transport evidence only, NEVER a viable execution quote.
    if not result.is_finite() or result < 0:
        raise ValueError("IEX_NATIVE_NONNEGATIVE_FINITE_PRICE_REQUIRED")
    return result


def inspect_quote(payload, *, symbol, observed_ns):
    """Sanitized provider quote metadata at an independently sampled UTC instant."""
    if (type(symbol) is not str or EXACT.fullmatch(symbol) is None
            or type(observed_ns) is not int or observed_ns <= 0
            or type(payload) is not dict or set(payload) != {"symbol", "quote"}
            or payload["symbol"] != symbol or type(payload["quote"]) is not dict):
        raise ValueError("IEX_NATIVE_EXACT_QUOTE_ENVELOPE_REQUIRED")
    quote = payload["quote"]
    if any(type(quote.get(k)) is not int or not 0 <= quote[k] <= 10**9
           for k in ("bs", "as")):
        raise ValueError("IEX_NATIVE_SHARE_SIZES_MALFORMED")
    bid, ask = _price(quote.get("bp")), _price(quote.get("ap"))
    # On IEX, a completely absent side may have zero price/size and no
    # active exchange identity; that is never an executable quote. Require V
    # for EVERY nonzero-priced side, and reject all foreign executable sides.
    if (bid > 0 and quote.get("bx") != "V"
            or ask > 0 and quote.get("ax") != "V"):
        raise ValueError("IEX_NATIVE_POSITIVE_SIDE_EXCHANGE_NOT_IEX")
    # Nonzero crossed prices are invalid; a zero on either side means absent
    # orders, never evidence of liquidity to simulate a fill.
    if bid > 0 and ask > 0 and bid > ask:
        raise ValueError("IEX_NATIVE_CROSSED_QUOTE_REFUSED")
    active = bool(bid > 0 and ask > 0
                  and quote["bs"] > 0 and quote["as"] > 0)
    timestamp = quote.get("t")
    if type(timestamp) is not str or not timestamp.endswith("Z"):
        raise ValueError("IEX_NATIVE_PROVIDER_UTC_TIMESTAMP_REQUIRED")
    try:
        event = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("IEX_NATIVE_PROVIDER_UTC_TIMESTAMP_REQUIRED") from None
    if event.tzinfo is None or event.utcoffset().total_seconds() != 0:
        raise ValueError("IEX_NATIVE_PROVIDER_UTC_TIMESTAMP_REQUIRED")
    unix_ns = (int(event.timestamp()) * 1_000_000_000
               + event.microsecond * 1000)
    age_ns = observed_ns - unix_ns
    # Even with validated transport, IEX has single-venue coverage and the
    # weekend/out-of-session result must remain a stale research observation.
    fresh = 0 <= age_ns <= 5_000_000_000
    return {
        "symbol": symbol,
        "provider_exchange": "IEX",
        "source_age_seconds": age_ns // 1_000_000_000,
        "bid_and_ask_present": active,
        "missing_one_or_both_sided_executable_quote": not active,
        "share_sizes_valid": True,
        "provider_quote_fresh_at_sample": fresh,
        "executable_paper_quote_authorized": False,
    }


def _decode_response(response, url):
    if (response.status != 200 or response.geturl() != url
            or response.headers.get_content_type() != "application/json"):
        raise ValueError("IEX_NATIVE_HTTP_STATUS_REDIRECT_OR_TYPE_REFUSED")
    raw = response.read(MAX_BYTES + 1)
    if not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("IEX_NATIVE_HTTP_RESPONSE_BOUNDS_REFUSED")
    def unique(fields):
        result = {}
        for key, value in fields:
            if key in result:
                raise ValueError("IEX_NATIVE_DUPLICATE_PROVIDER_FIELD")
            result[key] = value
        return result
    try:
        return json.loads(
            raw, parse_float=Decimal,
            object_pairs_hook=unique,
            parse_constant=lambda _:
                (_ for _ in ()).throw(ValueError("IEX_NATIVE_NONFINITE_NUMBER")),
        )
    except (ValueError, TypeError, UnicodeError):
        raise ValueError("IEX_NATIVE_JSON_NOT_ACCEPTED") from None


def _installed_ports(*, release):
    """Reject workspace/unselected quote, clock, owner, or credential classes."""
    expected = {
        IEXFeed: release / "backend/app/investment/alpaca_iex.py",
        RetainedSelectedNativeOwnerPreflight:
            release / "scripts/observation_runtime/personal_native_selected_owned_job_preflight.py",
        NativeVersionSafePaperOperatorClock:
            release / "scripts/observation_runtime/personal_version_safe_release_clock.py",
    }
    if (release.parent != Path("D:/AtlasRuntime/releases").resolve()
            or any(Path(inspect.getfile(cls)).resolve() != path.resolve()
                   for cls, path in expected.items())):
        raise ValueError("IEX_NATIVE_INSTALLED_SELECTED_PORTS_REQUIRED")


def _required_data_only_config():
    path = Path("D:/Work/Project Atlas/config/alpaca.env")
    if (not path.is_file() or path.is_symlink() or path.is_junction()
            or not 0 < path.stat().st_size <= 8192):
        raise ValueError("IEX_NATIVE_BOUND_DATA_ONLY_CREDENTIAL_FILE_REQUIRED")
    return path


def audit_owned_iex(*, owner, clock, runtime_id, release_digest,
                    symbols=WATCHLIST, opener=None, credential_reader=None):
    if (type(symbols) is not tuple or not 1 <= len(symbols) <= MAX_GETS
            or len(set(symbols)) != len(symbols)
            or any(type(s) is not str or s not in WATCHLIST for s in symbols)):
        raise ValueError("IEX_NATIVE_EXPLICIT_BOUNDED_WATCHLIST_REQUIRED")
    release = Path(sys.executable).resolve().parent.parent
    _installed_ports(release=release)
    if (type(owner) is not RetainedSelectedNativeOwnerPreflight
            or type(clock) is not NativeVersionSafePaperOperatorClock
            or type(runtime_id) is not str or not runtime_id
            or owner._phase != "PREINCEPTION"
            or owner.verify_still_running() is not True
            or clock.require_operational(runtime_id) is not clock
            or require_version_safe_release_digest(
                clock=clock, runtime_id=runtime_id,
                release_digest=release_digest,
            ) is not True):
        raise ValueError("IEX_NATIVE_ORIGINAL_JOB_CLOCK_OR_SELECTED_RELEASE_REQUIRED")
    path = _required_data_only_config()
    reader = credential_reader or Credentials.load
    credentials = reader(path)
    if type(credentials) is not Credentials:
        raise ValueError("IEX_NATIVE_ORIGINAL_DATA_CREDENTIALS_REQUIRED")
    if opener is None:
        opener = urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPSHandler(
                context=ssl.create_default_context(),
            ),
        )
    rows = []
    for symbol in symbols:
        if owner.verify_still_running() is not True:
            raise ValueError("IEX_NATIVE_ORIGINAL_JOB_REVOKED_BEFORE_GET")
        clock.require_operational(runtime_id)
        url = BASE + symbol + "/quotes/latest?feed=iex"
        request = urllib.request.Request(
            url, method="GET", headers={
                "APCA-API-KEY-ID": credentials.key,
                "APCA-API-SECRET-KEY": credentials.secret,
                "Accept": "application/json",
                "User-Agent": "Atlas-R20-Owned-IEX-DataOnly/1.0",
            },
        )
        try:
            with opener.open(request, timeout=8) as response:
                packet = _decode_response(response, url)
        except urllib.error.HTTPError:
            raise ValueError("IEX_NATIVE_HTTP_AUTH_OR_ENTITLEMENT_REFUSED") from None
        except urllib.error.URLError:
            raise ValueError("IEX_NATIVE_NETWORK_OR_TLS_UNAVAILABLE") from None
        s = clock.sample()
        if (not clock.verify(s)
                or owner.verify_still_running() is not True):
            raise ValueError("IEX_NATIVE_POST_GET_UTC_JOB_REVOKED")
        rows.append(inspect_quote(
            packet, symbol=symbol,
            observed_ns=s["utc"] * 1_000_000_000,
        ))
    if owner.verify_still_running() is not True:
        raise ValueError("IEX_NATIVE_ORIGINAL_JOB_CHANGED_AT_END")
    fresh = sum(row["provider_quote_fresh_at_sample"] for row in rows)
    present = sum(row["bid_and_ask_present"] for row in rows)
    recent_and_sided = sum(
        row["provider_quote_fresh_at_sample"] and row["bid_and_ask_present"]
        for row in rows
    )
    return {
        "schema": SCHEMA,
        "status": (
            "LATEST_QUOTES_HAVE_MISSING_IEX_SIDES_DATA_ONLY"
            if present != len(rows)
            else "ALL_LATEST_QUOTES_RECENT_DATA_ONLY"
            if fresh == len(rows)
            else "PROVIDER_REACHABLE_BUT_NOT_ALL_QUOTES_CURRENT_DATA_ONLY"
        ),
        "selected_original_windows_job_verified": True,
        "two_peer_independent_utc_observed": True,
        "provider_rest_authentication_observed": True,
        "single_exchange_not_nbbo": True,
        "http_get_count": len(rows),
        "requested_symbols": list(symbols),
        "fresh_quote_count": fresh,
        "stale_or_not_current_quote_count": len(rows) - fresh,
        "both_sided_quote_count": present,
        "missing_quote_side_count": len(rows) - present,
        "fresh_and_both_sided_source_only_count": recent_and_sided,
        "quotes": rows,
        "provider_data_rights_independently_accepted": False,
        "authenticated_operational_research_issuer_accepted": False,
        "financial_quote_admission_accepted": False,
        "market_session_verified": False,
        "financial_inception_authorized": False,
        "paper_startup_authorized": False,
        "live_trading_authorized": False,
    }
