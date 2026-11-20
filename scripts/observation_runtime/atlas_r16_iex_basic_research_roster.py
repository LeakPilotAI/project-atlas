"""Current SELECTED R16 Alpaca Basic 30-symbol IEX catalog coverage observation.

One catalog-SHA-bound, explicit nonfinancial WebSocket subscription; 10-35 sec;
1 connection, 0 reconnects. Retains existing QD R12 bounded research planner
for unique symbols and pinned research handles; does NOT claim pins are
financial positions or that a subscription ACK is a current quote.

Actual genuine R16 readback and all twelve EMPTY original account-root
identities precede keys/sockets. Result only contains counts/symbol names.
No raw bid/ask/timestamps, trading endpoints, financial writes or grants.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.investment.alpaca_iex import Credentials,IEXFeed,IEXRefused
from scripts.observation_runtime.alpaca_iex_probe import SCOPE
from scripts.observation_runtime.atlas_r16_alpaca_iex_rest_probe import (
    CONFIG,no_financial_claim,require_selected_r16_data_only,
)
from scripts.observation_runtime.atlas_r12_iex_rotation_plan import (
    CATALOG,MAX_SYMBOLS,plan as plan_roster,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)

SCHEMA="ATLAS_R16_IEX_BASIC_30_SYMBOL_RESEARCH_COVERAGE_V1"
MAX_CATALOG_BYTES=5*1024*1024
MIN_SECONDS=10
MAX_SECONDS=35


def catalog():
    if (not CATALOG.is_file() or CATALOG.is_symlink()
            or CATALOG.is_junction()
            or not 0<CATALOG.stat().st_size<=MAX_CATALOG_BYTES):
        raise ValueError("R16_IEX_CATALOG_ONLY_LOCAL_ORDINARY_SOURCE_REQUIRED")
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def prepare(*,confirmed_scope,offset=0,pins=(),snapshot=None):
    if (confirmed_scope!=SCOPE
            or type(offset) is not int or offset<0
            or type(pins) not in (tuple,list)):
        raise ValueError("R16_IEX_EXPLICIT_RESEARCH_ROSTER_SCOPE_REQUIRED")
    selected=require_selected_r16_data_only()
    roots=inspect_two_lane_native_roots()
    if (selected.get("selected_revision")!=15
            or selected.get("code_selection_accepted") is not True
            or roots.get("native_root_total")!=12
            or roots.get("all_twelve_distinct_and_empty") is not True):
        raise ValueError("R16_IEX_ORIGINAL_FINANCIAL_ROOTS_AND_CODE_REQUIRED")
    report=plan_roster(catalog() if snapshot is None else snapshot,
                       offset=offset,monitored_symbols=pins)
    if (report.get("schema")!="ATLAS_R12_IEX_RESEARCH_OBSERVATION_ROSTER_V1"
            or not 1<=report.get("requested_symbol_count",0)<=MAX_SYMBOLS
            or report.get("requested_symbol_count")!=len(report.get("requested_symbols",[]))
            or report.get("max_iex_websocket_symbols")!=MAX_SYMBOLS
            or report.get("authenticated_iex_connection") is not False
            or report.get("fresh_quote_delivery_verified") is not False
            or any(report.get(k) is not False for k in (
                "full_universe_one_connection_supported",
                "robinhood_brokerage_coverage_verified",
                "provider_rights_accepted","paper_execution_authorized",
                "live_trading_authorized","startup_authorized"))):
        raise ValueError("R16_IEX_EXISTING_FULL_CAPACITY_RESEARCH_PLAN_REQUIRED")
    return report


def sanitize(roster,raw,*,seconds,source_before,source_after,roots_before,roots_after):
    requested=roster["requested_symbols"]
    if (type(raw) is not dict or set(raw)!={
                "per_symbol_quote_diagnostics","authenticated","subscribed",
                "endpoint","feed","reconnects","result","quote_count",
                "fresh_quote_observed_during_connection"}
            or type(source_before) is not dict
            or source_before!=source_after or roots_before!=roots_after
            or roots_after.get("all_twelve_distinct_and_empty") is not True
            or type(seconds) is not int or not MIN_SECONDS<=seconds<=MAX_SECONDS
            or raw.get("authenticated") is not True
            or raw.get("subscribed") is not True
            or raw.get("endpoint")!="wss://stream.data.alpaca.markets/v2/iex"
            or raw.get("feed")!="IEX"
            or raw.get("reconnects")!=0
            or type(raw.get("result")) is not dict
            or raw["result"].get("connection")!="DISCONNECTED"
            or raw["result"].get("paper_startup_authorized") is not False
            or type(raw.get("quote_count")) is not int
            or raw["quote_count"]<0):
        raise ValueError("R16_IEX_RESEARCH_AUTH_ACK_DISCONNECT_REQUIRED")
    diag=raw.get("per_symbol_quote_diagnostics")
    if (type(diag) is not dict or set(diag)!=set(requested)
            or any(type(v) is not dict or set(v)!={
                "received","accepted","rejected","fresh_callbacks"}
                or any(type(z) is not int or z<0 for z in v.values())
                or v["received"]!=v["accepted"]+v["rejected"]
                or v["fresh_callbacks"]!=0 for v in diag.values())):
        raise ValueError("R16_IEX_RESEARCH_PER_SYMBOL_COUNTERS_ONLY_REQUIRED")
    received=sum(v["received"] for v in diag.values())
    accepted=sum(v["accepted"] for v in diag.values())
    rejected=sum(v["rejected"] for v in diag.values())
    observed_count=sum(1 for v in diag.values() if v["accepted"]>0)
    if (raw["quote_count"]!=accepted
            or raw.get("fresh_quote_observed_during_connection") is not
               (observed_count>0)):
        raise ValueError("R16_IEX_RESEARCH_ACCEPTED_QUOTE_TOTAL_CONFLICT")
    return {
        **no_financial_claim(),
        "schema":SCHEMA,
        "status":"R16_AUTHENTICATED_30_SYMBOL_RESEARCH_ACK_NOT_MARKET_COVERAGE",
        "source_release":"R16",
        "catalog_sha256":roster["catalog_sha256"],
        "catalog_total_research_symbols":roster["catalog_count"],
        "catalog_current_as_of_unverified":True,
        "requested_symbols":list(requested),
        "pinned_research_symbols":list(roster["pinned_research_symbols"]),
        "research_offset":roster["offset"],
        "next_research_offset_not_committed":roster["next_offset"],
        "minimum_complete_catalog_subscription_batches":
            roster["minimum_rosters_with_same_pinned_symbols"],
        "websocket_authenticated":True,
        "exact_roster_subscription_acknowledged":True,
        "websocket_closed":True,
        "websocket_connections":1,
        "reconnects":0,
        "observation_seconds":seconds,
        "symbols_requested_count":len(requested),
        "symbols_with_at_least_one_accepted_quote":observed_count,
        "requested_symbols_without_accepted_quote":len(requested)-observed_count,
        "quote_messages_received":received,
        "quote_messages_accepted":accepted,
        "quote_messages_rejected":rejected,
        "subscription_ack_is_not_per_symbol_quote_liveness":True,
        "full_universe_realtime_coverage":False,
        "robinhood_instrument_eligibility_verified":False,
        "no_raw_prices_or_quote_timestamps_exposed":True,
        "native_financial_account_files_written":0,
        "hyperliquid_provider_requests":0,
        "provider_licenses_independently_accepted":False,
        "supervised_paper_source_authorized":False,
        "financial_operating_gates_accepted":0,
        "paper_orders_created":0,
        "live_orders_created":0,
    }


async def observe(*,seconds,confirmed_scope,offset=0,pins=(),
                  credential_reader=Credentials.load,feed_factory=IEXFeed,
                  snapshot=None):
    # The old host-runner has no independently qualified quote-freshness
    # clock. Only injected synthetic test transports may reach this function;
    # the operational observation must use atlas_r16_iex_basic_native_ntp_observer
    # under the ORIGINAL installed R16 Python image.
    if type(seconds) is not int or not MIN_SECONDS<=seconds<=MAX_SECONDS:
        raise ValueError("R16_IEX_RESEARCH_BOUNDED_SECONDS_REQUIRED")
    if feed_factory is IEXFeed:
        raise ValueError("R16_IEX_UNQUALIFIED_HOST_CLOCK_REAL_FEED_DISABLED")
    plan=prepare(confirmed_scope=confirmed_scope,offset=offset,
                 pins=pins,snapshot=snapshot)
    before=require_selected_r16_data_only()
    roots=inspect_two_lane_native_roots()
    if (not CONFIG.is_file() or CONFIG.is_symlink()
            or CONFIG.is_junction()):
        raise ValueError("R16_IEX_RESEARCH_DATA_ONLY_CREDENTIALS_REQUIRED")
    keys=credential_reader(CONFIG)
    if type(keys) is not Credentials:
        raise ValueError("R16_IEX_RESEARCH_DATA_ONLY_CREDENTIALS_TYPE_REQUIRED")
    data=await feed_factory(plan["requested_symbols"]).run(
        keys,seconds=seconds,max_reconnects=0)
    return sanitize(
        plan,data,seconds=seconds,source_before=before,
        source_after=require_selected_r16_data_only(),
        roots_before=roots,roots_after=inspect_two_lane_native_roots())


def inspect(*,offset=0,pins=()):
    plan=prepare(confirmed_scope=SCOPE,offset=offset,pins=pins)
    return {
        **no_financial_claim(),
        "schema":SCHEMA,
        "status":"R16_CURRENT_30_SYMBOL_CATALOG_PLAN_NO_PROVIDER_REQUEST",
        "catalog_total_research_symbols":plan["catalog_count"],
        "roster_requested_symbols_count":plan["requested_symbol_count"],
        "full_catalog_batches_minimum":
            plan["minimum_rosters_with_same_pinned_symbols"],
        "catalog_sha256":plan["catalog_sha256"],
        "research_offset":offset,
        "pinned_research_symbols":plan["pinned_research_symbols"],
        "next_research_offset_not_committed":plan["next_offset"],
        "credentials_read":False,
        "network_requests":0,
        "provider_subscription_accepted":False,
        "financial_operating_gates_accepted":0,
        "paper_start_authorized":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect",action="store_true")
    mode.add_argument("--execute-data-only",action="store_true")
    p.add_argument("--confirm-scope")
    p.add_argument("--seconds",type=int,default=20)
    p.add_argument("--offset",type=int,default=0)
    p.add_argument("--monitor-research",action="append",default=[])
    args=p.parse_args(argv)
    if args.inspect:
        if args.confirm_scope is not None:
            return 2
        try:
            print(json.dumps(inspect(
                offset=args.offset,pins=args.monitor_research),sort_keys=True))
            return 0
        except (ValueError,OSError,TypeError,KeyError):
            return 2
    # The legacy research-only IEX session uses IEXFeed's default host
    # time.time(), which can reject EVERY quote if Windows UTC is drifting.
    # Real market observation must go through the installed R16 native
    # two-peer NTP observer, never this unqualified host-clock CLI.
    print(json.dumps({
        **no_financial_claim(),"schema":SCHEMA,
        "status":"R16_HOST_WINDOWS_CLOCK_LIVE_RESEARCH_DISABLED_USE_ORIGINAL_NATIVE_NTP",
        "financial_operating_gates_accepted":0,
        "paper_start_authorized":False,
    },sort_keys=True))
    return 2


if __name__=="__main__":
    raise SystemExit(main())
