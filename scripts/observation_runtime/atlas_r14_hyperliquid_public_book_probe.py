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
import os
import sqlite3
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx
from app.adapters import hyperliquid_gate_registry
from app.adapters.hyperliquid import (
    HyperliquidAdapter,
    HyperliquidPublicBookAdmissionRefused,
)
from app.adapters.hyperliquid_request_gate import (
    HyperliquidRequestGate,
    RequestGateRefused,
)
from app.personal_paper import DEFAULT_HYPERLIQUID_BUDGET

from scripts.observation_runtime.atlas_independent_ntp_clock import (
    SOURCE as CLOCK_SOURCE,
)
from scripts.observation_runtime.atlas_independent_ntp_clock import (
    IndependentNtpClock,
)
from scripts.observation_runtime.atlas_r14_selected_paper_readiness import (
    collect_selected_reference,
)
from scripts.observation_runtime.atlas_r14_two_lane_source_preflight import (
    selected_contracts,
)
from scripts.observation_runtime.hyperliquid_native_preflight import (
    inspect as inventory,
)

SCOPE = "HYPERLIQUID_TWO_PUBLIC_INFO_REQUESTS_DATA_ONLY_NO_TRADING"
SYMBOLS = ("BTC", "ETH", "SOL")
BUDGET = Path(DEFAULT_HYPERLIQUID_BUDGET)
MAX_ATTEMPTS = 12
MAX_HTTP_ATTEMPTS = 2
HTTP_DEADLINE_SECONDS = 25
R15_SELECTED_ENVELOPE = Path("D:/AtlasRuntime/selection/r0014.json")
R16_SUCCESSOR_RECORD = Path("D:/AtlasRuntime/selection/r0015.json")


