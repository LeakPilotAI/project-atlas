"""Selected R14 bounded Hyperliquid public BTC/ETH/SOL L2-book evidence.

Offline inspect performs no socket/clock/provider/account writes. One explicit
data-only execute requires a previously enrolled durable 12-request budget
with >=2 remaining; never creates/replaces/resets it. Actual two HTTP info
calls are gated and use real independent NTP for observation timing. All
samples remain nonfinancial public evidence, not PAPER execution rights.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import httpx
from decimal import Decimal, InvalidOperation
from pathlib import Path

from scripts.observation_runtime.atlas_r14_selected_paper_readiness import (
    collect_selected_reference,
)
from scripts.observation_runtime.atlas_r14_two_lane_source_preflight import (
    selected_contracts,
)
from scripts.observation_runtime.hyperliquid_native_preflight import inspect as inventory
from app.personal_paper import DEFAULT_HYPERLIQUID_BUDGET
from app.adapters import hyperliquid_gate_registry
from app.adapters.hyperliquid import HyperliquidAdapter, HyperliquidPublicBookAdmissionRefused
from app.adapters.hyperliquid_request_gate import (
    HyperliquidRequestGate, RequestGateRefused,
)
from scripts.observation_runtime.atlas_independent_ntp_clock import (
    IndependentNtpClock, SOURCE as CLOCK_SOURCE,
)

SCOPE = "HYPERLIQUID_TWO_PUBLIC_INFO_REQUESTS_DATA_ONLY_NO_TRADING"
SYMBOLS = ("BTC", "ETH", "SOL")
BUDGET = Path(DEFAULT_HYPERLIQUID_BUDGET)
MAX_ATTEMPTS = 12
MAX_HTTP_ATTEMPTS = 2
HTTP_DEADLINE_SECONDS = 25


def read_enrolled_budget():
    """Existing source ledger only. Never creates a budget or opens rw."""
    state = inventory(budget_path=BUDGET)
    if state.get("request_budget_inventory") != (
        "EXISTING_LEDGER_STRUCTURE_VALID_NOT_AUTHORIZED"
    ):
        return {"status":"MISSING_OR_UNVERIFIED", "remaining":None}
    if not BUDGET.is_file() or BUDGET.is_symlink() or BUDGET.is_junction():
        raise ValueError("R14_HL_EXISTING_ORDINARY_BUDGET_REQUIRED")
    with sqlite3.connect(BUDGET.resolve().as_uri()+"?mode=ro",uri=True,timeout=1) as db:
        rows = db.execute("SELECT max_attempts,attempted FROM budget WHERE id=1").fetchall()
    if (len(rows)!=1 or type(rows[0][0]) is not int
            or type(rows[0][1]) is not int
            or rows[0][0]!=MAX_ATTEMPTS
            or not 0<=rows[0][1]<=MAX_ATTEMPTS):
        raise ValueError("R14_HL_EXISTING_REQUEST_BUDGET_CORRUPT")
    return {"status":"EXISTING_UNAUTHORIZED_RESEARCH_BUDGET",
            "remaining":MAX_ATTEMPTS-rows[0][1]}


def inspect():
    selected = collect_selected_reference()
    contracts = selected_contracts()
    if (selected.get("revision") != 13
            or selected.get("native_selection_record_verified") is not True
            or selected.get("financial_authority") is not False
            or "backend/app/services/personal_hyperliquid_public_data.py" not in contracts):
        raise ValueError("R14_HL_SELECTED_RUNTIME_NOT_VERIFIED")
    budget=read_enrolled_budget()
    return {
        "schema":"ATLAS_SELECTED_R14_HL_PUBLIC_BOOK_PREFLIGHT_V1",
        "decision":"REQUIRES_EXPLICIT_DATA_ONLY_SCOPE",
        "selected_code_revision":13,
        "selected_code_release":selected["selected_release"],
        "selected_code_verified":True,
        "allowed_symbols":list(SYMBOLS),
        "public_info_requests_per_probe":MAX_HTTP_ATTEMPTS,
        "total_durable_budget":MAX_ATTEMPTS,
        "existing_request_budget":budget,
        "independent_two_peer_time_required":True,
        "provider_connection_opened":False,
        "private_account_accessed":False,
        "order_endpoint_used":False,
        "market_book_observed":False,
        "provider_rights_independently_accepted":False,
        "continuous_executable_prices_verified":False,
        "financial_execution_authorized":False,
        "paper_startup_authorized":False,
        "live_trading_authorized":False,
    }


def require_execute_scope(*, mode, scope, symbol):
    if (mode is not True or scope != SCOPE
            or type(symbol) is not str or symbol not in SYMBOLS):
        raise ValueError("R14_HL_EXPLICIT_TWO_REQUEST_PUBLIC_ONLY_SCOPE_REQUIRED")
    return symbol


def admit_public_book(book, symbol):
    """Accept validated data transport, never financial authority."""
    if (type(book) is not dict
            or book.get("schema") != "ATLAS_HYPERLIQUID_PUBLIC_BOOK_V1"
            or book.get("symbol") != symbol
            or book.get("timestamp_basis") != "PROVIDER_BOOK_MS"
            or book.get("market_book_validated") is not True
            or book.get("financial_execution_authorized") is not False
            or book.get("startup_authorized") is not False
            or book.get("funding_settlement") is not None
            or book.get("historical_settlement_oracle") is not None
            or book.get("fee_schedule") is not None):
        raise ValueError("R14_HL_PUBLIC_BOOK_SCOPE_OR_FRESHNESS_REFUSED")
    started=book.get("request_started_ms")
    observed=book.get("observed_at_ms")
    published=book.get("book_timestamp_ms")
    if (type(started) is not int or type(observed) is not int
            or type(published) is not int or started<=0
            or not started<=published<=observed
            or observed-published>5000 or observed-started>10000):
        raise ValueError("R14_HL_PUBLIC_BOOK_TIMESTAMP_BOUNDS_REFUSED")
    try:
        values = {key:Decimal(book[key]) for key in (
            "bid","ask","bid_size","ask_size","mark","oracle")}
    except (InvalidOperation,KeyError,TypeError):
        raise ValueError("R14_HL_PUBLIC_BOOK_FINITE_DECIMALS_REQUIRED") from None
    if (any(type(book[key]) is not str or not value.is_finite()
            or value<=0 for key,value in values.items())
            or values["ask"]<=values["bid"]):
        raise ValueError("R14_HL_PUBLIC_BOOK_POSITIVE_UNCROSSED_REQUIRED")
    return {
        "schema":"ATLAS_R14_HL_PUBLIC_BOOK_DATA_ONLY_SAMPLE_V1",
        "status":"BOUNDED_TWO_REQUEST_PUBLIC_BOOK_OBSERVED_NOT_FINANCIAL_AUTHORITY",
        "symbol":symbol,
        "bid":book["bid"],"ask":book["ask"],
        "bid_size":book["bid_size"],"ask_size":book["ask_size"],
        "mark":book["mark"],"oracle":book["oracle"],
        "provider_book_timestamp_ms":book["book_timestamp_ms"],
        "observed_at_ms":book["observed_at_ms"],
        "independent_clock_source":CLOCK_SOURCE,
        "provider_book_validated":True,
        "provider_data_continuity_verified":False,
        "provider_rights_independently_accepted":False,
        "actual_financial_writer_enrolled":False,
        "paper_order_authorized":False,
        "live_order_authorized":False,
        "automatic_startup_authorized":False,
    }


def independent_utc_ms(clock):
    """Derive milliseconds from the already verified independent NTP anchor.

    The public clock sample's UTC is deliberately whole seconds; using only
    that for provider-book timestamps creates artificial future-book refusals.
    This never reads Windows wall time or provides financial clock authority.
    """
    if type(clock) is not IndependentNtpClock:
        raise ValueError("R14_HL_REAL_INDEPENDENT_NTP_CLOCK_REQUIRED")
    sample=clock.sample()
    anchor=clock._anchor
    if (type(sample) is not dict or sample.get("source") != CLOCK_SOURCE
            or type(sample.get("utc")) is not int
            or type(sample.get("monotonic_ns")) is not int
            or type(anchor) is not dict
            or type(anchor.get("mono_ns")) is not int
            or type(anchor.get("utc_ns")) is not int
            or sample["monotonic_ns"] < anchor["mono_ns"]):
        raise ValueError("R14_HL_INDEPENDENT_UTC_MILLISECOND_ANCHOR_REFUSED")
    milliseconds=(anchor["utc_ns"] + sample["monotonic_ns"]
                  - anchor["mono_ns"])//1_000_000
    if milliseconds//1000 != sample["utc"]:
        raise ValueError("R14_HL_INDEPENDENT_UTC_MILLISECOND_MISMATCH")
    return milliseconds


async def _perform_two_requests(symbol, clock, identity, gate):
    adapter=HyperliquidAdapter()
    try:
        clock.require_operational(identity)
        await adapter.connect_http_only()
        clock.require_operational(identity)
        return await asyncio.wait_for(
            adapter.paper_execution_observation(
                symbol,clock_ms=lambda:independent_utc_ms(clock)
            ), timeout=HTTP_DEADLINE_SECONDS)
    finally:
        await adapter.close()


def execute_data_only(*, symbol, confirm_scope):
    require_execute_scope(mode=True,scope=confirm_scope,symbol=symbol)
    snapshot=inspect()
    if (snapshot["selected_code_release"]
            != "7ff9d3dba2eabe110f843c13efac49464805de2a"
            or snapshot["existing_request_budget"]["remaining"] is None
            or snapshot["existing_request_budget"]["remaining"] < MAX_HTTP_ATTEMPTS):
        raise ValueError("R14_HL_TWO_REQUEST_ENROLLED_BUDGET_NOT_AVAILABLE")
    # The exact CLI confirmation means data-only authorization, not finance
    # or unlimited provider request rights. Never reset the existing budget.
    gate=HyperliquidRequestGate(BUDGET,rights_approved=True,budget_approved=True,
                      max_attempts=MAX_ATTEMPTS)
    if gate.remaining()<MAX_HTTP_ATTEMPTS:
        raise ValueError("R14_HL_TWO_REQUEST_BUDGET_ALREADY_CONSUMED")
    hyperliquid_gate_registry.install_gate(gate)
    identity="atlas-r14-hl-public-book-"+symbol.lower()+"-data-only"
    clock=IndependentNtpClock(runtime_id=identity)
    if type(clock) is not IndependentNtpClock:
        raise ValueError('R14_HL_REAL_INDEPENDENT_NTP_CLOCK_REQUIRED')
    try:
        clock.require_operational(identity)
        book=asyncio.run(_perform_two_requests(symbol,clock,identity,gate))
        clock.require_operational(identity)
        return admit_public_book(book,symbol)
    finally:
        clock.revoke()


_SAFE_BOOK_REFUSALS = frozenset({
    "SYMBOL_NOT_ALLOWLISTED",
    "OBSERVATION_CLOCK_TYPE",
    "OBSERVATION_CLOCK_REVERSED",
    "OBSERVATION_DURATION_EXCEEDED",
    "METADATA_ENVELOPE",
    "METADATA_PART_TYPES",
    "BOOK_ENVELOPE",
    "BOOK_COIN_MISMATCH",
    "BOOK_TIMESTAMP_TYPE",
    "BOOK_TIMESTAMP_FUTURE",
    "BOOK_TIMESTAMP_STALE",
})


def safe_refusal_code(error):
    """Classify only fixed, reviewed tokens; never emit raw provider content."""
    if isinstance(error, RequestGateRefused):
        return "HL_REQUEST_BUDGET_OR_GATE_REFUSED"
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return "HL_PUBLIC_HTTP_TIMEOUT"
    if isinstance(error, httpx.HTTPStatusError):
        return "HL_PUBLIC_HTTP_STATUS_REFUSED"
    if isinstance(error, httpx.RequestError):
        return "HL_PUBLIC_TRANSPORT_REFUSED"
    if isinstance(error, HyperliquidPublicBookAdmissionRefused):
        reason = getattr(error, "reason_code", None)
        if type(reason) is str and reason in _SAFE_BOOK_REFUSALS:
            return "HL_PUBLIC_BOOK_" + reason
        return "HL_PUBLIC_BOOK_ADMISSION_REFUSED"
    if isinstance(error, ValueError) and str(error).startswith("NTP_"):
        return "HL_INDEPENDENT_NTP_REFUSED"
    return "HL_SOURCE_OR_DATA_VALIDATION_REFUSED"


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect",action="store_true")
    mode.add_argument("--execute-data-only",action="store_true")
    parser.add_argument("--confirm-scope",default=None)
    parser.add_argument("--symbol",default="BTC")
    args=parser.parse_args(argv)
    if args.inspect:
        if args.confirm_scope is not None:
            print(json.dumps({"status":"REFUSED","financial_execution_authorized":False}))
            return 1
        try:
            print(json.dumps(inspect(),sort_keys=True))
            return 0
        except (ValueError,OSError,sqlite3.Error):
            print(json.dumps({"status":"REFUSED","financial_execution_authorized":False}))
            return 1
    try:
        require_execute_scope(mode=args.execute_data_only,scope=args.confirm_scope,
                              symbol=args.symbol)
        result=execute_data_only(symbol=args.symbol,confirm_scope=args.confirm_scope)
        print(json.dumps(result,sort_keys=True))
        return 0
    except (ValueError,OSError,RuntimeError,sqlite3.Error,TimeoutError,TypeError,httpx.HTTPError) as error:
        print(json.dumps({"status":"REFUSED","reason":safe_refusal_code(error),
                          "financial_execution_authorized":False,
                          "paper_order_authorized":False,"live_order_authorized":False},
                         sort_keys=True))
        return 1


if __name__=="__main__":
    raise SystemExit(main())