def require_legacy_release_still_current():
    """Retire R14/R15 provider calls after R16 selection, even on future budget resets.

    A historic revision-14 record is retained for provenance, NOT proof of
    current selection. Treat even a damaged/junction successor record as a
    terminal refusal; only the separately reviewed R16 source path may probe.
    """
    if os.path.lexists(R16_SUCCESSOR_RECORD):
        raise ValueError("R14_HL_HISTORICAL_RELEASE_NOT_CURRENT_AFTER_R16")
    return True


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
    if os.path.lexists(R16_SUCCESSOR_RECORD):
        # Exact R16 readback, NOT the now-obsolete R15-only selected reader.
        from scripts.observation_runtime.atlas_r16_selected_code_readback import (
            R16_HEAD,
            selected_code,
        )
        current = selected_code()
        if (current.get("selected_revision") != 15
                or current.get("selected_native_head") != R16_HEAD
                or current.get("code_selection_accepted") is not True
                or current.get("paper_start_authorized") is not False):
            raise ValueError("R14_HL_REAL_CURRENT_R16_SELECTED_CODE_REQUIRED")
        return {
            "schema": "ATLAS_R16_HISTORICAL_HL_PROBE_RETIRED_V1",
            "decision": "RETIRED_NOT_CURRENT_NO_PROVIDER_CALL",
            "selected_code_revision": 15,
            "selected_code_release": current["selected_release"],
            "selected_code_verified": True,
            "current_release_executable_for_legacy_probe": False,
            "historical_releases_never_inherit_r16_provider_approval": True,
            "allowed_symbols": list(SYMBOLS),
            "public_info_requests_per_probe": MAX_HTTP_ATTEMPTS,
            "total_durable_budget": MAX_ATTEMPTS,
            "existing_request_budget": read_enrolled_budget(),
            "provider_connection_opened": False,
            "private_account_accessed": False,
            "order_endpoint_used": False,
            "market_book_observed": False,
            "provider_rights_independently_accepted": False,
            "continuous_executable_prices_verified": False,
            "financial_execution_authorized": False,
            "paper_startup_authorized": False,
            "live_trading_authorized": False,
        }
    # An old selected r0013 remains on disk after native R15 selection.
    # Never call an R14-only verifier to decide the CURRENT selected code.
    if R15_SELECTED_ENVELOPE.exists():
        from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
            inspect as inspect_r15,
        )
        selected=inspect_r15()
        codes=selected.get("selected_native_financial_port_sources")
        if (selected.get("schema") != "ATLAS_SELECTED_R15_OFFLINE_FINANCIAL_COMMISSIONING_V1"
                or selected.get("decision") != "NO_GO"
                or selected.get("selected_native_revision") != 14
                or selected.get("selected_code_verified") is not True
                or selected.get("financial_operating_gates_independently_accepted") != 0
                or selected.get("current_hyperliquid_public_book_verified") is not False
                or selected.get("native_hyperliquid_forward_writer_enrolled") is not False
                or selected.get("provider_connection_opened") is not False
                or selected.get("paper_start_authorized") is not False
                or selected.get("live_trading_authorized") is not False
                or type(codes) is not dict
                or codes.get("backend/app/services/personal_hyperliquid_public_data.py",{}).get(
                    "native_installed_source_present") is not True):
            raise ValueError("R15_HL_SELECTED_RUNTIME_NOT_VERIFIED")
        revision=14
        release=selected["selected_code_identity"]["selected_release"]
    else:
        selected = collect_selected_reference()
        contracts = selected_contracts()
        if (selected.get("revision") != 13
                or selected.get("native_selection_record_verified") is not True
                or selected.get("financial_authority") is not False
                or "backend/app/services/personal_hyperliquid_public_data.py" not in contracts):
            raise ValueError("R14_HL_SELECTED_RUNTIME_NOT_VERIFIED")
        revision=13
        release=selected["selected_release"]
    budget=read_enrolled_budget()
    return {
        "schema":("ATLAS_SELECTED_R15_HL_PUBLIC_BOOK_PREFLIGHT_V1" if revision==14
                  else "ATLAS_SELECTED_R14_HL_PUBLIC_BOOK_PREFLIGHT_V1"),
        "decision":"REQUIRES_EXPLICIT_DATA_ONLY_SCOPE",
        "selected_code_revision":revision,
        "selected_code_release":release,
        "selected_code_verified":True,
        "current_release_executable_for_legacy_probe":not os.path.lexists(R16_SUCCESSOR_RECORD),
        "historical_releases_never_inherit_r16_provider_approval":True,
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
    # Reject an obsolete source before inspecting/consuming any durable budget
    # or constructing NTP/provider clients. R16 has its own native selection.
    require_legacy_release_still_current()
    snapshot=inspect()
    expected={13:"7ff9d3dba2eabe110f843c13efac49464805de2a",
              14:"2c79a8d846d6b33669008114732ae5896153812a"}
    if (snapshot.get("selected_code_release") != expected.get(snapshot.get("selected_code_revision"))
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
    # Native selector revision 14 selects software R15 (not R14).
    software_label="r15" if snapshot["selected_code_revision"]==14 else "r14"
    identity="atlas-"+software_label+"-hl-public-book-"+symbol.lower()+"-data-only"
    clock=IndependentNtpClock(runtime_id=identity)
    if type(clock) is not IndependentNtpClock:
        raise ValueError('R14_HL_REAL_INDEPENDENT_NTP_CLOCK_REQUIRED')
    try:
        clock.require_operational(identity)
        book=asyncio.run(_perform_two_requests(symbol,clock,identity,gate))
        clock.require_operational(identity)
        accepted=admit_public_book(book,symbol)
        if snapshot["selected_code_revision"]==14:
            accepted["schema"]="ATLAS_R15_HL_PUBLIC_BOOK_DATA_ONLY_SAMPLE_V1"
            accepted["selected_native_revision"]=14
            accepted["selected_native_release"]=snapshot["selected_code_release"]
        return accepted
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
